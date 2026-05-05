from __future__ import annotations

import json

import httpx

from avito.ratings import RatingProfile, Review, ReviewAnswer
from tests.helpers.transport import make_transport


def test_ratings_flows() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/ratings/v1/answers":
            assert json.loads(request.content.decode()) == {
                "reviewId": 123,
                "message": "Спасибо за отзыв",
            }
            return httpx.Response(200, json={"id": 456, "createdAt": 1713427200})
        if path == "/ratings/v1/answers/456":
            return httpx.Response(200, json={"success": True})
        if path == "/ratings/v1/info":
            return httpx.Response(
                200,
                json={
                    "isEnabled": True,
                    "rating": {"score": 4.7, "reviewsCount": 25, "reviewsWithScoreCount": 20},
                },
            )
        return httpx.Response(
            200,
            json={
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
            },
        )

    transport = make_transport(httpx.MockTransport(handler))
    answer = ReviewAnswer(transport, answer_id="456")
    profile = RatingProfile(transport)
    review = Review(transport)

    assert answer.create(review_id=123, text="Спасибо за отзыв").answer_id == "456"
    assert answer.delete().success is True
    assert profile.get().score == 4.7
    assert review.list(page=2).items[0].text == "Все отлично"


def test_review_list_uses_working_default_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/ratings/v1/reviews"
        assert request.url.params["page"] == "1"
        assert request.url.params["limit"] == "50"
        return httpx.Response(200, json={"reviews": []})

    review = Review(make_transport(httpx.MockTransport(handler)))

    assert review.list().items == []
