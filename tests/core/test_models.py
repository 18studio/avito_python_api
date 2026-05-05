from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum

from avito.core import RequestModel, api_field


class ExampleMode(StrEnum):
    ACTIVE = "active"


@dataclass(slots=True, frozen=True)
class NestedRequest(RequestModel):
    city_id: int = api_field("cityId")


@dataclass(slots=True, frozen=True)
class ExampleRequest(RequestModel):
    item_id: int = api_field("itemId")
    created_at: datetime = api_field("createdAt")
    day: date = api_field("day")
    mode: ExampleMode = ExampleMode.ACTIVE
    nested: NestedRequest = field(default_factory=lambda: NestedRequest(city_id=1))
    tags: list[ExampleMode | None] = field(default_factory=lambda: [ExampleMode.ACTIVE, None])
    skipped: str | None = None
    raw_payload: dict[str, object] | None = None


def test_request_model_to_payload_uses_api_field_names_and_serializes_values() -> None:
    request = ExampleRequest(
        item_id=42,
        created_at=datetime(2026, 4, 30, 12, 15),
        day=date(2026, 4, 30),
        raw_payload={"secret": True},
    )

    assert request.to_payload() == {
        "itemId": 42,
        "mode": "active",
        "createdAt": "2026-04-30T12:15:00",
        "day": "2026-04-30",
        "nested": {"cityId": 1},
        "tags": ["active"],
    }


def test_request_model_to_params_matches_payload_contract() -> None:
    request = NestedRequest(city_id=10)

    assert request.to_params() == {"cityId": 10}
