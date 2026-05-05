from __future__ import annotations

import warnings
from collections.abc import Iterator
from typing import cast

import pytest

from avito.accounts.models import AccountProfile, EmployeeItem
from avito.core.deprecation import _WARNED_SYMBOLS
from avito.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    RateLimitError,
    UpstreamApiError,
    ValidationError,
)
from avito.core.operations import OperationSpec
from avito.core.pagination import PaginatedList
from avito.core.swagger_discovery import DiscoveredSwaggerBinding, discover_swagger_bindings
from avito.core.swagger_linter import _load_sdk_method, _operation_specs_for_sdk_method
from avito.core.swagger_registry import SwaggerOperation, SwaggerRegistry, load_swagger_registry
from avito.testing import (
    SwaggerFakeTransport,
    error_payload,
    generate_schema_value,
    validate_schema_value,
)

_REGISTRY = load_swagger_registry()
_DISCOVERY = discover_swagger_bindings(registry=_REGISTRY)
_BINDINGS = _DISCOVERY.bindings
_BINDING_BY_OPERATION = _DISCOVERY.canonical_map
_BINDING_OPERATION_BY_KEY = {operation.key: operation for operation in _REGISTRY.operations}


def _binding_id(binding: DiscoveredSwaggerBinding) -> str:
    return binding.operation_key or binding.sdk_method


def _error_status_cases() -> tuple[
    tuple[SwaggerOperation, DiscoveredSwaggerBinding, int, type[Exception]],
    ...,
]:
    cases: list[tuple[SwaggerOperation, DiscoveredSwaggerBinding, int, type[Exception]]] = []
    for operation in _REGISTRY.operations:
        binding = _BINDING_BY_OPERATION[operation.key]
        for response in operation.error_responses:
            if response.status_code.isdigit():
                status_code = int(response.status_code)
                cases.append(
                    (
                        operation,
                        binding,
                        status_code,
                        _expected_exception_type(status_code, binding),
                    )
                )
    return tuple(cases)


def _error_status_id(
    case: tuple[SwaggerOperation, DiscoveredSwaggerBinding, int, type[Exception]],
) -> str:
    operation, _binding, status_code, _expected_error = case
    return f"{operation.key} {status_code}"


def _expected_exception_type(
    status_code: int,
    binding: DiscoveredSwaggerBinding,
) -> type[Exception]:
    if binding.domain == "auth":
        return AuthenticationError
    if status_code == 400:
        return ValidationError
    if status_code == 401:
        return AuthenticationError
    if status_code == 403:
        return AuthorizationError
    if status_code == 409:
        return ConflictError
    if status_code == 422:
        return ValidationError
    if status_code == 429:
        return RateLimitError
    return UpstreamApiError


def _binding(registry: SwaggerRegistry, operation_key: str) -> DiscoveredSwaggerBinding:
    discovery = discover_swagger_bindings(registry=registry)
    matches = [binding for binding in discovery.bindings if binding.operation_key == operation_key]
    assert len(matches) == 1
    return matches[0]


def _operation_spec(binding: DiscoveredSwaggerBinding) -> OperationSpec[object]:
    sdk_method = _load_sdk_method(binding)
    specs = _operation_specs_for_sdk_method(sdk_method)
    assert len(specs) == 1, f"{binding.sdk_method}: expected one OperationSpec, got {len(specs)}"
    return cast(OperationSpec[object], specs[0])


def test_swagger_contract_coverage_matches_discovered_bindings() -> None:
    assert len(_BINDINGS) == len(_REGISTRY.operations) == 204
    assert len(_BINDING_BY_OPERATION) == len(_REGISTRY.operations)


