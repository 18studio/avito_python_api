from __future__ import annotations

import httpx
import pytest

from avito.core import ValidationError
from avito.jobs import Application, JobDictionary, JobWebhook, Resume, Vacancy
from avito.jobs.models import (
    ApplicationViewedItem,
    VacancyBillingType,
    VacancyEmployment,
    VacancyExperience,
    VacancySchedule,
)
from tests.helpers.transport import make_transport


def test_application_webhook_and_resume_flows() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/job/v1/applications/get_ids":
            return httpx.Response(
                200,
                json={
                    "items": [{"id": "app-1", "updatedAt": "2026-04-18T10:00:00+03:00"}],
                    "cursor": "app-1",
                },
            )
        if path == "/job/v1/applications/get_by_ids":
            return httpx.Response(
                200,
                json={
                    "applies": [
                        {
                            "id": "app-1",
                            "vacancy_id": 101,
                            "state": "new",
                            "is_viewed": False,
                            "applicant": {"name": "Иван"},
                        }
                    ]
                },
            )
        if path == "/job/v1/applications/get_states":
            return httpx.Response(
                200, json={"states": [{"slug": "new", "description": "Новый отклик"}]}
            )
        if path == "/job/v1/applications/set_is_viewed":
            return httpx.Response(200, json={"ok": True, "status": "viewed"})
        if path == "/job/v1/applications/apply_actions":
            return httpx.Response(200, json={"ok": True, "status": "invited"})
        if path == "/job/v1/applications/webhook" and request.method == "GET":
            return httpx.Response(
                200, json={"url": "https://example.com/job", "is_active": True, "version": "v1"}
            )
        if path == "/job/v1/applications/webhook" and request.method == "PUT":
            return httpx.Response(
                200, json={"url": "https://example.com/job", "is_active": True, "version": "v1"}
            )
        if path == "/job/v1/applications/webhook" and request.method == "DELETE":
            return httpx.Response(200, json={"ok": True})
        if path == "/job/v1/applications/webhooks":
            return httpx.Response(
                200, json=[{"url": "https://example.com/job", "is_active": True, "version": "v1"}]
            )
        if path == "/job/v1/resumes/":
            return httpx.Response(
                200,
                json={
                    "meta": {"cursor": "2", "total": 1},
                    "resumes": [
                        {
                            "id": "res-1",
                            "title": "Оператор call-центра",
                            "name": "Петр",
                            "location": "Москва",
                            "salary": 90000,
                        }
                    ],
                },
            )
        if path == "/job/v1/resumes/res-1/contacts/":
            return httpx.Response(
                200, json={"name": "Петр", "phone": "+79990000000", "email": "petr@example.com"}
            )
        return httpx.Response(
            200,
            json={
                "id": "res-1",
                "title": "Оператор call-центра",
                "fullName": "Петр Петров",
                "address_details": {"location": "Москва"},
                "salary": {"from": 90000},
            },
        )

    transport = make_transport(httpx.MockTransport(handler))
    application = Application(transport)
    webhook = JobWebhook(transport)
    resume = Resume(transport, resume_id="res-1")

    assert application.get_ids(updated_at_from="2026-04-18").items[0].id == "app-1"
    assert application.get_by_ids(ids=["app-1"]).items[0].applicant_name == "Иван"
    assert application.get_states().items[0].slug == "new"
    assert (
        application.update(applies=[ApplicationViewedItem(id="app-1", is_viewed=True)]).status
        == "viewed"
    )
    assert application.apply(ids=["app-1"], action="invited").status == "invited"
    assert webhook.get().url == "https://example.com/job"
    assert (
        webhook.update(
            url="https://example.com/job",
            secret="cb1e150b-c5bf-4c3e-acd1-20ec88bdb3a1",
        ).is_active
        is True
    )
    assert webhook.delete(url="https://example.com/job").success is True
    assert webhook.list().items[0].version == "v1"
    assert resume.list(query="оператор").items[0].candidate_name == "Петр"
    assert resume.get_contacts().phone == "+79990000000"
    assert resume.get().location == "Москва"


