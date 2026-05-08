from __future__ import annotations

import warnings
from collections.abc import Iterator

import pytest

from avito.core.deprecation import _WARNED_SYMBOLS
from avito.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    RateLimitError,
    UpstreamApiError,
    ValidationError,
)
from avito.core.swagger_discovery import discover_swagger_bindings
from avito.core.swagger_registry import SwaggerOperation, load_swagger_registry
from avito.testing import (
    AsyncSwaggerFakeTransport,
    error_payload,
    generate_schema_value,
    validate_schema_value,
)

_REGISTRY = load_swagger_registry()
_DISCOVERY = discover_swagger_bindings(registry=_REGISTRY)
_BINDINGS = tuple(binding for binding in _DISCOVERY.bindings if binding.variant == "async")
_BINDING_OPERATION_BY_KEY = {operation.key: operation for operation in _REGISTRY.operations}


def _binding_id(binding: object) -> str:
    operation_key = getattr(binding, "operation_key", None)
    sdk_method = getattr(binding, "sdk_method", repr(binding))
    return operation_key or sdk_method


def _expected_exception_type(status_code: int, domain: str) -> type[Exception]:
    if domain == "auth":
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


def _error_status_cases() -> tuple[tuple[SwaggerOperation, object, int, type[Exception]], ...]:
    cases: list[tuple[SwaggerOperation, object, int, type[Exception]]] = []
    binding_by_operation = {binding.operation_key: binding for binding in _BINDINGS}
    for operation in _REGISTRY.operations:
        binding = binding_by_operation[operation.key]
        for response in operation.error_responses:
            if response.status_code.isdigit():
                status_code = int(response.status_code)
                cases.append(
                    (
                        operation,
                        binding,
                        status_code,
                        _expected_exception_type(status_code, binding.domain),
                    )
                )
    return tuple(cases)


def _error_status_id(case: tuple[SwaggerOperation, object, int, type[Exception]]) -> str:
    operation, _binding, status_code, _expected_error = case
    return f"{operation.key} {status_code}"


def test_async_swagger_bindings_are_discoverable_for_ported_domains() -> None:
    assert {binding.class_name for binding in _BINDINGS} == {
        "AsyncAccount",
        "AsyncAccountHierarchy",
        "AsyncAd",
        "AsyncAdPromotion",
        "AsyncAdStats",
        "AsyncAlternateTokenClient",
        "AsyncAutotekaMonitoring",
        "AsyncAutotekaReport",
        "AsyncAutotekaScoring",
        "AsyncAutotekaValuation",
        "AsyncAutotekaVehicle",
        "AsyncAutoloadArchive",
        "AsyncAutoloadProfile",
        "AsyncAutoloadReport",
        "AsyncCallTrackingCall",
        "AsyncChat",
        "AsyncChatMedia",
        "AsyncChatMessage",
        "AsyncChatWebhook",
        "AsyncCpaArchive",
        "AsyncCpaAuction",
        "AsyncCpaCall",
        "AsyncCpaChat",
        "AsyncCpaLead",
        "AsyncDeliveryOrder",
        "AsyncDeliveryTask",
        "AsyncAutostrategyCampaign",
        "AsyncBbipPromotion",
        "AsyncApplication",
        "AsyncJobDictionary",
        "AsyncJobWebhook",
        "AsyncResume",
        "AsyncVacancy",
        "AsyncRatingProfile",
        "AsyncRealtyAnalyticsReport",
        "AsyncRealtyBooking",
        "AsyncRealtyListing",
        "AsyncRealtyPricing",
        "AsyncOrder",
        "AsyncOrderLabel",
        "AsyncReview",
        "AsyncReviewAnswer",
        "AsyncSandboxDelivery",
        "AsyncSpecialOfferCampaign",
        "AsyncStock",
        "AsyncPromotionOrder",
        "AsyncTariff",
        "AsyncTargetActionPricing",
        "AsyncTokenClient",
        "AsyncTrxPromotion",
    }
    assert len(_BINDINGS) == 204


@pytest.mark.asyncio
@pytest.mark.parametrize("binding", _BINDINGS, ids=_binding_id)
async def test_async_swagger_fake_transport_invokes_every_discovered_binding(binding: object) -> None:
    fake = AsyncSwaggerFakeTransport(registry=_REGISTRY)
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
        await fake.invoke_binding(binding)

    assert fake.count() >= 1


@pytest.mark.asyncio
@pytest.mark.parametrize("binding", _BINDINGS, ids=_binding_id)
async def test_async_swagger_fake_transport_request_body_matches_swagger_schema(
    binding: object,
) -> None:
    if binding.operation_key is None:
        pytest.fail(f"{binding.sdk_method}: binding без operation_key")
    operation = _BINDING_OPERATION_BY_KEY[binding.operation_key]
    if (
        operation.request_body is None
        or "application/json" not in operation.request_body.content_types
    ):
        return

    fake = AsyncSwaggerFakeTransport(registry=_REGISTRY)
    fake.add_success_operation(binding.operation_key)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        await fake.invoke_binding(binding)

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


@pytest.mark.asyncio
@pytest.mark.parametrize("binding", _BINDINGS, ids=_binding_id)
async def test_async_swagger_success_response_models_accept_swagger_schema_payload(
    binding: object,
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
    fake = AsyncSwaggerFakeTransport(registry=_REGISTRY)
    fake.add_operation(operation.key, payload, status_code=int(response.status_code))

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        result = await fake.invoke_binding(binding)

    assert not isinstance(result, dict)


def test_async_swagger_error_contract_coverage_matches_numeric_error_responses() -> None:
    cases = _error_status_cases()
    expected_count = sum(
        1
        for operation in _REGISTRY.operations
        for response in operation.error_responses
        if response.status_code.isdigit()
    )

    assert len(cases) == expected_count == 639


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _error_status_cases(), ids=_error_status_id)
async def test_async_swagger_fake_transport_maps_every_declared_error_status(
    case: tuple[SwaggerOperation, object, int, type[Exception]],
) -> None:
    operation, binding, status_code, expected_error = case
    fake = AsyncSwaggerFakeTransport(registry=_REGISTRY)
    fake.add_operation(operation.key, error_payload(status_code), status_code=status_code)

    with pytest.raises(expected_error) as exc_info:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            await fake.invoke_binding(binding)

    assert exc_info.value.args[0] == f"Ошибка {status_code}"
