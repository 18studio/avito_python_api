"""Swagger-aware fake transport for SDK contract tests."""

from __future__ import annotations

import inspect
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import MISSING as DATACLASS_MISSING
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, date, datetime
from enum import Enum
from types import UnionType
from typing import Union, cast, get_args, get_origin, get_type_hints
from urllib.parse import parse_qs

import httpx

from avito.auth import AuthSettings
from avito.auth.models import ClientCredentialsRequest, RefreshTokenRequest
from avito.auth.provider import AlternateTokenClient, TokenClient
from avito.client import AvitoClient
from avito.core.swagger_discovery import DiscoveredSwaggerBinding
from avito.core.swagger_names import swagger_field_aliases
from avito.core.swagger_registry import (
    SwaggerOperation,
    SwaggerRegistry,
    SwaggerResponse,
    SwaggerSchema,
)
from avito.core.swagger_schema_paths import (
    SwaggerBodyPath,
    SwaggerSchemaPathError,
    resolve_body_path,
)
from avito.testing.fake_transport import FakeTransport, JsonValue, RecordedRequest

SdkValue = object
_MISSING = object()

_PATH_PARAMETER_RE = re.compile(r"{([A-Za-z_][A-Za-z0-9_]*)}")
_NAME_ALIASES: Mapping[str, tuple[str, ...]] = {
    "campaignId": ("campaign_id",),
    "minimal_duration": ("min_stay_days",),
}
_SDK_CONSTANTS: Mapping[str, SdkValue] = {
    "account_id": 7,
    "action_id": 101,
    "call_id": 102,
    "campaign_id": 103,
    "category_id": 1,
    "chat_id": "chat-1",
    "delivery_provider_id": "provider-1",
    "dictionary_id": 104,
    "employee_id": 10,
    "grant_type": "client_credentials",
    "grouping": "day",
    "is_enabled": True,
    "item_id": 105,
    "item_ids": [105],
    "limit": 2,
    "message_id": "message-1",
    "offset": 0,
    "order_id": 106,
    "parcel_id": 107,
    "price": 1500,
    "report_id": 108,
    "review_id": 115,
    "resume_id": 109,
    "scoring_id": 110,
    "tariff_id": 111,
    "teaser_id": "teaser-1",
    "task_id": 112,
    "user_id": 7,
    "url": "https://example.test/file.xml",
    "vacancy_id": 113,
    "vacancy_uuid": "vacancy-uuid-1",
    "value": "value",
    "subscriptionId": 1,
    "vehicle_id": "XTA210990Y2766384",
    "version": 1,
    "voice_ids": ["voice-1"],
}
_BODY_VALUES: Mapping[str, SdkValue] = {
    "action": "approve",
    "action_type_id": 1,
    "action_id": 101,
    "action_ids": [101],
    "applies": [],
    "auto_renewal": True,
    "autoload_enabled": True,
    "bid_penny": 1000,
    "billing_type": "package",
    "blacklisted_user_id": 7,
    "blocked_dates": ["2026-05-01"],
    "brand_id": 1,
    "budget_penny": 1000,
    "budget_type": "daily",
    "business_area": 7,
    "call_id": 102,
    "campaign_id": 103,
    "code": "1234",
    "codes": ["xl"],
    "date_time_from": "2026-04-01T00:00:00+00:00",
    "date_time_to": "2026-04-02T00:00:00+00:00",
    "dateFrom": "2026-04-01",
    "dateTo": "2026-04-02",
    "description": "Описание вакансии",
    "dispatch_id": 1,
    "employee_id": 10,
    "employment": "full",
    "experience": "noMatter",
    "files": ["file-1"],
    "grouping": "day",
    "is_enabled": True,
    "ids": [101],
    "image_id": "image-1",
    "intervals": [],
    "item_id": 105,
    "item_ids": [105],
    "limit": 2,
    "message": "Тестовое сообщение",
    "metrics": ["views"],
    "mileage": 10000,
    "min_stay_days": 2,
    "name": "Тариф",
    "order_id": 106,
    "package_code": "xl",
    "offer_slug": "discount",
    "periods": [{"date_from": "2026-05-01", "date_to": "2026-05-02"}],
    "pickup_point_id": 1,
    "plate_number": "А123АА77",
    "postal_office_id": 1,
    "preview_id": 1,
    "price": 1500,
    "reason": "test",
    "reg_number": "А123АА77",
    "report_email": "autoload@example.test",
    "recipients_count": 1,
    "schedule": "fixed",
    "schedule_rate": 100,
    "secret": "cb1e150b-c5bf-4c3e-acd1-20ec88bdb3a1",
    "specification_id": 1,
    "spendingTypes": ["promotion"],
    "slugs": ["xl"],
    "task_id": 112,
    "text": "Ответ",
    "title": "Тест",
    "transition": "confirm",
    "url": "https://example.test/file.xml",
    "vacancy_id": 113,
    "vacancy_schedule": "fixed",
    "vehicle_id": "XTA210990Y2766384",
    "vehicles": [{"vin": "XTA210990Y2766384"}],
    "vin": "XTA210990Y2766384",
}


