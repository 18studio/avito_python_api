from __future__ import annotations

import httpx
import pytest

from avito.async_client import AsyncAvitoClient
from avito.auth.settings import AuthSettings
from avito.config import AvitoSettings
from avito.core import ValidationError
from avito.jobs import (
    AsyncApplication,
    AsyncJobDictionary,
    AsyncJobWebhook,
    AsyncResume,
    AsyncVacancy,
)
from avito.jobs.models import (
    ApplicationViewedItem,
    VacancyBillingType,
    VacancyEmployment,
    VacancyExperience,
    VacancySchedule,
)
from avito.testing import AsyncFakeTransport
from avito.testing.fake_transport import RecordedRequest


@pytest.mark.asyncio
async def test_async_application_webhook_and_resume_flows() -> None:
    fake = (
        AsyncFakeTransport()
        .add_json(
            "GET",
            "/job/v1/applications/get_ids",
            {
                "items": [{"id": "app-1", "updatedAt": "2026-04-18T10:00:00+03:00"}],
                "cursor": "app-1",
            },
        )
        .add_json(
            "POST",
            "/job/v1/applications/get_by_ids",
            {
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
        .add_json(
            "GET",
            "/job/v1/applications/get_states",
            {"states": [{"slug": "new", "description": "Новый отклик"}]},
        )
        .add_json("POST", "/job/v1/applications/set_is_viewed", {"ok": True, "status": "viewed"})
        .add_json(
            "POST",
            "/job/v1/applications/apply_actions",
            {"ok": True, "status": "invited"},
        )
        .add_json(
            "GET",
            "/job/v1/applications/webhook",
            {"url": "https://example.com/job", "is_active": True, "version": "v1"},
        )
        .add_json(
            "PUT",
            "/job/v1/applications/webhook",
            {"url": "https://example.com/job", "is_active": True, "version": "v1"},
        )
        .add_json("DELETE", "/job/v1/applications/webhook", {"ok": True})
        .add_json(
            "GET",
            "/job/v1/applications/webhooks",
            [{"url": "https://example.com/job", "is_active": True, "version": "v1"}],
        )
        .add_json(
            "GET",
            "/job/v1/resumes/",
            {
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
        .add_json(
            "GET",
            "/job/v1/resumes/res-1/contacts/",
            {"name": "Петр", "phone": "+79990000000", "email": "petr@example.com"},
        )
        .add_json(
            "GET",
            "/job/v2/resumes/res-1",
            {
                "id": "res-1",
                "title": "Оператор call-центра",
                "fullName": "Петр Петров",
                "address_details": {"location": "Москва"},
                "salary": {"from": 90000},
            },
        )
    )
    transport = fake.build()
    application = AsyncApplication(transport)
    webhook = AsyncJobWebhook(transport)
    resume = AsyncResume(transport, resume_id="res-1")

    assert (await application.get_ids(updated_at_from="2026-04-18")).items[0].id == "app-1"
    assert (await application.get_by_ids(ids=["app-1"])).items[0].applicant_name == "Иван"
    assert (await application.get_states()).items[0].slug == "new"
    assert (
        await application.update(applies=[ApplicationViewedItem(id="app-1", is_viewed=True)])
    ).status == "viewed"
    assert (await application.apply(ids=["app-1"], action="invited")).status == "invited"
    assert (await webhook.get()).url == "https://example.com/job"
    assert (
        await webhook.update(
            url="https://example.com/job",
            secret="cb1e150b-c5bf-4c3e-acd1-20ec88bdb3a1",
            idempotency_key="idem-webhook",
        )
    ).is_active is True
    assert (await webhook.delete(url="https://example.com/job")).success is True
    assert (await webhook.list()).items[0].version == "v1"
    assert (await resume.list(query="оператор")).items[0].candidate_name == "Петр"
    assert (await resume.get_contacts()).phone == "+79990000000"
    assert (await resume.get()).location == "Москва"
    assert (
        fake.last(method="PUT", path="/job/v1/applications/webhook").headers["idempotency-key"]
        == "idem-webhook"
    )
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_vacancy_and_dictionary_flows() -> None:
    def update_auto_renewal(request: RecordedRequest) -> httpx.Response:
        assert request.json_body == {"auto_renewal": True}
        assert request.headers["idempotency-key"] == "idem-auto-renewal"
        return httpx.Response(200, json={"ok": True, "status": "auto-renewal-updated"})

    fake = (
        AsyncFakeTransport()
        .add_json("POST", "/job/v1/vacancies", {"id": 101, "status": "created"}, status_code=201)
        .add_json("PUT", "/job/v1/vacancies/101", {"ok": True, "status": "updated"})
        .add_json(
            "PUT",
            "/job/v1/vacancies/archived/101",
            {"ok": True, "status": "archived"},
        )
        .add_json(
            "POST",
            "/job/v1/vacancies/101/prolongate",
            {"ok": True, "status": "prolongated"},
        )
        .add_json(
            "GET",
            "/job/v2/vacancies",
            {
                "vacancies": [
                    {"id": 101, "uuid": "vac-uuid-1", "title": "Продавец", "status": "active"}
                ],
                "total": 1,
            },
        )
        .add_json(
            "POST",
            "/job/v2/vacancies",
            {"vacancy_uuid": "vac-uuid-1", "status": "created"},
            status_code=202,
        )
        .add_json(
            "POST",
            "/job/v2/vacancies/batch",
            {
                "vacancies": [
                    {"id": 101, "uuid": "vac-uuid-1", "title": "Продавец", "status": "active"}
                ]
            },
        )
        .add_json(
            "POST",
            "/job/v2/vacancies/statuses",
            {"items": [{"id": 101, "uuid": "vac-uuid-1", "status": "active"}]},
        )
        .add_json(
            "POST",
            "/job/v2/vacancies/update/vac-uuid-1",
            {"vacancy_uuid": "vac-uuid-1", "status": "updated"},
            status_code=202,
        )
        .add_json(
            "GET",
            "/job/v2/vacancies/101",
            {
                "id": 101,
                "uuid": "vac-uuid-1",
                "title": "Продавец",
                "status": "active",
                "url": "https://avito.ru/vacancy/101",
            },
        )
        .add("PUT", "/job/v2/vacancies/vac-uuid-1/auto_renewal", update_auto_renewal)
        .add_json("GET", "/job/v2/vacancy/dict", [{"id": "profession", "description": "Профессия"}])
        .add_json(
            "GET",
            "/job/v2/vacancy/dict/profession",
            [{"id": 10106, "name": "IT, интернет, телеком", "deprecated": True}],
        )
    )
    transport = fake.build()
    vacancy = AsyncVacancy(transport, vacancy_id="101")
    dictionary = AsyncJobDictionary(transport, dictionary_id="profession")

    assert (
        await vacancy.create(
            title="Продавец",
            billing_type=VacancyBillingType.PACKAGE,
            description="Описание вакансии",
            business_area=7,
            employment=VacancyEmployment.FULL,
            schedule=VacancySchedule.FIXED,
            experience=VacancyExperience.NO_MATTER,
            version=1,
        )
    ).id == "101"
    assert (
        await vacancy.update(title="Старший продавец", billing_type="package", version=1)
    ).status == "updated"
    assert (await vacancy.delete(employee_id=7)).status == "archived"
    assert (await vacancy.prolongate(billing_type="package")).status == "prolongated"
    assert (await vacancy.list()).items[0].uuid == "vac-uuid-1"
    assert (
        await vacancy.create(title="Вакансия v2", billing_type=VacancyBillingType.PACKAGE)
    ).id == "vac-uuid-1"
    assert (await vacancy.get_by_ids(ids=[101])).items[0].title == "Продавец"
    assert (await vacancy.get_statuses(ids=["vac-uuid-1"])).items[0].status == "active"
    assert (
        await vacancy.update(
            title="Вакансия v2 updated",
            billing_type="package",
            version=2,
            vacancy_uuid="vac-uuid-1",
        )
    ).status == "updated"
    assert (await vacancy.get()).url == "https://avito.ru/vacancy/101"
    assert (
        await vacancy.update_auto_renewal(
            auto_renewal=True,
            vacancy_uuid="vac-uuid-1",
            idempotency_key="idem-auto-renewal",
        )
    ).status == "auto-renewal-updated"
    assert (await dictionary.list()).items[0].id == "profession"
    assert (await dictionary.get()).items[0].deprecated is True
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_application_rejects_invalid_updated_at_before_transport() -> None:
    fake = AsyncFakeTransport()
    transport = fake.build()
    application = AsyncApplication(transport)

    with pytest.raises(ValidationError, match="updated_at_from"):
        await application.get_ids(updated_at_from="18-04-2026")

    assert fake.count() == 0
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_vacancy_rejects_unknown_closed_values_before_transport() -> None:
    fake = AsyncFakeTransport()
    transport = fake.build()
    vacancy = AsyncVacancy(transport)

    with pytest.raises(ValidationError, match="billing_type"):
        await vacancy.create(title="Вакансия", billing_type="unknown")
    with pytest.raises(ValidationError, match="employment"):
        await vacancy.create(
            title="Вакансия",
            billing_type=VacancyBillingType.PACKAGE,
            description="Описание",
            business_area=7,
            employment="unknown",
            schedule=VacancySchedule.FIXED,
            experience=VacancyExperience.NO_MATTER,
            version=1,
        )

    assert fake.count() == 0
    await transport.aclose()


@pytest.mark.asyncio
async def test_async_client_jobs_factories_return_async_domains() -> None:
    client = AsyncFakeTransport().as_client()

    assert isinstance(client.vacancy("101"), AsyncVacancy)
    assert isinstance(client.application(), AsyncApplication)
    assert isinstance(client.resume("res-1"), AsyncResume)
    assert isinstance(client.job_webhook(), AsyncJobWebhook)
    assert isinstance(client.job_dictionary("profession"), AsyncJobDictionary)
    await client.aclose()


def test_async_client_jobs_factories_require_entered_client() -> None:
    client = AsyncAvitoClient(
        AvitoSettings(auth=AuthSettings(client_id="id", client_secret="secret"))
    )

    with pytest.raises(RuntimeError, match="async with"):
        client.vacancy("101")
