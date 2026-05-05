from __future__ import annotations

import pytest

from avito.core.swagger_registry import SwaggerSchema
from avito.core.swagger_schema_paths import SwaggerSchemaPathError, resolve_body_path


def test_resolve_body_path_accepts_array_object_leaf() -> None:
    schema = SwaggerSchema(
        kind="object",
        properties={
            "dispatches": SwaggerSchema(
                kind="array",
                items=SwaggerSchema(
                    kind="object",
                    properties={"dispatchId": SwaggerSchema(kind="integer")},
                ),
            ),
        },
    )

    path = resolve_body_path(schema, "dispatches[].dispatchId")

    assert path.leaf_name == "dispatchId"
    assert path.leaf_schema.kind == "integer"


def test_resolve_body_path_accepts_snake_case_aliases() -> None:
    schema = SwaggerSchema(
        kind="object",
        properties={
            "users": SwaggerSchema(
                kind="array",
                items=SwaggerSchema(
                    kind="object",
                    properties={"userId": SwaggerSchema(kind="integer")},
                ),
            ),
        },
    )

    path = resolve_body_path(schema, "users[].user_id")

    assert path.leaf_name == "user_id"
    assert path.leaf_schema.kind == "integer"


def test_resolve_body_path_accepts_literal_field_with_brackets() -> None:
    schema = SwaggerSchema(
        kind="object",
        properties={"uploadfile[]": SwaggerSchema(kind="array")},
    )

    path = resolve_body_path(schema, "uploadfile[]")

    assert path.leaf_name == "uploadfile"
    assert path.leaf_schema.kind == "array"


def test_resolve_body_path_rejects_array_marker_on_object() -> None:
    schema = SwaggerSchema(
        kind="object",
        properties={"schedule": SwaggerSchema(kind="object")},
    )

    with pytest.raises(SwaggerSchemaPathError):
        resolve_body_path(schema, "schedule[].id")
