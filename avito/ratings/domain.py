"""Доменные объекты пакета ratings."""

from __future__ import annotations

from dataclasses import dataclass

from avito.core import ApiTimeouts, RetryOverride, ValidationError
from avito.core.domain import DomainObject
from avito.core.swagger import swagger_operation
from avito.ratings.models import (
    CreateReviewAnswerRequest,
    RatingProfileInfo,
    ReviewAnswerInfo,
    ReviewsQuery,
    ReviewsResult,
)
from avito.ratings.operations import (
    CREATE_REVIEW_ANSWER,
    DELETE_REVIEW_ANSWER,
    GET_RATINGS_INFO,
    LIST_REVIEWS,
)


@dataclass(slots=True, frozen=True)
class Review(DomainObject):
    """Доменный объект отзывов."""

    __swagger_domain__ = "ratings"
    __sdk_factory__ = "review"

    user_id: int | str | None = None

    @swagger_operation(
        "GET",
        "/ratings/v1/reviews",
        spec="Рейтингииотзывы.json",
        operation_id="getReviewsV1",
    )
    def list(
        self,
        *,
        offset: int | None = None,
        page: int | None = None,
        limit: int | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> ReviewsResult:
        """Возвращает список отзывов.

        Аргументы:
            offset: задает смещение первой записи в выборке.
            page: задает номер страницы для постраничной выборки.
            limit: ограничивает размер возвращаемой выборки.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `ReviewsResult` с типизированными данными ответа API.

        Поведение:
            Параметры пагинации ограничивают объем данных без изменения модели ответа.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        resolved_query = ReviewsQuery(
            offset=offset if offset is not None else 0,
            page=page if page is not None else 1,
            limit=limit if limit is not None else 50,
        )
        return self._execute(LIST_REVIEWS, query=resolved_query, timeout=timeout, retry=retry)


@dataclass(slots=True, frozen=True)
class ReviewAnswer(DomainObject):
    """Доменный объект ответов на отзывы."""

    __swagger_domain__ = "ratings"
    __sdk_factory__ = "review_answer"
    __sdk_factory_args__ = {"answer_id": "path.answer_id"}

    answer_id: int | str | None = None
    user_id: int | str | None = None

    @swagger_operation(
        "POST",
        "/ratings/v1/answers",
        spec="Рейтингииотзывы.json",
        operation_id="createReviewAnswerV1",
        method_args={"review_id": "body.review_id", "text": "body.message"},
    )
    def create(
        self,
        *,
        review_id: int,
        text: str,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> ReviewAnswerInfo:
        """Создает ответ на отзыв.

        Аргументы:
            review_id: идентифицирует отзыв.
            text: передает текст ответа или сообщения.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `ReviewAnswerInfo` с типизированными данными ответа API.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return self._execute(
            CREATE_REVIEW_ANSWER,
            request=CreateReviewAnswerRequest(review_id=review_id, text=text),
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    @swagger_operation(
        "DELETE",
        "/ratings/v1/answers/{answer_id}",
        spec="Рейтингииотзывы.json",
        operation_id="removeReviewAnswerV1",
    )
    def delete(
        self,
        *,
        answer_id: int | str | None = None,
        idempotency_key: str | None = None,
        timeout: ApiTimeouts | None = None,
        retry: RetryOverride | None = None,
    ) -> ReviewAnswerInfo:
        """Удаляет ответ на отзыв.

        Аргументы:
            answer_id: идентифицирует ответ на отзыв.
            idempotency_key: задает ключ идемпотентности для безопасного повтора write-операции.
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `ReviewAnswerInfo` с типизированными данными ответа API.

        Поведение:
            `idempotency_key` следует передавать для write-операций, которые могут безопасно повторяться.
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return self._execute(
            DELETE_REVIEW_ANSWER,
            path_params={"answer_id": answer_id or self._require_answer_id()},
            idempotency_key=idempotency_key,
            timeout=timeout,
            retry=retry,
        )

    def _require_answer_id(self) -> str:
        if self.answer_id is None:
            raise ValidationError("Для операции требуется `answer_id`.")
        return str(self.answer_id)


@dataclass(slots=True, frozen=True)
class RatingProfile(DomainObject):
    """Доменный объект рейтингового профиля."""

    __swagger_domain__ = "ratings"
    __sdk_factory__ = "rating_profile"

    user_id: int | str | None = None

    @swagger_operation(
        "GET",
        "/ratings/v1/info",
        spec="Рейтингииотзывы.json",
        operation_id="getRatingsInfoV1",
    )
    def get(
        self, *, timeout: ApiTimeouts | None = None, retry: RetryOverride | None = None
    ) -> RatingProfileInfo:
        """Возвращает рейтинга профиля.

        Аргументы:
            timeout: переопределяет таймауты HTTP-запроса для этого вызова.
            retry: переопределяет retry-политику операции: default, enabled или disabled.

        Возвращает:
            `RatingProfileInfo` с типизированными данными ответа API.

        Поведение:
            `timeout` и `retry` действуют только на этот вызов и не меняют настройки клиента.

        Исключения:
            AvitoError: ошибка SDK с контекстом operation, status, request_id, attempt, method и endpoint.
        """

        return self._execute(GET_RATINGS_INFO, timeout=timeout, retry=retry)


__all__ = ("RatingProfile", "Review", "ReviewAnswer")
