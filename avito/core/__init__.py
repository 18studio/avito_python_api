"""Пакет общей инфраструктуры SDK."""

from avito.core.domain import DomainObject
from avito.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    AvitoError,
    ClientClosedError,
    ConfigurationError,
    ConflictError,
    RateLimitError,
    ResponseMappingError,
    TransportError,
    UnsupportedOperationError,
    UpstreamApiError,
    ValidationError,
)
from avito.core.fields import api_field
from avito.core.models import ApiErrorPayload, ApiModel, EmptyRequest, RequestModel
from avito.core.operations import EmptyResponse, OperationExecutor, OperationSpec
from avito.core.pagination import PaginatedList, Paginator
from avito.core.payload import JsonReader
from avito.core.retries import RetryDecision, RetryPolicy
from avito.core.serialization import SerializableModel
from avito.core.swagger import SwaggerOperationBinding, swagger_operation
from avito.core.transport import Transport
from avito.core.types import (
    ApiTimeouts,
    BinaryResponse,
    JsonPage,
    RequestContext,
    RetryOverride,
    TransportDebugInfo,
)

__all__ = (
    "ApiTimeouts",
    "ApiModel",
    "ApiErrorPayload",
    "AuthenticationError",
    "AuthorizationError",
    "AvitoError",
    "BinaryResponse",
    "ClientClosedError",
    "ConfigurationError",
    "ConflictError",
    "DomainObject",
    "EmptyResponse",
    "EmptyRequest",
    "JsonReader",
    "JsonPage",
    "OperationExecutor",
    "OperationSpec",
    "PaginatedList",
    "Paginator",
    "RateLimitError",
    "RequestContext",
    "RequestModel",
    "ResponseMappingError",
    "RetryDecision",
    "RetryOverride",
    "RetryPolicy",
    "SerializableModel",
    "SwaggerOperationBinding",
    "Transport",
    "TransportDebugInfo",
    "TransportError",
    "UnsupportedOperationError",
    "UpstreamApiError",
    "ValidationError",
    "api_field",
    "swagger_operation",
)
