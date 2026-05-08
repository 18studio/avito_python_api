from __future__ import annotations

import httpx
import pytest

from avito.async_client import AsyncAvitoClient
from avito.auth.settings import AuthSettings
from avito.config import AvitoSettings
from avito.core.exceptions import (
    AuthenticationError,
    RateLimitError,
    TransportError,
    ValidationError,
)
from avito.core.retries import RetryPolicy
from avito.ratings import AsyncRatingProfile, AsyncReview, AsyncReviewAnswer
from avito.testing import AsyncFakeTransport
from avito.testing.fake_transport import RecordedRequest


def _reviews_payload() -> dict[str, object]:
    return {
        "total": 25,
        "reviews": [
            {
                "id": 123,
                "score": 5,
                "stage": "done",
                "text": "Все отлично",
                "createdAt": 1713427200,
                "canAnswer": True,
                "usedInScore": True,
            }
        ],
    }


def _rating_payload() -> dict[str, object]:
    return {
        "isEnabled": True,
        "rating": {"score": 4.7, "reviewsCount": 25, "reviewsWithScoreCount": 20},
    }


@pytest.mark.asyncio
async def test_async_ratings_flows() -> None:
    def create_answer(request: RecordedRequest) -> httpx.Response:
        assert request.json_body == {"reviewId": 123, "message": "Спасибо за отзыв"}
        return httpx.Response(200, json={"id": 456, "createdAt": 1713427200})

    fake = (
        AsyncFakeTransport()
        .add("POST", "/ratings/v1/answers", create_answer)
        .add_json("DELETE", "/ratings/v1/answers/456", {"success": True})
        .add_json("GET", "/ratings/v1/info", _rating_payload())
        .add_json("GET", "/ratings/v1/reviews", _reviews_payload())
    )
    transport = fake.build()

    answer = AsyncReviewAnswer(transport, answer_id="456")
    profile = AsyncRatingProfile(transport)
    review = AsyncReview(transport)

    assert (await answer.create(review_id=123, text="Спасибо за отзыв")).answer_id == "456"
    assert (await answer.delete()).success is True
    assert (await profile.get()).score == 4.7
    assert (await review.list(page=2)).items[0].text == "Все отлично"
    assert fake.last(method="GET", path="/ratings/v1/reviews").params["page"] == "2"
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_review_list_uses_working_default_page() -> None:
    fake = AsyncFakeTransport().add_json("GET", "/ratings/v1/reviews", {"reviews": []})
    transport = fake.build()

    assert (await AsyncReview(transport).list()).items == []
    request = fake.last(method="GET", path="/ratings/v1/reviews")
    assert request.params["page"] == "1"
    assert request.params["limit"] == "50"
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_client_ratings_factories_return_async_domains() -> None:
    fake = (
        AsyncFakeTransport()
        .add_json("GET", "/ratings/v1/reviews", _reviews_payload())
        .add_json("POST", "/ratings/v1/answers", {"id": 456, "createdAt": 1713427200})
        .add_json("GET", "/ratings/v1/info", _rating_payload())
    )
    client = fake.as_client()

    review = client.review()
    answer = client.review_answer()
    profile = client.rating_profile()

    assert isinstance(review, AsyncReview)
    assert isinstance(answer, AsyncReviewAnswer)
    assert isinstance(profile, AsyncRatingProfile)
    assert (await review.list()).total == 25
    assert (await answer.create(review_id=123, text="Спасибо")).answer_id == "456"
    assert (await profile.get()).reviews_count == 25
    await client.aclose()


@pytest.mark.asyncio
async def test_async_review_answer_delete_requires_answer_id() -> None:
    transport = AsyncFakeTransport().build()

    with pytest.raises(ValidationError):
        await AsyncReviewAnswer(transport).delete()

    await transport.aclose()


@pytest.mark.asyncio
async def test_async_ratings_maps_401() -> None:
    fake = AsyncFakeTransport().add_json(
        "GET",
        "/ratings/v1/info",
        {"error": "unauthorized"},
        status_code=401,
    )
    transport = fake.build()

    with pytest.raises(AuthenticationError):
        await AsyncRatingProfile(transport).get()

    await transport.aclose()


@pytest.mark.asyncio
async def test_async_ratings_maps_429() -> None:
    fake = AsyncFakeTransport().add_json(
        "GET",
        "/ratings/v1/info",
        {"error": "rate limit"},
        status_code=429,
    )
    transport = fake.build(retry_policy=RetryPolicy(max_attempts=1))

    with pytest.raises(RateLimitError):
        await AsyncRatingProfile(transport).get()

    await transport.aclose()


@pytest.mark.asyncio
async def test_async_ratings_maps_transport_error() -> None:
    def raise_network_error(request: object) -> httpx.Response:
        raise httpx.NetworkError("connection failed")

    fake = AsyncFakeTransport().add("GET", "/ratings/v1/info", raise_network_error)
    transport = fake.build(retry_policy=RetryPolicy(max_attempts=1))

    with pytest.raises(TransportError):
        await AsyncRatingProfile(transport).get()

    await transport.aclose()


def test_async_client_ratings_factories_require_entered_client() -> None:
    client = AsyncAvitoClient(
        AvitoSettings(auth=AuthSettings(client_id="id", client_secret="secret"))
    )

    with pytest.raises(RuntimeError):
        client.review()
    with pytest.raises(RuntimeError):
        client.review_answer()
    with pytest.raises(RuntimeError):
        client.rating_profile()