def test_swagger_operation_specs_cover_all_declared_json_bodies() -> None:
    failures: list[str] = []
    for binding in _BINDINGS:
        if binding.operation_key is None or binding.domain == "auth":
            continue
        operation = _BINDING_OPERATION_BY_KEY[binding.operation_key]
        spec = _operation_spec(binding)
        request_body = operation.request_body
        if request_body is not None and "application/json" in request_body.content_types:
            if request_body.schema is None:
                failures.append(f"{operation.key}: requestBody schema не разобрана")
            if spec.request_model is None:
                failures.append(f"{operation.key}: {spec.name} без request_model")
        for response in operation.success_responses:
            if "application/json" not in response.content_types:
                continue
            if response.schema is None:
                failures.append(
                    f"{operation.key} {response.status_code}: response schema не разобрана"
                )
            if spec.response_kind == "json" and spec.response_model is None:
                failures.append(
                    f"{operation.key} {response.status_code}: {spec.name} без response_model"
                )
        for response in operation.error_responses:
            if "application/json" not in response.content_types:
                continue
            if response.schema is None:
                failures.append(
                    f"{operation.key} {response.status_code}: error schema не разобрана"
                )
            if response.status_code not in spec.error_models:
                failures.append(
                    f"{operation.key} {response.status_code}: {spec.name} без error_model"
                )

    assert failures == []


@pytest.mark.parametrize("binding", _BINDINGS, ids=_binding_id)
def test_swagger_fake_transport_invokes_every_discovered_binding(
    binding: DiscoveredSwaggerBinding,
) -> None:
    fake = SwaggerFakeTransport(registry=_REGISTRY)
    fake.add_success_operation(binding.operation_key or "")

    warning_context: Iterator[object]
    if binding.deprecated:
        _WARNED_SYMBOLS.clear()
        warning_context = pytest.warns(DeprecationWarning)
    else:
        warning_context = warnings.catch_warnings()
    with warning_context:
        if not binding.deprecated:
            warnings.simplefilter("ignore", DeprecationWarning)
        fake.invoke_binding(binding)

    assert fake.count() >= 1


@pytest.mark.parametrize("binding", _BINDINGS, ids=_binding_id)
def test_swagger_fake_transport_request_body_matches_swagger_schema(
    binding: DiscoveredSwaggerBinding,
) -> None:
    if binding.operation_key is None:
        pytest.fail(f"{binding.sdk_method}: binding без operation_key")
    operation = _BINDING_OPERATION_BY_KEY[binding.operation_key]
    if (
        operation.request_body is None
        or "application/json" not in operation.request_body.content_types
    ):
        return

    fake = SwaggerFakeTransport(registry=_REGISTRY)
    fake.add_success_operation(binding.operation_key)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        fake.invoke_binding(binding)

    request = fake.last()
    if request.json_body is None:
        assert not operation.request_body.required
        return
    assert operation.request_body.schema is not None
    validate_schema_value(
        request.json_body,
        operation.request_body.schema,
        path=f"{operation.key}.requestBody",
    )


@pytest.mark.parametrize("binding", _BINDINGS, ids=_binding_id)
def test_swagger_success_response_models_accept_swagger_schema_payload(
    binding: DiscoveredSwaggerBinding,
) -> None:
    if binding.operation_key is None:
        pytest.fail(f"{binding.sdk_method}: binding без operation_key")
    operation = _BINDING_OPERATION_BY_KEY[binding.operation_key]
    response = next(
        (
            item
            for item in operation.success_responses
            if "application/json" in item.content_types and item.schema is not None
        ),
        None,
    )
    if response is None:
        return

    payload = generate_schema_value(response.schema)
    validate_schema_value(payload, response.schema, path=f"{operation.key}.{response.status_code}")
    fake = SwaggerFakeTransport(registry=_REGISTRY)
    fake.add_operation(operation.key, payload, status_code=int(response.status_code))

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        result = fake.invoke_binding(binding)

    assert not isinstance(result, dict)


def test_swagger_error_contract_coverage_matches_numeric_error_responses() -> None:
    cases = _error_status_cases()
    expected_count = sum(
        1
        for operation in _REGISTRY.operations
        for response in operation.error_responses
        if response.status_code.isdigit()
    )

    assert len(cases) == expected_count == 639


