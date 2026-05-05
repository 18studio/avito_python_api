"""Operation specs for ratings domain."""

from __future__ import annotations

from avito.core import OperationSpec
from avito.ratings.models import (
    CreateReviewAnswerRequest,
    RatingProfileInfo,
    ReviewAnswerInfo,
    ReviewsQuery,
    ReviewsResult,
)

CREATE_REVIEW_ANSWER = OperationSpec(
    name="ratings.answers.create",
    method="POST",
    path="/ratings/v1/answers",
    request_model=CreateReviewAnswerRequest,
    response_model=ReviewAnswerInfo,
    retry_mode="enabled",
)
DELETE_REVIEW_ANSWER = OperationSpec(
    name="ratings.answers.delete",
    method="DELETE",
    path="/ratings/v1/answers/{answer_id}",
    response_model=ReviewAnswerInfo,
    retry_mode="enabled",
)
GET_RATINGS_INFO = OperationSpec(
    name="ratings.info.get",
    method="GET",
    path="/ratings/v1/info",
    response_model=RatingProfileInfo,
)
LIST_REVIEWS = OperationSpec(
    name="ratings.reviews.list",
    method="GET",
    path="/ratings/v1/reviews",
    query_model=ReviewsQuery,
    response_model=ReviewsResult,
)

__all__ = (
    "CREATE_REVIEW_ANSWER",
    "DELETE_REVIEW_ANSWER",
    "GET_RATINGS_INFO",
    "LIST_REVIEWS",
)
