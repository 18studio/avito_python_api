"""Tests for Swagger binding linter rules."""

from __future__ import annotations

from avito.core.operations import OperationSpec
from avito.core.swagger_discovery import DiscoveredSwaggerBinding
from avito.core.swagger_linter import _validate_operation_json_body_models
from avito.core.swagger_registry import (
    SwaggerOperation,
    SwaggerRequestBody,
    SwaggerResponse,
    SwaggerSchema,
)


def test_validate_operation_json_body_models_requires_declared_models() -> None:
    schema = SwaggerSchema(kind="object")
    binding = DiscoveredSwaggerBinding(
        module="avito.accounts.domain",
        class_name="Account",
        method_name="example",
        domain="accounts",
        operation_key="Spec.json POST /example",
        spec="Spec.json",
        method="POST",
        path="/example",
        operation_id="example",
        factory="account",
    )
    operation = SwaggerOperation(
        spec="Spec.json",
        method="POST",
        path="/example",
        operation_id="example",
        deprecated=False,
        parameters=(),
        request_body=SwaggerRequestBody(
            required=True,
            content_types=("application/json",),
            field_names=(),
            schema_extracted=True,
            schema=schema,
        ),
        responses=(
            SwaggerResponse(
                status_code="200",
                content_types=("application/json",),
                schema=schema,
            ),
            SwaggerResponse(
                status_code="400",
                content_types=("application/json",),
                schema=schema,
            ),
        ),
    )
    spec = OperationSpec[object](
        name="EXAMPLE",
        method="POST",
        path="/example",
        error_models={},
    )

    errors = _validate_operation_json_body_models(
        binding=binding,
        operation=operation,
        spec=spec,
    )

    assert {error.code for error in errors} == {
        "SWAGGER_CONTRACT_REQUEST_MODEL_MISSING",
        "SWAGGER_CONTRACT_RESPONSE_MODEL_MISSING",
        "SWAGGER_CONTRACT_ERROR_MODEL_MISSING",
    }