def test_vacancy_and_dictionary_flows() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/job/v1/vacancies":
            return httpx.Response(201, json={"id": 101, "status": "created"})
        if path == "/job/v1/vacancies/101":
            return httpx.Response(200, json={"ok": True, "status": "updated"})
        if path == "/job/v1/vacancies/archived/101":
            return httpx.Response(200, json={"ok": True, "status": "archived"})
        if path == "/job/v1/vacancies/101/prolongate":
            return httpx.Response(200, json={"ok": True, "status": "prolongated"})
        if path == "/job/v2/vacancies" and request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "vacancies": [
                        {"id": 101, "uuid": "vac-uuid-1", "title": "Продавец", "status": "active"}
                    ],
                    "total": 1,
                },
            )
        if path == "/job/v2/vacancies":
            return httpx.Response(202, json={"vacancy_uuid": "vac-uuid-1", "status": "created"})
        if path == "/job/v2/vacancies/batch":
            return httpx.Response(
                200,
                json={
                    "vacancies": [
                        {"id": 101, "uuid": "vac-uuid-1", "title": "Продавец", "status": "active"}
                    ]
                },
            )
        if path == "/job/v2/vacancies/statuses":
            return httpx.Response(
                200, json={"items": [{"id": 101, "uuid": "vac-uuid-1", "status": "active"}]}
            )
        if path == "/job/v2/vacancies/update/vac-uuid-1":
            return httpx.Response(202, json={"vacancy_uuid": "vac-uuid-1", "status": "updated"})
        if path == "/job/v2/vacancies/101":
            return httpx.Response(
                200,
                json={
                    "id": 101,
                    "uuid": "vac-uuid-1",
                    "title": "Продавец",
                    "status": "active",
                    "url": "https://avito.ru/vacancy/101",
                },
            )
        if path == "/job/v2/vacancies/vac-uuid-1/auto_renewal":
            return httpx.Response(200, json={"ok": True, "status": "auto-renewal-updated"})
        if path == "/job/v2/vacancy/dict":
            return httpx.Response(200, json=[{"id": "profession", "description": "Профессия"}])
        return httpx.Response(
            200, json=[{"id": 10106, "name": "IT, интернет, телеком", "deprecated": True}]
        )

    transport = make_transport(httpx.MockTransport(handler))
    vacancy = Vacancy(transport, vacancy_id="101")
    dictionary = JobDictionary(transport, dictionary_id="profession")

    assert (
        vacancy.create(
            title="Продавец",
            billing_type=VacancyBillingType.PACKAGE,
            description="Описание вакансии",
            business_area=7,
            employment=VacancyEmployment.FULL,
            schedule=VacancySchedule.FIXED,
            experience=VacancyExperience.NO_MATTER,
            version=1,
        ).id
        == "101"
    )
    assert (
        vacancy.update(title="Старший продавец", billing_type="package", version=1).status
        == "updated"
    )
    assert vacancy.delete(employee_id=7).status == "archived"
    assert vacancy.prolongate(billing_type="package").status == "prolongated"
    assert vacancy.list().items[0].uuid == "vac-uuid-1"
    assert (
        vacancy.create(title="Вакансия v2", billing_type=VacancyBillingType.PACKAGE).id
        == "vac-uuid-1"
    )
    assert vacancy.get_by_ids(ids=[101]).items[0].title == "Продавец"
    assert vacancy.get_statuses(ids=["vac-uuid-1"]).items[0].status == "active"
    assert (
        vacancy.update(
            title="Вакансия v2 updated",
            billing_type="package",
            version=2,
            vacancy_uuid="vac-uuid-1",
        ).status
        == "updated"
    )
    assert vacancy.get().url == "https://avito.ru/vacancy/101"
    assert (
        vacancy.update_auto_renewal(auto_renewal=True, vacancy_uuid="vac-uuid-1").status
        == "auto-renewal-updated"
    )
    assert dictionary.list().items[0].id == "profession"
    assert dictionary.get().items[0].deprecated is True


def test_application_rejects_invalid_updated_at_before_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("transport must not be called")

    application = Application(make_transport(httpx.MockTransport(handler)))

    with pytest.raises(ValidationError, match="updated_at_from"):
        application.get_ids(updated_at_from="18-04-2026")


def test_vacancy_rejects_unknown_closed_values_before_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("transport must not be called")

    vacancy = Vacancy(make_transport(httpx.MockTransport(handler)))

    with pytest.raises(ValidationError, match="billing_type"):
        vacancy.create(title="Вакансия", billing_type="unknown")
    with pytest.raises(ValidationError, match="employment"):
        vacancy.create(
            title="Вакансия",
            billing_type=VacancyBillingType.PACKAGE,
            description="Описание",
            business_area=7,
            employment="unknown",
            schedule=VacancySchedule.FIXED,
            experience=VacancyExperience.NO_MATTER,
            version=1,
        )
