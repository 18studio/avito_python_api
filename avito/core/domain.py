"""Базовый доменный объект SDK."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar

from avito.core.exceptions import ValidationError
from avito.core.operations import OperationExecutor, OperationSpec
from avito.core.types import ApiTimeouts, RequestContext, RetryOverride

if TYPE_CHECKING:
    from avito.core.transport import Transport

ResponseT = TypeVar("ResponseT")


@dataclass(slots=True, frozen=True)
class DomainObject:
    """Базовый доменный объект с доступом к transport-слою."""

    transport: Transport

    def _execute(
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
        """Выполняет v2 operation spec через общий executor."""

        return OperationExecutor(self.transport).execute(
            spec,
            path_params=path_params,
            query=query,
            request=request,
            headers=headers,
            idempotency_key=idempotency_key,
            data=data,
            files=files,
            timeout=timeout,
            retry=retry,
        )

    def _resolve_user_id(self, user_id: int | str | None = None) -> int:
        """Возвращает user_id из аргумента, настроек SDK или профиля текущего пользователя."""

        if user_id is not None:
            return int(user_id)

        configured_user_id = self.transport.debug_info().user_id
        if configured_user_id is not None:
            return configured_user_id

        payload = self.transport.request_json(
            "GET",
            "/core/v1/accounts/self",
            context=RequestContext("accounts.resolve_user_id"),
        )
        resolved_user_id = _extract_user_id(payload)
        if resolved_user_id is None:
            raise ValidationError(
                "Для операции требуется `user_id`: передайте его в фабрику клиента, "
                "в метод операции или задайте `AVITO_USER_ID`."
            )
        return resolved_user_id


def _extract_user_id(payload: object) -> int | None:
    if not isinstance(payload, dict):
        return None
    for key in ("id", "user_id", "userId"):
        value = payload.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
    return None


__all__ = ("DomainObject",)