@pytest.mark.parametrize("case", _error_status_cases(), ids=_error_status_id)
def test_swagger_fake_transport_maps_every_declared_error_status(
    case: tuple[SwaggerOperation, DiscoveredSwaggerBinding, int, type[Exception]],
) -> None:
    operation, binding, status_code, expected_error = case
    fake = SwaggerFakeTransport(registry=_REGISTRY)
    fake.add_operation(operation.key, error_payload(status_code), status_code=status_code)

    with pytest.raises(expected_error) as exc_info:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            fake.invoke_binding(binding)

    assert exc_info.value.args[0] == f"Ошибка {status_code}"


@pytest.mark.parametrize("case", _error_status_cases(), ids=_error_status_id)
def test_swagger_error_responses_preserve_swagger_schema_payload(
    case: tuple[SwaggerOperation, DiscoveredSwaggerBinding, int, type[Exception]],
) -> None:
    operation, binding, status_code, expected_error = case
    response = next(
        item for item in operation.error_responses if item.status_code == str(status_code)
    )
    if "application/json" not in response.content_types:
        return
    assert response.schema is not None
    payload = generate_schema_value(response.schema)
    validate_schema_value(payload, response.schema, path=f"{operation.key}.{status_code}")
    fake = SwaggerFakeTransport(registry=_REGISTRY)
    fake.add_operation(operation.key, payload, status_code=status_code)

    with pytest.raises(expected_error) as exc_info:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            fake.invoke_binding(binding)

    assert exc_info.value.payload == payload


def test_swagger_deprecated_contract_covers_all_deprecated_operations() -> None:
    deprecated_bindings = tuple(binding for binding in _BINDINGS if binding.deprecated)

    assert len(deprecated_bindings) == len(_REGISTRY.deprecated_operations) == 7
    for binding in deprecated_bindings:
        _WARNED_SYMBOLS.clear()
        fake = SwaggerFakeTransport(registry=_REGISTRY)
        fake.add_success_operation(binding.operation_key or "")

        with pytest.warns(DeprecationWarning):
            fake.invoke_binding(binding)


def test_swagger_fake_transport_invokes_generated_read_call_and_validates_path() -> None:
    registry = load_swagger_registry()
    binding = _binding(
        registry, "Информацияопользователе.json GET /core/v1/accounts/{user_id}/balance"
    )
    fake = SwaggerFakeTransport(registry=registry)
    fake.add_operation(
        binding.operation_key or "",
        {"user_id": 7, "balance": {"real": 150.0, "bonus": 20.0, "currency": "RUB"}},
    )

    result = fake.invoke_binding(binding)

    request = fake.last()
    assert request.method == "GET"
    assert request.path == "/core/v1/accounts/7/balance/"
    assert request.json_body is None
    assert result.to_dict()["total"] == 170.0


def test_swagger_fake_transport_invokes_generated_write_call_and_validates_json_body() -> None:
    registry = load_swagger_registry()
    binding = _binding(registry, "ИерархияАккаунтов.json POST /listItemsByEmployeeIdV1")
    fake = SwaggerFakeTransport(registry=registry)
    fake.add_operation(
        binding.operation_key or "",
        {
            "items": [{"item_id": 105, "title": "Объявление", "status": "active"}],
            "total": 1,
        },
    )

    result = fake.invoke_binding(binding)

    request = fake.last()
    assert request.method == "POST"
    assert request.path == "/listItemsByEmployeeIdV1"
    assert request.headers["content-type"] == "application/json"
    assert request.json_body == {"employeeId": 10, "categoryId": 1}
    assert isinstance(result, PaginatedList)
    assert isinstance(result[0], EmployeeItem)


