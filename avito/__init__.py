"""Публичные экспорты пакета SDK для Avito."""

from avito.auth.settings import AuthSettings
from avito.client import AvitoClient
from avito.config import AvitoSettings
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
from avito.core.pagination import PaginatedList
from avito.summary import (
    AccountHealthSummary,
    CapabilityDiscoveryResult,
    CapabilityInfo,
    ChatSummary,
    ListingHealthItem,
    ListingHealthSummary,
    OrderSummary,
    PromotionSummary,
    ReviewSummary,
    SummaryUnavailableSection,
)

__all__ = (
    "AccountHealthSummary",
    "AuthSettings",
    "AuthenticationError",
    "AuthorizationError",
    "AvitoClient",
    "AvitoError",
    "AvitoSettings",
    "CapabilityDiscoveryResult",
    "CapabilityInfo",
    "ChatSummary",
    "ClientClosedError",
    "ConfigurationError",
    "ConflictError",
    "ListingHealthItem",
    "ListingHealthSummary",
    "OrderSummary",
    "PaginatedList",
    "PromotionSummary",
    "RateLimitError",
    "ResponseMappingError",
    "ReviewSummary",
    "SummaryUnavailableSection",
    "TransportError",
    "UnsupportedOperationError",
    "UpstreamApiError",
    "ValidationError",
)
