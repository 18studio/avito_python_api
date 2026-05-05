"""Operation specs for jobs domain."""

from __future__ import annotations

from avito.core import OperationSpec
from avito.jobs.models import (
    ApplicationActionRequest,
    ApplicationIdsQuery,
    ApplicationIdsRequest,
    ApplicationIdsResult,
    ApplicationsResult,
    ApplicationStatesResult,
    ApplicationViewedRequest,
    JobActionResult,
    JobDictionariesResult,
    JobDictionaryValuesResult,
    JobWebhookInfo,
    JobWebhooksResult,
    JobWebhookUpdateRequest,
    ResumeContactInfo,
    ResumeInfo,
    ResumeSearchQuery,
    ResumesResult,
    VacanciesQuery,
    VacanciesResult,
    VacancyArchiveRequest,
    VacancyAutoRenewalRequest,
    VacancyClassicCreateRequest,
    VacancyClassicUpdateRequest,
    VacancyCreateRequest,
    VacancyIdsRequest,
    VacancyInfo,
    VacancyProlongateRequest,
    VacancyStatusesResult,
    VacancyUpdateRequest,
)

CREATE_VACANCY_CLASSIC = OperationSpec(
    name="jobs.vacancies.create_classic",
    method="POST",
    path="/job/v1/vacancies",
    request_model=VacancyClassicCreateRequest,
    response_model=JobActionResult,
    retry_mode="enabled",
)
CREATE_VACANCY = OperationSpec(
    name="jobs.vacancies.create",
    method="POST",
    path="/job/v2/vacancies",
    request_model=VacancyCreateRequest,
    response_model=JobActionResult,
    retry_mode="enabled",
)
UPDATE_VACANCY_CLASSIC = OperationSpec(
    name="jobs.vacancies.update_classic",
    method="PUT",
    path="/job/v1/vacancies/{vacancy_id}",
    request_model=VacancyClassicUpdateRequest,
    response_model=JobActionResult,
    retry_mode="enabled",
)
UPDATE_VACANCY = OperationSpec(
    name="jobs.vacancies.update",
    method="POST",
    path="/job/v2/vacancies/update/{vacancy_uuid}",
    request_model=VacancyUpdateRequest,
    response_model=JobActionResult,
    retry_mode="enabled",
)
ARCHIVE_VACANCY = OperationSpec(
    name="jobs.vacancies.archive",
    method="PUT",
    path="/job/v1/vacancies/archived/{vacancy_id}",
    request_model=VacancyArchiveRequest,
    response_model=JobActionResult,
    retry_mode="enabled",
)
PROLONGATE_VACANCY = OperationSpec(
    name="jobs.vacancies.prolongate",
    method="POST",
    path="/job/v1/vacancies/{vacancy_id}/prolongate",
    request_model=VacancyProlongateRequest,
    response_model=JobActionResult,
    retry_mode="enabled",
)
LIST_VACANCIES = OperationSpec(
    name="jobs.vacancies.list",
    method="GET",
    path="/job/v2/vacancies",
    query_model=VacanciesQuery,
    response_model=VacanciesResult,
)
GET_VACANCY = OperationSpec(
    name="jobs.vacancies.get_item",
    method="GET",
    path="/job/v2/vacancies/{vacancy_id}",
    query_model=VacanciesQuery,
    response_model=VacancyInfo,
)
GET_VACANCIES_BY_IDS = OperationSpec(
    name="jobs.vacancies.get_by_ids",
    method="POST",
    path="/job/v2/vacancies/batch",
    request_model=VacancyIdsRequest,
    response_model=VacanciesResult,
    retry_mode="enabled",
)
GET_VACANCY_STATUSES = OperationSpec(
    name="jobs.vacancies.get_statuses",
    method="POST",
    path="/job/v2/vacancies/statuses",
    request_model=VacancyIdsRequest,
    response_model=VacancyStatusesResult,
    retry_mode="enabled",
)
UPDATE_VACANCY_AUTO_RENEWAL = OperationSpec(
    name="jobs.vacancies.update_auto_renewal",
    method="PUT",
    path="/job/v2/vacancies/{vacancy_uuid}/auto_renewal",
    request_model=VacancyAutoRenewalRequest,
    response_model=JobActionResult,
    retry_mode="enabled",
)
APPLY_APPLICATION_ACTIONS = OperationSpec(
    name="jobs.applications.apply_actions",
    method="POST",
    path="/job/v1/applications/apply_actions",
    request_model=ApplicationActionRequest,
    response_model=JobActionResult,
    retry_mode="enabled",
)
GET_APPLICATIONS_BY_IDS = OperationSpec(
    name="jobs.applications.get_by_ids",
    method="POST",
    path="/job/v1/applications/get_by_ids",
    request_model=ApplicationIdsRequest,
    response_model=ApplicationsResult,
    retry_mode="enabled",
)
GET_APPLICATION_IDS = OperationSpec(
    name="jobs.applications.get_ids",
    method="GET",
    path="/job/v1/applications/get_ids",
    query_model=ApplicationIdsQuery,
    response_model=ApplicationIdsResult,
)
GET_APPLICATION_STATES = OperationSpec(
    name="jobs.applications.get_states",
    method="GET",
    path="/job/v1/applications/get_states",
    response_model=ApplicationStatesResult,
)
SET_APPLICATIONS_IS_VIEWED = OperationSpec(
    name="jobs.applications.set_is_viewed",
    method="POST",
    path="/job/v1/applications/set_is_viewed",
    request_model=ApplicationViewedRequest,
    response_model=JobActionResult,
    retry_mode="enabled",
)
SEARCH_RESUMES = OperationSpec(
    name="jobs.resumes.search",
    method="GET",
    path="/job/v1/resumes/",
    query_model=ResumeSearchQuery,
    response_model=ResumesResult,
)
GET_RESUME = OperationSpec(
    name="jobs.resumes.get_item",
    method="GET",
    path="/job/v2/resumes/{resume_id}",
    response_model=ResumeInfo,
)
GET_RESUME_CONTACTS = OperationSpec(
    name="jobs.resumes.get_contacts",
    method="GET",
    path="/job/v1/resumes/{resume_id}/contacts/",
    response_model=ResumeContactInfo,
)
GET_JOB_WEBHOOK = OperationSpec(
    name="jobs.webhook.get",
    method="GET",
    path="/job/v1/applications/webhook",
    response_model=JobWebhookInfo,
)
LIST_JOB_WEBHOOKS = OperationSpec(
    name="jobs.webhook.list",
    method="GET",
    path="/job/v1/applications/webhooks",
    response_model=JobWebhooksResult,
)
UPDATE_JOB_WEBHOOK = OperationSpec(
    name="jobs.webhook.put",
    method="PUT",
    path="/job/v1/applications/webhook",
    request_model=JobWebhookUpdateRequest,
    response_model=JobWebhookInfo,
    retry_mode="enabled",
)
DELETE_JOB_WEBHOOK = OperationSpec(
    name="jobs.webhook.delete",
    method="DELETE",
    path="/job/v1/applications/webhook",
    response_model=JobActionResult,
    retry_mode="enabled",
)
LIST_JOB_DICTIONARIES = OperationSpec(
    name="jobs.dictionaries.list_dicts",
    method="GET",
    path="/job/v2/vacancy/dict",
    response_model=JobDictionariesResult,
)
GET_JOB_DICTIONARY = OperationSpec(
    name="jobs.dictionaries.get_dict_by_id",
    method="GET",
    path="/job/v2/vacancy/dict/{dictionary_id}",
    response_model=JobDictionaryValuesResult,
)

__all__ = (
    "APPLY_APPLICATION_ACTIONS",
    "ARCHIVE_VACANCY",
    "CREATE_VACANCY",
    "CREATE_VACANCY_CLASSIC",
    "DELETE_JOB_WEBHOOK",
    "GET_APPLICATIONS_BY_IDS",
    "GET_APPLICATION_IDS",
    "GET_APPLICATION_STATES",
    "GET_JOB_DICTIONARY",
    "GET_JOB_WEBHOOK",
    "GET_RESUME",
    "GET_RESUME_CONTACTS",
    "GET_VACANCIES_BY_IDS",
    "GET_VACANCY",
    "GET_VACANCY_STATUSES",
    "LIST_JOB_DICTIONARIES",
    "LIST_JOB_WEBHOOKS",
    "LIST_VACANCIES",
    "PROLONGATE_VACANCY",
    "SEARCH_RESUMES",
    "SET_APPLICATIONS_IS_VIEWED",
    "UPDATE_JOB_WEBHOOK",
    "UPDATE_VACANCY",
    "UPDATE_VACANCY_AUTO_RENEWAL",
    "UPDATE_VACANCY_CLASSIC",
)