@dataclass(frozen=True, slots=True)
class SwaggerRoute:
    """Registered fake route bound to one Swagger operation."""

    operation: SwaggerOperation
    payload: JsonValue
    status_code: int
    headers: Mapping[str, str]


class SwaggerFakeTransport(FakeTransport):
    """Fake transport that validates requests against local Swagger operations."""

    def __init__(
        self,
        *,
        registry: SwaggerRegistry,
        base_url: str = "https://api.avito.ru",
    ) -> None:
        super().__init__(base_url=base_url)
        self.registry = registry
        self._swagger_routes: dict[str, SwaggerRoute] = {}

    def add_operation(
        self,
        operation_key: str,
        payload: JsonValue,
        *,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
    ) -> SwaggerFakeTransport:
        """Register response for one Swagger operation key."""

        operation = self.operation(operation_key)
        self._validate_declared_status(operation, status_code)
        self._swagger_routes[operation.key] = SwaggerRoute(
            operation=operation,
            payload=payload,
            status_code=status_code,
            headers=dict(headers or {}),
        )
        return self

    def add_success_operation(
        self,
        operation_key: str,
        *,
        payload: JsonValue | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> SwaggerFakeTransport:
        """Register a deterministic success response for one Swagger operation."""

        operation = self.operation(operation_key)
        response = _success_response(operation)
        status_code = int(response.status_code)
        return self.add_operation(
            operation_key,
            success_payload(operation) if payload is None else payload,
            status_code=status_code,
            headers=headers,
        )

    def operation(self, operation_key: str) -> SwaggerOperation:
        """Return operation metadata by canonical key."""

        for operation in self.registry.operations:
            if operation.key == operation_key:
                return operation
        raise AssertionError(f"Swagger operation не найдена: {operation_key}")

    def invoke_binding(
        self,
        binding: DiscoveredSwaggerBinding,
        *,
        client: AvitoClient | None = None,
    ) -> object:
        """Build and invoke SDK call from discovered Swagger binding metadata."""

        if binding.operation_key is None:
            raise AssertionError(f"Привязка Swagger неоднозначна: {binding.sdk_method}")
        if binding.domain == "auth":
            target = self._build_auth_target(binding)
            method = getattr(target, binding.method_name)
            return method(**self._build_arguments(binding.method_args, method))
        sdk_client = client or self.as_client(user_id=cast(int, _SDK_CONSTANTS["user_id"]))
        target = self._build_target(sdk_client, binding)
        method = getattr(target, binding.method_name)
        return method(**self._build_arguments(binding.method_args, method))

    def _handle(self, request: httpx.Request) -> httpx.Response:
        recorded = RecordedRequest(
            method=request.method.upper(),
            path=request.url.path,
            params=dict(request.url.params),
            headers=dict(request.headers),
            json_body=self._decode_json(request),
            content=request.content,
        )
        self.requests.append(recorded)

        route = self._match_route(recorded)
        self._validate_request(route.operation, recorded)
        response = httpx.Response(
            route.status_code,
            json=route.payload,
            headers=dict(route.headers),
        )
        response.request = request
        return response

    def _build_target(
        self,
        client: AvitoClient,
        binding: DiscoveredSwaggerBinding,
    ) -> object:
        if binding.factory is None:
            raise AssertionError(f"Binding не содержит AvitoClient factory: {binding.sdk_method}")
        factory = getattr(client, binding.factory)
        return factory(**self._build_arguments(binding.factory_args, factory))

    def _build_auth_target(self, binding: DiscoveredSwaggerBinding) -> object:
        settings = AuthSettings(
            client_id="fake-client-id",
            client_secret="fake-client-secret",
            refresh_token="fake-refresh-token",
            scope="fake-scope",
            token_url=binding.path,
            alternate_token_url=binding.path,
            autoteka_token_url="/token",
            autoteka_client_id="fake-autoteka-client-id",
            autoteka_client_secret="fake-autoteka-client-secret",
            autoteka_scope="autoteka:read",
        )
        client = httpx.Client(
            transport=httpx.MockTransport(self._handle),
            base_url=self.base_url,
        )
        if binding.class_name == "AlternateTokenClient":
            return AlternateTokenClient(settings=settings, client=client)
        if binding.class_name == "TokenClient":
            return TokenClient(settings=settings, client=client)
        raise AssertionError(f"Неподдерживаемый auth binding: {binding.sdk_method}")

    def _build_arguments(
        self,
        mapping: Mapping[str, str],
        callable_object: Callable[..., object],
    ) -> dict[str, object]:
        signature = inspect.signature(callable_object)
        type_hints = _callable_type_hints(callable_object)
        arguments = {}
        for argument_name, expression in mapping.items():
            parameter = signature.parameters.get(argument_name)
            arguments[argument_name] = self._value_for_argument(
                argument_name,
                expression,
                parameter,
                type_hints.get(argument_name),
            )
        for name, parameter in signature.parameters.items():
            if name == "self" or name in arguments:
                continue
            if (
                parameter.default is inspect.Parameter.empty
                or self._should_supply_optional_argument(name, parameter)
            ):
                arguments[name] = self._value_for_argument(
                    name,
                    f"constant.{name}",
                    parameter,
                    type_hints.get(name),
                )
        return arguments

    def _value_for_argument(
        self,
        argument_name: str,
        expression: str,
        parameter: inspect.Parameter | None,
        annotation_type: object | None,
    ) -> object:
        annotation = _annotation_name(parameter)
        if "ClientCredentialsRequest" in annotation:
            return ClientCredentialsRequest(
                client_id="fake-client-id",
                client_secret="fake-client-secret",
                scope="fake-scope",
            )
        if "RefreshTokenRequest" in annotation:
            return RefreshTokenRequest(
                client_id="fake-client-id",
                client_secret="fake-client-secret",
                refresh_token="fake-refresh-token",
                scope="fake-scope",
            )
        if argument_name == "query":
            return self._query_value(annotation)
        if argument_name == "files" or "UploadImageFile" in annotation:
            from avito.messenger.models import UploadImageFile

            return [
                UploadImageFile(
                    field_name="image",
                    filename="image.jpg",
                    content=b"image-bytes",
                    content_type="image/jpeg",
                )
            ]
        if expression == "body":
            return self._body_value(
                argument_name,
                annotation,
                annotation_type,
                self._current_request_body_schema(),
            )
        return self._value_for_expression(
            expression,
            argument_name=argument_name,
            annotation=annotation,
            annotation_type=annotation_type,
        )

    def _value_for_expression(
        self,
        expression: str,
        *,
        argument_name: str,
        annotation: str,
        annotation_type: object | None,
    ) -> object:
        if expression == "body":
            return self._body_value(
                argument_name,
                annotation,
                annotation_type,
                self._current_request_body_schema(),
            )
        prefix, separator, field_name = expression.partition(".")
        if not separator:
            raise AssertionError(f"Некорректное binding expression: {expression}")
        if prefix in {"path", "query", "header", "constant"}:
            return self._value_for_name(field_name)
        if prefix == "body":
            return self._body_path_value(argument_name, field_name, annotation, annotation_type)
        raise AssertionError(f"Неподдерживаемое binding expression: {expression}")

    def _query_value(self, annotation: str) -> object:
        if "MonitoringEventsQuery" in annotation:
            from avito.autoteka.models import MonitoringEventsQuery

            return MonitoringEventsQuery(limit=2)
        if "ApplicationIdsQuery" in annotation:
            from avito.jobs.models import ApplicationIdsQuery

            return ApplicationIdsQuery(updated_at_from="2026-04-01T00:00:00+00:00")
        if "ResumeSearchQuery" in annotation:
            from avito.jobs.models import ResumeSearchQuery

            return ResumeSearchQuery(query="python")
        if "VacanciesQuery" in annotation:
            from avito.jobs.models import VacanciesQuery

            return VacanciesQuery(query="python")
        if "ReviewsQuery" in annotation:
            from avito.ratings.models import ReviewsQuery

            return ReviewsQuery(offset=0, limit=10)
        return self._value_for_name("query")

    def _body_value(
        self,
        argument_name: str,
        annotation: str,
        annotation_type: object | None,
        schema: SwaggerSchema | None,
    ) -> object:
        value = self._value_for_type(argument_name, annotation_type, schema)
        if value is not _MISSING:
            return value
        return self._body_field_value(argument_name, argument_name, annotation, annotation_type, schema)

    def _body_path_value(
        self,
        argument_name: str,
        path: str,
        annotation: str,
        annotation_type: object | None,
    ) -> object:
        binding = self._binding_body_path(path)
        if "datetime" in annotation:
            return datetime(2026, 5, 1, tzinfo=UTC)
        if _is_nested_body_path(binding):
            value = _known_value(argument_name)
            if value is not _MISSING:
                return _coerce_schema_value(value, binding)
            value = _known_value(*_name_aliases(binding.leaf_name))
            if value is not _MISSING:
                return _coerce_schema_value(value, binding)
        return _coerce_schema_value(
            self._body_field_value(
                argument_name,
                binding.leaf_name,
                annotation,
                annotation_type,
                binding.leaf_schema,
            ),
            binding,
        )

    def _binding_body_path(self, path: str) -> SwaggerBodyPath:
        for route in self._swagger_routes.values():
            request_body = route.operation.request_body
            if request_body is None or request_body.schema is None:
                continue
            try:
                return resolve_body_path(request_body.schema, path)
            except SwaggerSchemaPathError:
                continue
        raise AssertionError(f"Swagger body path не найден: body.{path}")

    def _current_request_body_schema(self) -> SwaggerSchema | None:
        for route in self._swagger_routes.values():
            if route.operation.request_body is not None:
                return route.operation.request_body.schema
        return None

    def _body_field_value(
        self,
        argument_name: str,
        field_name: str,
        annotation: str,
        annotation_type: object | None,
        schema: SwaggerSchema | None,
    ) -> object:
        if field_name == "ids" and "str" in annotation:
            return ["id-1"]
        value = _known_value(*_name_aliases(field_name))
        if value is not _MISSING:
            return value
        typed_value = self._value_for_type(field_name, annotation_type, schema)
        if typed_value is not _MISSING:
            return typed_value
        if "datetime" in annotation:
            return datetime(2026, 5, 1, tzinfo=UTC)
        return self._value_for_name(field_name)

    def _value_for_type(
        self,
        name: str,
        annotation_type: object | None,
        schema: SwaggerSchema | None,
    ) -> object:
        if annotation_type is None:
            return _MISSING
        annotation_type = _unwrap_optional(annotation_type)
        origin = get_origin(annotation_type)
        if origin in {list, Sequence}:
            item_type = _first_type_arg(annotation_type)
            item_schema = schema.items if schema is not None and schema.is_array else None
            item = self._value_for_type(_singular_name(name), item_type, item_schema)
            if item is not _MISSING:
                return [item]
            return _MISSING
        if annotation_type is datetime:
            return datetime(2026, 5, 1, tzinfo=UTC)
        if _is_date_input_type(annotation_type):
            value = _dateish_value(name)
            return "2026-05-01" if value is _MISSING else value
        if inspect.isclass(annotation_type) and issubclass(annotation_type, Enum):
            enum_values = list(annotation_type)
            if enum_values:
                return enum_values[0]
        if is_dataclass(annotation_type):
            return self._dataclass_value(cast(type, annotation_type), schema)
        if annotation_type is str:
            return self._string_value(name, schema)
        if annotation_type is int:
            return 1
        if annotation_type is float:
            return 1.5
        if annotation_type is bool:
            return True
        return _MISSING

    def _dataclass_value(self, model_type: type, schema: SwaggerSchema | None) -> object:
        type_hints = get_type_hints(model_type)
        kwargs: dict[str, object] = {}
        schema_properties = schema.properties if schema is not None and schema.is_object else {}
        schema_required = schema.required if schema is not None and schema.is_object else frozenset()
        for field in fields(model_type):
            field_schema = _schema_for_dataclass_field(field.name, schema_properties)
            field_type = type_hints.get(field.name)
            should_fill = (
                field.default is DATACLASS_MISSING
                and field.default_factory is DATACLASS_MISSING
            )
            if schema_properties:
                serialized_names = _name_aliases(field.name)
                should_fill = should_fill or any(name in schema_required for name in serialized_names)
                should_fill = should_fill or field_schema is not None and not _allows_none(field_type)
            if not should_fill:
                continue
            value = self._value_for_type(field.name, field_type, field_schema)
            if value is _MISSING:
                value = self._value_for_name(field.name)
            kwargs[field.name] = value
        return model_type(**kwargs)

    def _string_value(self, name: str, schema: SwaggerSchema | None) -> str:
        if schema is not None and schema.enum:
            enum_value = schema.enum[0]
            if isinstance(enum_value, str):
                return enum_value
        value = self._value_for_name(name)
        return value if isinstance(value, str) else str(value)

    def _should_supply_optional_argument(
        self,
        name: str,
        parameter: inspect.Parameter,
    ) -> bool:
        if parameter.default is not None:
            return False
        return name in _SDK_CONSTANTS or name in {"item_ids", "query"}

    def _value_for_name(self, name: str) -> object:
        if name == "intervals":
            from avito.realty.models import RealtyInterval

            return [RealtyInterval(date="2026-05-01", available=True)]
        if name == "blocked_dates":
            return ["2026-05-01"]
        if name == "data":
            return ["XTA210990Y2766384"]
        if name == "autoload_enabled":
            return True
        if name == "feeds_data":
            return "https://example.test/feed.xml"
        if name == "report_email":
            return "autoload@example.test"
        if name == "schedule":
            return 100
        if name == "upload_url":
            return "https://example.test/feed.xml"
        if name == "date_start":
            return "2026-05-01"
        if name == "date_end":
            return "2026-05-02"
        dateish_value = _dateish_value(name)
        if dateish_value is not _MISSING:
            return dateish_value
        value = _known_value(*_name_aliases(name))
        if value is not _MISSING:
            return value
        return f"{name}-value"

    def _match_route(self, request: RecordedRequest) -> SwaggerRoute:
        for route in self._swagger_routes.values():
            if route.operation.method != request.method:
                continue
            if self._path_matches(route.operation.path, request.path):
                return route
        available = ", ".join(
            f"{route.operation.method} {route.operation.path}"
            for route in self._swagger_routes.values()
        )
        raise AssertionError(
            f"Маршрут не соответствует Swagger operation: {request.method} "
            f"{request.path}. Доступные: {available}"
        )

    def _validate_request(self, operation: SwaggerOperation, request: RecordedRequest) -> None:
        path_values = self._extract_path_values(operation.path, request.path)
        form_values = self._form_values(request)
        for parameter in operation.parameters:
            if parameter.location == "path" and parameter.required:
                if parameter.name not in path_values:
                    raise AssertionError(f"Не найден path parameter `{parameter.name}`.")
            if parameter.location == "query" and parameter.required:
                if parameter.name not in request.params and parameter.name not in form_values:
                    raise AssertionError(f"Не найден query parameter `{parameter.name}`.")
            if parameter.location == "header" and parameter.required:
                if parameter.name.lower() == "authorization":
                    continue
                headers = {name.lower() for name in request.headers}
                if parameter.name.lower() not in headers:
                    raise AssertionError(f"Не найден header parameter `{parameter.name}`.")
        if operation.request_body is None:
            return
        if operation.request_body.required and request.content == b"":
            raise AssertionError(f"{operation.key}: requestBody обязателен.")
        content_type = request.headers.get("content-type", "")
        if request.content and operation.request_body.content_types:
            if not any(
                expected in content_type for expected in operation.request_body.content_types
            ):
                raise AssertionError(
                    f"{operation.key}: content-type `{content_type}` не описан в Swagger."
                )
        if "application/json" in content_type and request.content:
            try:
                json.loads(request.content.decode())
            except json.JSONDecodeError as exc:
                raise AssertionError(f"{operation.key}: requestBody не является JSON.") from exc

    def _form_values(self, request: RecordedRequest) -> Mapping[str, str]:
        content_type = request.headers.get("content-type", "")
        if "application/x-www-form-urlencoded" not in content_type or not request.content:
            return {}
        parsed = parse_qs(request.content.decode())
        return {name: values[-1] for name, values in parsed.items() if values}

    def _validate_declared_status(self, operation: SwaggerOperation, status_code: int) -> None:
        declared = {
            int(response.status_code)
            for response in operation.responses
            if response.status_code.isdigit()
        }
        if status_code not in declared:
            raise AssertionError(
                f"{operation.key}: status {status_code} не описан в Swagger responses."
            )

    def _path_matches(self, template: str, path: str) -> bool:
        return (
            self._path_pattern(template).fullmatch(self._normalize_swagger_path(path)) is not None
        )

    def _extract_path_values(self, template: str, path: str) -> Mapping[str, str]:
        match = self._path_pattern(template).fullmatch(self._normalize_swagger_path(path))
        return match.groupdict() if match is not None else {}

    def _path_pattern(self, template: str) -> re.Pattern[str]:
        pattern = "^"
        position = 0
        for match in _PATH_PARAMETER_RE.finditer(template):
            pattern += re.escape(template[position : match.start()])
            pattern += f"(?P<{match.group(1)}>[^/]+)"
            position = match.end()
        pattern += re.escape(template[position:])
        pattern += "$"
        return re.compile(pattern)

    def _normalize_swagger_path(self, path: str) -> str:
        if path != "/":
            return path.rstrip("/")
        return path


def error_payload(status_code: int) -> JsonValue:
    """Build deterministic JSON error payload for contract tests."""

    return {
        "message": f"Ошибка {status_code}",
        "code": f"status_{status_code}",
        "details": {"status": status_code},
    }


def success_payload(operation: SwaggerOperation) -> JsonValue:
    """Build deterministic success payload for one operation."""

    if operation.spec in {"Авторизация.json", "Автотека.json"} and operation.path.startswith(
        "/token"
    ):
        return {
            "access_token": "access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "refresh-token",
            "scope": "fake-scope",
        }
    if operation.key == "CallTracking[КТ].json POST /calltracking/v1/getCallById":
        return {"call": {"id": "call-1"}, "error": {"code": 0, "message": "ok"}}
    if operation.key == "Продвижение.json POST /promotion/v1/items/services/orders/status":
        return {"orderId": "order-1", "status": "active", "items": [], "errors": []}
    if operation.key == "Настройкаценыцелевогодействия.json GET /cpxpromo/1/getBids/{itemId}":
        return {"actionTypeID": 1, "selectedType": "manual", "manual": {}, "auto": {}}
    if (
        operation.key
        == "Настройкаценыцелевогодействия.json POST /cpxpromo/1/getPromotionsByItemIds"
    ):
        return {"items": []}
    return {}


def _success_response(operation: SwaggerOperation) -> SwaggerResponse:
    for response in operation.success_responses:
        if response.status_code.isdigit():
            return response
    raise AssertionError(f"{operation.key}: Swagger operation не содержит success response.")


def _annotation_name(parameter: inspect.Parameter | None) -> str:
    if parameter is None:
        return ""
    annotation = parameter.annotation
    if annotation is inspect.Parameter.empty:
        return ""
    return str(annotation)


def _callable_type_hints(callable_object: Callable[..., object]) -> Mapping[str, object]:
    try:
        return get_type_hints(callable_object)
    except (NameError, TypeError):
        return {}


def _known_value(*names: str) -> object:
    for name in names:
        if name in _BODY_VALUES:
            return _BODY_VALUES[name]
        if name in _SDK_CONSTANTS:
            return _SDK_CONSTANTS[name]
    return _MISSING


def _name_aliases(name: str) -> tuple[str, ...]:
    aliases = _NAME_ALIASES.get(name, ())
    return (*swagger_field_aliases(name), *aliases)


def _schema_for_dataclass_field(
    field_name: str,
    schema_properties: Mapping[str, SwaggerSchema],
) -> SwaggerSchema | None:
    for name in _name_aliases(field_name):
        if name in schema_properties:
            return schema_properties[name]
    return None


def _unwrap_optional(annotation_type: object) -> object:
    origin = get_origin(annotation_type)
    if origin not in {UnionType, Union}:
        return annotation_type
    args = tuple(item for item in get_args(annotation_type) if item is not type(None))
    if len(args) == 1:
        return args[0]
    return annotation_type


def _allows_none(annotation_type: object | None) -> bool:
    if annotation_type is None:
        return True
    origin = get_origin(annotation_type)
    if origin not in {UnionType, Union}:
        return False
    return any(item is type(None) for item in get_args(annotation_type))


def _first_type_arg(annotation_type: object) -> object | None:
    args = get_args(annotation_type)
    return args[0] if args else None


def _is_date_input_type(annotation_type: object) -> bool:
    origin = get_origin(annotation_type)
    if origin not in {UnionType, Union}:
        return False
    args = set(get_args(annotation_type))
    return date in args and datetime in args and str in args


def _dateish_value(name: str) -> object:
    normalized = name.lower()
    if normalized in {"date", "created_at", "updated_at"}:
        return "2026-05-01T00:00:00+00:00"
    if "date" in normalized or "time" in normalized or normalized.endswith("_at"):
        return "2026-05-01T00:00:00+00:00"
    return _MISSING


def _singular_name(name: str) -> str:
    if name.endswith("ies"):
        return f"{name[:-3]}y"
    if name.endswith("s"):
        return name[:-1]
    return name


def _is_nested_body_path(path: SwaggerBodyPath) -> bool:
    return len(path.segments) > 1 or any(segment.array for segment in path.segments)


def _coerce_schema_value(value: object, path: SwaggerBodyPath) -> object:
    if path.leaf_schema.kind == "string" and isinstance(value, int | float) and not isinstance(
        value, bool
    ):
        return str(value)
    return value


__all__ = ("SwaggerFakeTransport", "SwaggerRoute", "error_payload", "success_payload")
