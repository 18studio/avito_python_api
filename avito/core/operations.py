"""Operation specifications and executor for v2 domain architecture."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from email.message import Message
from typing import Literal, Protocol, TypeVar, cast
from urllib.parse import quote

import httpx

from avito.core.models import ApiErrorPayload, RequestModel
from avito.core.types import ApiTimeouts, BinaryResponse, HttpMethod, RequestContext, RetryOverride

ResponseKind = Literal["json", "empty", "binary"]
RetryMode = Literal["default", "enabled", "disabled"]
ModelT = TypeVar("ModelT", covariant=True)
ResponseT = TypeVar("ResponseT", covariant=True)
DEFAULT_ERROR_MODELS: Mapping[str, type[ResponseModel[object]]] = {
    "400": ApiErrorPayload,
    "401": ApiErrorPayload,
    "402": ApiErrorPayload,
    "403": ApiErrorPayload,
    "404": ApiErrorPayload,
    "409": ApiErrorPayload,
    "422": ApiErrorPayload,
    "425": ApiErrorPayload,
    "429": ApiErrorPayload,
    "500": ApiErrorPayload,
    "503": ApiErrorPayload,
    "default": ApiErrorPayload,
}


class ResponseModel(Protocol[ModelT]):
    """Protocol for response model classes parsed from JSON payloads."""

    @classmethod
    def from_payload(cls, payload: object) -> ModelT:
        """Build response model from raw JSON payload."""


class ParamsModel(Protocol):
    """Protocol for query models."""

    def to_params(self) -> Mapping[str, object]:
        """Serialize model to query params."""


class PayloadModel(Protocol):
    """Protocol for request models."""

    def to_payload(self) -> object:
        """Serialize model to JSON payload."""


class OperationTransport(Protocol):
    """Transport methods required by the operation executor."""

    def request(
        self,
        method: HttpMethod,
        path: str,
        *,
        context: RequestContext,
        params: Mapping[str, object] | None = None,
        json_body: object | None = None,
        data: Mapping[str, object] | None = None,
        files: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
        content: bytes | None = None,
        idempotency_key: str | None = None,
    ) -> httpx.Response:
        """Execute raw request and return response object."""

    def request_json(
        self,
        method: HttpMethod,
        path: str,
        *,
        context: RequestContext,
        params: Mapping[str, object] | None = None,
        json_body: object | None = None,
        data: Mapping[str, object] | None = None,
        files: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> object:
        """Execute request and return decoded JSON payload."""


@dataclass(slots=True, frozen=True)
class EmptyResponse:
    """Typed result for successful operations without response body."""

    status_code: int
    headers: Mapping[str, str] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class OperationSpec[ResponseT]:
    """HTTP contract metadata for a single SDK operation."""

    name: str
    method: HttpMethod
    path: str
    query_model: type[object] | None = None
    request_model: type[object] | None = None
    response_model: type[ResponseModel[ResponseT]] | None = None
    error_models: Mapping[str, type[ResponseModel[object]]] = field(
        default_factory=lambda: DEFAULT_ERROR_MODELS
    )
    response_kind: ResponseKind = "json"
    content_type: str | None = None
    requires_auth: bool = True
    retry_mode: RetryMode = "default"


class OperationExecutor:
    """Execute operation specs through the shared transport layer."""

    def __init__(self, transport: OperationTransport) -> None:
        self._transport = transport

    def execute(
        self,
        spec: OperationSpec[ResponseT],
        *,
        path_params: Mapping[str, object] | None = None,
        query: object | Mapping[str, object] | None = None,
        request: object | Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
        idempotency_key: str | None = None,
        data: Mapping[str, object] | None = None,
        files: Mapping[str, object] | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> ResponseT:
        """Execute operation spec and return typed response object."""

        path = render_path(spec.path, path_params or {})
        params = _serialize_query(spec, query)
        json_body = _serialize_request(spec, request)
        request_headers = _merge_content_type(headers, spec.content_type)
        effective_retry = spec.retry_mode if retry is None or retry == "default" else retry
        context = RequestContext(
            operation_name=spec.name,
            allow_retry=effective_retry == "enabled",
            retry_disabled=effective_retry == "disabled",
            requires_auth=spec.requires_auth,
            timeout=timeout,
        )

        if spec.response_kind == "binary":
            return cast(
                ResponseT,
                _request_binary(
                    self._transport,
                    spec=spec,
                    path=path,
                    context=context,
                    params=params,
                    headers=request_headers,
                    idempotency_key=idempotency_key,
                ),
            )
        if spec.response_kind == "empty":
            response = self._transport.request(
                spec.method,
                path,
                context=context,
                params=params,
                json_body=json_body,
                data=data,
                files=files,
                headers=request_headers,
                idempotency_key=idempotency_key,
            )
            return cast(
                ResponseT,
                EmptyResponse(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                ),
            )

        payload = self._transport.request_json(
            spec.method,
            path,
            context=context,
            params=params,
            json_body=json_body,
            data=data,
            files=files,
            headers=request_headers,
            idempotency_key=idempotency_key,
        )
        if spec.response_model is None:
            return cast(ResponseT, payload)
        return spec.response_model.from_payload(payload)


def render_path(path_template: str, path_params: Mapping[str, object]) -> str:
    """Render operation path and percent-encode path parameter values."""

    path = path_template
    for key, value in path_params.items():
        path = path.replace("{" + key + "}", quote(str(value), safe=""))
    return path


def _serialize_query[SpecResponseT](
    spec: OperationSpec[SpecResponseT],
    query: object | Mapping[str, object] | None,
) -> Mapping[str, object] | None:
    if query is None:
        return None
    if isinstance(query, RequestModel):
        return query.to_params()
    if spec.query_model is not None and isinstance(query, spec.query_model):
        return cast(ParamsModel, query).to_params()
    if isinstance(query, Mapping):
        return query
    raise TypeError("Query object не поддерживает сериализацию.")


def _serialize_request[SpecResponseT](
    spec: OperationSpec[SpecResponseT],
    request: object | Mapping[str, object] | None,
) -> object | None:
    if request is None:
        return None
    if isinstance(request, RequestModel):
        return request.to_payload()
    if spec.request_model is not None and isinstance(request, spec.request_model):
        return cast(PayloadModel, request).to_payload()
    if isinstance(request, Mapping):
        return request
    raise TypeError("Request object не поддерживает сериализацию.")


def _merge_content_type(
    headers: Mapping[str, str] | None,
    content_type: str | None,
) -> Mapping[str, str] | None:
    if content_type is None:
        return headers
    merged = dict(headers or {})
    merged.setdefault("Content-Type", content_type)
    return merged


def _request_binary[SpecResponseT](
    transport: OperationTransport,
    *,
    spec: OperationSpec[SpecResponseT],
    path: str,
    context: RequestContext,
    params: Mapping[str, object] | None,
    headers: Mapping[str, str] | None,
    idempotency_key: str | None,
) -> BinaryResponse:
    response = transport.request(
        spec.method,
        path,
        context=context,
        params=params,
        headers=headers,
        idempotency_key=idempotency_key,
    )
    return BinaryResponse(
        content=response.content,
        content_type=response.headers.get("content-type"),
        filename=_extract_filename(response.headers.get("content-disposition")),
        status_code=response.status_code,
        headers=dict(response.headers),
    )


def _extract_filename(content_disposition: str | None) -> str | None:
    if content_disposition is None:
        return None
    message = Message()
    message["content-disposition"] = content_disposition
    filename = message.get_param("filename", header="content-disposition")
    if isinstance(filename, tuple):
        _, _, decoded_value = filename
        return decoded_value
    return filename


__all__ = (
    "EmptyResponse",
    "OperationExecutor",
    "OperationSpec",
    "OperationTransport",
    "DEFAULT_ERROR_MODELS",
    "ResponseKind",
    "ResponseModel",
    "RetryMode",
    "render_path",
)