def test_swagger_fake_transport_validates_response_status_is_declared_in_swagger() -> None:
    registry = load_swagger_registry()
    fake = SwaggerFakeTransport(registry=registry)

    with pytest.raises(AssertionError, match="не описан в Swagger responses"):
        fake.add_operation(
            "Информацияопользователе.json GET /core/v1/accounts/self",
            {},
            status_code=418,
        )


def test_swagger_fake_transport_maps_happy_path_response_to_typed_sdk_model() -> None:
    registry = load_swagger_registry()
    binding = _binding(registry, "Информацияопользователе.json GET /core/v1/accounts/self")
    fake = SwaggerFakeTransport(registry=registry)
    fake.add_operation(
        binding.operation_key or "",
        {"id": 7, "name": "Иван", "email": "user@example.test", "phone": "+7000"},
    )

    result = fake.invoke_binding(binding)

    assert isinstance(result, AccountProfile)
    assert result.user_id == 7
    assert result.name == "Иван"


@pytest.mark.parametrize(
    ("operation_key", "status_code", "expected_error"),
    [
        (
            "Информацияопользователе.json GET /core/v1/accounts/self",
            401,
            AuthenticationError,
        ),
        (
            "Информацияопользователе.json GET /core/v1/accounts/self",
            403,
            AuthorizationError,
        ),
        (
            "АвитоРабота.json GET /job/v1/applications/get_states",
            400,
            ValidationError,
        ),
        (
            "АвитоРабота.json GET /job/v1/applications/get_states",
            402,
            UpstreamApiError,
        ),
        (
            "АвитоРабота.json GET /job/v1/applications/get_states",
            404,
            UpstreamApiError,
        ),
        (
            "Автостратегия.json POST /autostrategy/v1/campaign/info",
            409,
            ConflictError,
        ),
        (
            "Краткосрочнаяаренда.json POST /realty/v1/items/intervals",
            422,
            ValidationError,
        ),
        (
            "CallTracking[КТ].json GET /calltracking/v1/getRecordByCallId",
            425,
            UpstreamApiError,
        ),
        (
            "АвитоРабота.json GET /job/v1/applications/get_states",
            429,
            RateLimitError,
        ),
        (
            "Информацияопользователе.json GET /core/v1/accounts/self",
            500,
            UpstreamApiError,
        ),
        (
            "Информацияопользователе.json GET /core/v1/accounts/self",
            503,
            UpstreamApiError,
        ),
    ],
)
def test_swagger_fake_transport_validates_all_swagger_error_status_categories(
    operation_key: str,
    status_code: int,
    expected_error: type[Exception],
) -> None:
    registry = load_swagger_registry()
    binding = _binding(registry, operation_key)
    fake = SwaggerFakeTransport(registry=registry)
    fake.add_operation(operation_key, error_payload(status_code), status_code=status_code)

    with pytest.raises(expected_error) as exc_info:
        fake.invoke_binding(binding)

    assert exc_info.value.args[0] == f"Ошибка {status_code}"


def test_swagger_fake_transport_covers_all_error_statuses_declared_by_corpus() -> None:
    registry = load_swagger_registry()

    assert sorted(
        {
            response.status_code
            for operation in registry.operations
            for response in operation.error_responses
            if response.status_code.isdigit()
        }
    ) == ["400", "401", "402", "403", "404", "409", "422", "425", "429", "500", "503"]


def test_swagger_fake_transport_invokes_deprecated_legacy_operation_with_runtime_warning() -> None:
    registry = load_swagger_registry()
    binding = _binding(registry, "Автозагрузка.json GET /autoload/v1/profile")
    fake = SwaggerFakeTransport(registry=registry)
    fake.add_operation(
        binding.operation_key or "",
        {"user_id": 7, "is_enabled": True, "upload_url": "https://example.test/upload"},
    )

    _WARNED_SYMBOLS.clear()
    with pytest.warns(DeprecationWarning):
        result = fake.invoke_binding(binding)

    request = fake.last()
    assert request.method == "GET"
    assert request.path == "/autoload/v1/profile"
    assert result.to_dict()["is_enabled"] is True
