from __future__ import annotations

from dataclasses import dataclass

import pytest

from avito.core import DomainObject, ValidationError
from avito.testing import FakeTransport


@dataclass(slots=True, frozen=True)
class ExampleDomain(DomainObject):
    """Concrete domain object for core domain tests."""


def test_resolve_user_id_prefers_explicit_value() -> None:
    transport = FakeTransport().build(user_id=20)
    domain = ExampleDomain(transport)

    assert domain._resolve_user_id("10") == 10


def test_resolve_user_id_uses_configured_user_id() -> None:
    transport = FakeTransport().build(user_id=20)
    domain = ExampleDomain(transport)

    assert domain._resolve_user_id() == 20


def test_resolve_user_id_falls_back_to_profile_without_legacy_account_client() -> None:
    fake_transport = FakeTransport()
    fake_transport.add_json("GET", "/core/v1/accounts/self", {"id": 30})
    domain = ExampleDomain(fake_transport.build())

    assert domain._resolve_user_id() == 30
    assert fake_transport.count(method="GET", path="/core/v1/accounts/self") == 1


def test_resolve_user_id_rejects_profile_without_user_id() -> None:
    fake_transport = FakeTransport()
    fake_transport.add_json("GET", "/core/v1/accounts/self", {"name": "test"})
    domain = ExampleDomain(fake_transport.build())

    with pytest.raises(ValidationError, match="user_id"):
        domain._resolve_user_id()
