"""Типизированные модели раздела ratings."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from avito.core import ApiModel, JsonReader, RequestModel


class ReviewStage(str, Enum):
    """Этап обработки отзыва."""

    UNKNOWN = "__unknown__"
    DONE = "done"
    FELL_THROUGH = "fell_through"
    NOT_AGREE = "not_agree"
    NOT_COMMUNICATE = "not_communicate"


class ReviewAnswerStatus(str, Enum):
    """Статус ответа на отзыв."""

    UNKNOWN = "__unknown__"
    MODERATION = "moderation"
    PUBLISHED = "published"
    REJECTED = "rejected"


@dataclass(slots=True, frozen=True)
class ReviewsQuery(RequestModel):
    """Query-параметры списка отзывов."""

    offset: int | None = None
    page: int | None = None
    limit: int | None = None

    def to_params(self) -> dict[str, object]:
        """Сериализует query-параметры списка отзывов."""

        params: dict[str, object] = {}
        if self.offset is not None:
            params["offset"] = self.offset
        if self.page is not None:
            params["page"] = self.page
        if self.offset is None and self.page is not None:
            page_size = self.limit or 50
            params["offset"] = max(self.page - 1, 0) * page_size
        if self.limit is not None:
            params["limit"] = self.limit
        return params


@dataclass(slots=True, frozen=True)
class CreateReviewAnswerRequest(RequestModel):
    """Запрос создания ответа на отзыв."""

    review_id: int
    text: str

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос создания ответа."""

        return {"reviewId": self.review_id, "message": self.text}


@dataclass(slots=True, frozen=True)
class ReviewInfo(ApiModel):
    """Информация об отзыве пользователя."""

    review_id: str | None
    score: int | None
    stage: ReviewStage | None
    text: str | None
    created_at: int | None
    can_answer: bool | None
    used_in_score: bool | None

    @classmethod
    def from_payload(cls, payload: object) -> ReviewInfo:
        """Преобразует JSON-объект отзыва в SDK-модель."""

        data = JsonReader.expect_mapping(payload)
        reader = JsonReader(payload)
        return cls(
            review_id=_optional_str_or_int(data, "id"),
            score=reader.optional_int("score"),
            stage=reader.enum(ReviewStage, "stage", unknown=ReviewStage.UNKNOWN),
            text=reader.optional_str("text"),
            created_at=reader.optional_int("createdAt"),
            can_answer=reader.optional_bool("canAnswer"),
            used_in_score=reader.optional_bool("usedInScore"),
        )


@dataclass(slots=True, frozen=True)
class ReviewsResult(ApiModel):
    """Список отзывов пользователя."""

    items: list[ReviewInfo]
    total: int | None = None

    @classmethod
    def from_payload(cls, payload: object) -> ReviewsResult:
        """Преобразует ответ API со списком отзывов в SDK-модель."""

        reader = JsonReader(payload)
        return cls(
            items=[
                ReviewInfo.from_payload(item)
                for item in reader.list("reviews", "items")
                if isinstance(item, Mapping)
            ],
            total=reader.optional_int("total"),
        )


@dataclass(slots=True, frozen=True)
class ReviewAnswerInfo(ApiModel):
    """Информация об ответе на отзыв."""

    answer_id: str | None = None
    created_at: int | None = None
    success: bool | None = None
    status: ReviewAnswerStatus | None = None

    @classmethod
    def from_payload(cls, payload: object) -> ReviewAnswerInfo:
        """Преобразует ответ API на создание или удаление ответа в SDK-модель."""

        data = JsonReader.expect_mapping(payload)
        reader = JsonReader(payload)
        return cls(
            answer_id=_optional_str_or_int(data, "id"),
            created_at=reader.optional_int("createdAt"),
            success=reader.optional_bool("success"),
            status=reader.enum(
                ReviewAnswerStatus,
                "status",
                unknown=ReviewAnswerStatus.UNKNOWN,
            ),
        )


@dataclass(slots=True, frozen=True)
class RatingProfileInfo(ApiModel):
    """Информация о рейтинговом профиле."""

    is_enabled: bool
    score: float | None = None
    reviews_count: int | None = None
    reviews_with_score_count: int | None = None

    @classmethod
    def from_payload(cls, payload: object) -> RatingProfileInfo:
        """Преобразует ответ API с рейтингом профиля в SDK-модель."""

        reader = JsonReader(payload)
        rating = reader.mapping("rating") or {}
        rating_reader = JsonReader(rating)
        return cls(
            is_enabled=reader.optional_bool("isEnabled") or False,
            score=rating_reader.optional_float("score"),
            reviews_count=rating_reader.optional_int("reviewsCount"),
            reviews_with_score_count=rating_reader.optional_int("reviewsWithScoreCount"),
        )


def _optional_str_or_int(payload: Mapping[str, object], key: str) -> str | None:
    value = payload.get(key)
    if isinstance(value, str):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return None


__all__ = (
    "CreateReviewAnswerRequest",
    "RatingProfileInfo",
    "ReviewAnswerInfo",
    "ReviewAnswerStatus",
    "ReviewInfo",
    "ReviewStage",
    "ReviewsQuery",
    "ReviewsResult",
)
