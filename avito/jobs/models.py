"""Типизированные модели раздела jobs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from avito.core import ApiModel, RequestModel
from avito.core.exceptions import ResponseMappingError, ValidationError

Payload = Mapping[str, object]


class JobActionStatus(str, Enum):
    """Статус мутационной операции jobs."""

    UNKNOWN = "__unknown__"
    VIEWED = "viewed"
    INVITED = "invited"
    CREATED = "created"
    UPDATED = "updated"
    ARCHIVED = "archived"
    PROLONGATED = "prolongated"
    AUTO_RENEWAL_UPDATED = "auto-renewal-updated"


class ApplicationStatus(str, Enum):
    """Статус отклика."""

    UNKNOWN = "__unknown__"
    NEW = "new"


class VacancyStatus(str, Enum):
    """Статус вакансии."""

    UNKNOWN = "__unknown__"
    ACTIVE = "active"
    CREATED = "created"
    UPDATED = "updated"
    ACTIVATED = "activated"
    ARCHIVED = "archived"
    BLOCKED = "blocked"
    CLOSED = "closed"
    EXPIRED = "expired"
    REJECTED = "rejected"
    UNBLOCKED = "unblocked"


class VacancyModerationStatus(str, Enum):
    """Статус модерации вакансии."""

    UNKNOWN = "__unknown__"
    IN_PROGRESS = "in_progress"
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    REJECTED = "rejected"


class JobEnrichmentStatus(str, Enum):
    """Статус обогащения параметров вакансии."""

    UNKNOWN = "__unknown__"
    IN_PROGRESS = "in_progress"
    NOT_COMPLETED = "not_completed"
    COMPLETED_NO_CRITERIA = "completed_no_criteria"
    COMPLETED_MATCHED = "completed_matched"
    COMPLETED_MISMATCHED = "completed_mismatched"


class JobMatchingStatus(str, Enum):
    """Статус сопоставления критерия вакансии."""

    UNKNOWN = "__unknown__"
    NO_CRITERIA = "no_criteria"
    MATCHED = "matched"
    MISMATCHED = "mismatched"


class VacancyBillingType(str, Enum):
    """Вариант платного размещения вакансии."""

    PACKAGE = "package"
    SINGLE = "single"
    PACKAGE_OR_SINGLE = "packageOrSingle"


class VacancyEmployment(str, Enum):
    """Тип занятости вакансии."""

    TEMPORARY = "temporary"
    FULL = "full"
    INTERNSHIP = "internship"
    PARTIAL = "partial"


class VacancySchedule(str, Enum):
    """Режим работы вакансии."""

    FLY_IN_FLY_OUT = "flyInFlyOut"
    FIXED = "fixed"
    FLEXIBLE = "flexible"
    SHIFT = "shift"


class VacancyExperience(str, Enum):
    """Требуемый опыт работы для вакансии."""

    NO_MATTER = "noMatter"
    MORE_THAN_1 = "moreThan1"
    MORE_THAN_3 = "moreThan3"
    MORE_THAN_5 = "moreThan5"
    MORE_THAN_10 = "moreThan10"


VacancyBillingTypeInput = VacancyBillingType | str
VacancyEmploymentInput = VacancyEmployment | str
VacancyScheduleInput = VacancySchedule | str
VacancyExperienceInput = VacancyExperience | str


@dataclass(slots=True, frozen=True)
class ApplicationIdsQuery(RequestModel):
    """Query списка идентификаторов откликов."""

    updated_at_from: str

    def to_params(self) -> dict[str, object]:
        """Сериализует query-параметры идентификаторов откликов."""

        return {"updatedAtFrom": self.updated_at_from}


@dataclass(slots=True, frozen=True)
class ApplicationIdsRequest(RequestModel):
    """Запрос получения откликов по идентификаторам."""

    ids: list[str]

    def to_payload(self) -> dict[str, object]:
        """Сериализует идентификаторы откликов."""

        return {"ids": list(self.ids)}


@dataclass(slots=True, frozen=True)
class ApplicationActionRequest(RequestModel):
    """Запрос действия над откликами."""

    ids: list[str]
    action: str

    def to_payload(self) -> dict[str, object]:
        """Сериализует действие над откликами."""

        return {"ids": list(self.ids), "action": self.action}


@dataclass(slots=True, frozen=True)
class ApplicationViewedItem(ApiModel):
    """Флаг просмотра для отклика."""

    id: str
    is_viewed: bool

    def to_payload(self) -> dict[str, object]:
        """Сериализует флаг просмотра отклика."""

        return {"id": self.id, "is_viewed": self.is_viewed}

    @classmethod
    def from_payload(cls, payload: object) -> ApplicationViewedItem:
        """Преобразует флаг просмотра отклика."""

        data = _expect_mapping(payload)
        return cls(id=str(data.get("id", "")), is_viewed=bool(data.get("is_viewed")))


@dataclass(slots=True, frozen=True)
class ApplicationViewedRequestItem(RequestModel):
    """Внутренний элемент запроса обновления флага просмотра."""

    id: str
    is_viewed: bool

    def to_payload(self) -> dict[str, object]:
        """Сериализует флаг просмотра отклика."""

        return {"id": self.id, "is_viewed": self.is_viewed}


@dataclass(slots=True, frozen=True)
class ApplicationViewedRequest(RequestModel):
    """Запрос обновления флага просмотра откликов."""

    applies: list[ApplicationViewedRequestItem]

    def to_payload(self) -> dict[str, object]:
        """Сериализует запрос обновления просмотра откликов."""

        return {"applies": [item.to_payload() for item in self.applies]}


@dataclass(slots=True, frozen=True)
class JobWebhookUpdateRequest(RequestModel):
    """Запрос обновления webhook откликов."""

    url: str
    secret: str

    def to_payload(self) -> dict[str, object]:
        """Сериализует webhook откликов."""

        return {"url": self.url, "secret": self.secret}


@dataclass(slots=True, frozen=True)
class ResumeSearchQuery(RequestModel):
    """Query поиска резюме."""

    query: str

    def to_params(self) -> dict[str, object]:
        """Сериализует query поиска резюме."""

        return {"query": self.query}


@dataclass(slots=True, frozen=True)
class VacanciesQuery(RequestModel):
    """Query списка или карточки вакансий."""

    query: str | None = None

    def to_params(self) -> dict[str, object]:
        """Сериализует query вакансий."""

        params: dict[str, object] = {}
        if self.query is not None:
            params["query"] = self.query
        return params


@dataclass(slots=True, frozen=True)
class VacancyCreateRequest(RequestModel):
    """Запрос создания вакансии v2."""

    title: str
    billing_type: VacancyBillingTypeInput

    def to_payload(self) -> dict[str, object]:
        """Сериализует создание вакансии."""

        return {
            "title": self.title,
            "billing_type": _enum_value(VacancyBillingType, "billing_type", self.billing_type),
        }


@dataclass(slots=True, frozen=True)
class VacancyClassicCreateRequest(RequestModel):
    """Запрос создания вакансии v1."""

    title: str
    description: str
    billing_type: VacancyBillingTypeInput
    business_area: int
    employment: VacancyEmploymentInput
    schedule: VacancyScheduleInput
    experience: VacancyExperienceInput

    def to_payload(self) -> dict[str, object]:
        """Сериализует создание вакансии v1."""

        return {
            "name": self.title,
            "description": self.description,
            "billing_type": _enum_value(VacancyBillingType, "billing_type", self.billing_type),
            "business_area": self.business_area,
            "employment": _enum_value(VacancyEmployment, "employment", self.employment),
            "schedule": {"id": _enum_value(VacancySchedule, "schedule", self.schedule)},
            "experience": {"id": _enum_value(VacancyExperience, "experience", self.experience)},
        }


@dataclass(slots=True, frozen=True)
class VacancyUpdateRequest(RequestModel):
    """Запрос обновления вакансии."""

    title: str
    billing_type: VacancyBillingTypeInput

    def to_payload(self) -> dict[str, object]:
        """Сериализует обновление вакансии."""

        return {
            "title": self.title,
            "billing_type": _enum_value(VacancyBillingType, "billing_type", self.billing_type),
        }


@dataclass(slots=True, frozen=True)
class VacancyClassicUpdateRequest(RequestModel):
    """Запрос обновления вакансии v1."""

    title: str
    billing_type: VacancyBillingTypeInput

    def to_payload(self) -> dict[str, object]:
        """Сериализует обновление вакансии v1."""

        return {
            "name": self.title,
            "billing_type": _enum_value(VacancyBillingType, "billing_type", self.billing_type),
        }


@dataclass(slots=True, frozen=True)
class VacancyArchiveRequest(RequestModel):
    """Запрос архивации вакансии v1."""

    employee_id: int

    def to_payload(self) -> dict[str, object]:
        """Сериализует архивацию вакансии."""

        return {"employee_id": self.employee_id}


@dataclass(slots=True, frozen=True)
class VacancyProlongateRequest(RequestModel):
    """Запрос продления вакансии v1."""

    billing_type: VacancyBillingTypeInput

    def to_payload(self) -> dict[str, object]:
        """Сериализует продление вакансии."""

        return {"billing_type": _enum_value(VacancyBillingType, "billing_type", self.billing_type)}


@dataclass(slots=True, frozen=True)
class VacancyIdsRequest(RequestModel):
    """Запрос списка вакансий по идентификаторам."""

    ids: list[int | str]

    def to_payload(self) -> dict[str, object]:
        """Сериализует идентификаторы вакансий."""

        return {"ids": list(self.ids)}


@dataclass(slots=True, frozen=True)
class VacancyAutoRenewalRequest(RequestModel):
    """Запрос обновления автообновления вакансии."""

    auto_renewal: bool

    def to_payload(self) -> dict[str, object]:
        """Сериализует флаг автообновления."""

        return {"auto_renewal": self.auto_renewal}


@dataclass(slots=True, frozen=True)
class JobActionResult(ApiModel):
    """Результат mutation-операции Jobs API."""

    success: bool
    id: str | None = None
    status: JobActionStatus | None = None
    message: str | None = None

    @classmethod
    def from_payload(cls, payload: object) -> JobActionResult:
        """Преобразует результат mutation-операции Jobs API."""

        data = _expect_mapping(payload)
        result = _mapping(data, "result")
        source = result or data
        identifier = _str(source, "id", "uuid", "vacancy_uuid", "vacancyUuid", "apply_id")
        numeric_id = _int(source, "id", "vacancy_id", "vacancyId")
        return cls(
            success=bool(source.get("ok", source.get("success", True))),
            id=identifier or (str(numeric_id) if numeric_id is not None else None),
            status=_enum(JobActionStatus, _str(source, "status", "state")),
            message=_str(source, "message"),
        )


@dataclass(slots=True, frozen=True)
class ApplicationInfo(ApiModel):
    """Информация об отклике."""

    id: str | None
    vacancy_id: int | None
    resume_id: str | None
    state: ApplicationStatus | None
    is_viewed: bool | None
    applicant_name: str | None

    @classmethod
    def from_payload(cls, payload: object) -> ApplicationInfo:
        data = _expect_mapping(payload)
        return cls(
            id=_str(data, "id"),
            vacancy_id=_int(data, "vacancy_id", "vacancyId"),
            resume_id=_str(data, "resume_id", "resumeId"),
            state=_enum(ApplicationStatus, _str(data, "state", "status")),
            is_viewed=_bool(data, "is_viewed", "isViewed"),
            applicant_name=_str(_mapping(data, "applicant"), "name", "fullName"),
        )


@dataclass(slots=True, frozen=True)
class ApplicationsResult(ApiModel):
    """Список откликов."""

    items: list[ApplicationInfo]

    @classmethod
    def from_payload(cls, payload: object) -> ApplicationsResult:
        data = _expect_mapping(payload)
        return cls(
            items=[
                ApplicationInfo.from_payload(item)
                for item in _list(data, "applies", "applications", "items", "result")
            ],
        )


@dataclass(slots=True, frozen=True)
class ApplicationIdItem(ApiModel):
    """Идентификатор отклика."""

    id: str | None
    updated_at: str | None


@dataclass(slots=True, frozen=True)
class ApplicationIdsResult(ApiModel):
    """Постраничный список идентификаторов откликов."""

    items: list[ApplicationIdItem]
    cursor: str | None = None

    @classmethod
    def from_payload(cls, payload: object) -> ApplicationIdsResult:
        data = _expect_mapping(payload)
        return cls(
            items=[
                ApplicationIdItem(
                    id=_str(item, "id"), updated_at=_str(item, "updatedAt", "updated_at")
                )
                for item in _list(data, "items", "applies", "result")
            ],
            cursor=_str(_mapping(data, "meta"), "cursor") or _str(data, "cursor"),
        )


@dataclass(slots=True, frozen=True)
class ApplicationState(ApiModel):
    """Статус отклика."""

    slug: str | None
    description: str | None


@dataclass(slots=True, frozen=True)
class ApplicationStatesResult(ApiModel):
    """Список возможных статусов откликов."""

    items: list[ApplicationState]

    @classmethod
    def from_payload(cls, payload: object) -> ApplicationStatesResult:
        data = _expect_mapping(payload)
        return cls(
            items=[
                ApplicationState(
                    slug=_str(item, "slug", "id"),
                    description=_str(item, "description", "name"),
                )
                for item in _list(data, "states", "items", "result")
            ],
        )


@dataclass(slots=True, frozen=True)
class ResumeInfo(ApiModel):
    """Краткая или полная информация о резюме."""

    id: str | None
    title: str | None
    candidate_name: str | None
    location: str | None
    salary: int | None

    @classmethod
    def from_payload(cls, payload: object) -> ResumeInfo:
        data = _expect_mapping(payload)
        salary_payload = _mapping(data, "salary")
        return cls(
            id=_str(data, "id", "resume_id", "resumeId"),
            title=_str(data, "title"),
            candidate_name=_str(data, "name", "full_name", "fullName"),
            location=_str(data, "location") or _str(_mapping(data, "address_details"), "location"),
            salary=_int(data, "salary") or _int(salary_payload, "value", "from"),
        )


@dataclass(slots=True, frozen=True)
class ResumesResult(ApiModel):
    """Результат поиска резюме."""

    items: list[ResumeInfo]
    cursor: str | None = None
    total: int | None = None

    @classmethod
    def from_payload(cls, payload: object) -> ResumesResult:
        data = _expect_mapping(payload)
        meta = _mapping(data, "meta")
        return cls(
            items=[
                ResumeInfo.from_payload(item) for item in _list(data, "resumes", "items", "result")
            ],
            cursor=_str(meta, "cursor"),
            total=_int(meta, "total"),
        )


@dataclass(slots=True, frozen=True)
class ResumeContactInfo(ApiModel):
    """Контакты соискателя."""

    name: str | None
    phone: str | None
    email: str | None

    @classmethod
    def from_payload(cls, payload: object) -> ResumeContactInfo:
        data = _expect_mapping(payload)
        return cls(
            name=_str(data, "name", "fullName"),
            phone=_str(data, "phone", "phoneNumber"),
            email=_str(data, "email"),
        )


@dataclass(slots=True, frozen=True)
class VacancyInfo(ApiModel):
    """Информация о вакансии."""

    id: str | None
    uuid: str | None
    title: str | None
    status: VacancyStatus | None
    url: str | None

    @classmethod
    def from_payload(cls, payload: object) -> VacancyInfo:
        data = _expect_mapping(payload)
        numeric_id = _int(data, "id", "vacancy_id", "vacancyId")
        return cls(
            id=_str(data, "id", "vacancy_id", "vacancyId")
            or (str(numeric_id) if numeric_id is not None else None),
            uuid=_str(data, "uuid", "vacancy_uuid", "vacancyUuid"),
            title=_str(data, "title", "name"),
            status=_enum(VacancyStatus, _str(data, "status", "state")),
            url=_str(data, "url"),
        )


@dataclass(slots=True, frozen=True)
class VacanciesResult(ApiModel):
    """Список вакансий."""

    items: list[VacancyInfo]
    total: int | None = None

    @classmethod
    def from_payload(cls, payload: object) -> VacanciesResult:
        items = _expect_list(payload) if isinstance(payload, list) else []
        data = {} if isinstance(payload, list) else _expect_mapping(payload)
        if not items:
            items = _list(data, "vacancies", "items", "result")
        meta = _mapping(data, "meta")
        return cls(
            items=[VacancyInfo.from_payload(item) for item in items],
            total=_int(meta, "total") or _int(data, "total"),
        )


@dataclass(slots=True, frozen=True)
class VacancyStatusInfo(ApiModel):
    """Статус публикации вакансии v2."""

    id: str | None
    uuid: str | None
    status: VacancyStatus | None
    moderation_status: VacancyModerationStatus | None = None


@dataclass(slots=True, frozen=True)
class VacancyStatusesResult(ApiModel):
    """Список статусов вакансий."""

    items: list[VacancyStatusInfo]

    @classmethod
    def from_payload(cls, payload: object) -> VacancyStatusesResult:
        if isinstance(payload, list):
            raw_items = _expect_list(payload)
        else:
            data = _expect_mapping(payload)
            raw_items = _list(data, "items", "statuses", "vacancies", "result")
        items: list[VacancyStatusInfo] = []
        for item in raw_items:
            vacancy = _mapping(item, "vacancy") or item
            numeric_id = _int(vacancy, "id", "vacancy_id")
            items.append(
                VacancyStatusInfo(
                    id=_str(vacancy, "id", "vacancy_id")
                    or (str(numeric_id) if numeric_id is not None else None),
                    uuid=_str(vacancy, "uuid", "vacancy_uuid"),
                    status=_enum(VacancyStatus, _str(vacancy, "status", "state")),
                    moderation_status=_enum(
                        VacancyModerationStatus,
                        _str(vacancy, "moderation_status", "moderationStatus"),
                    ),
                )
            )
        return cls(items=items)


@dataclass(slots=True, frozen=True)
class JobWebhookInfo(ApiModel):
    """Подписка webhook раздела Работа."""

    url: str | None
    is_active: bool | None
    version: str | None

    @classmethod
    def from_payload(cls, payload: object) -> JobWebhookInfo:
        data = _expect_mapping(payload)
        return cls(
            url=_str(data, "url"),
            is_active=_bool(data, "is_active", "isActive", "active"),
            version=_str(data, "version"),
        )


@dataclass(slots=True, frozen=True)
class JobWebhooksResult(ApiModel):
    """Список webhook-подписок."""

    items: list[JobWebhookInfo]

    @classmethod
    def from_payload(cls, payload: object) -> JobWebhooksResult:
        if isinstance(payload, list):
            return cls(items=[JobWebhookInfo.from_payload(item) for item in _expect_list(payload)])
        data = _expect_mapping(payload)
        return cls(
            items=[
                JobWebhookInfo.from_payload(item)
                for item in _list(data, "items", "webhooks", "result")
            ],
        )


@dataclass(slots=True, frozen=True)
class JobDictionaryInfo(ApiModel):
    """Справочник вакансий."""

    id: str | None
    description: str | None


@dataclass(slots=True, frozen=True)
class JobDictionariesResult(ApiModel):
    """Список доступных словарей."""

    items: list[JobDictionaryInfo]

    @classmethod
    def from_payload(cls, payload: object) -> JobDictionariesResult:
        items_payload = (
            _expect_list(payload)
            if isinstance(payload, list)
            else _list(_expect_mapping(payload), "items", "result")
        )
        return cls(
            items=[
                JobDictionaryInfo(id=_str(item, "id"), description=_str(item, "description"))
                for item in items_payload
            ],
        )


@dataclass(slots=True, frozen=True)
class JobDictionaryValue(ApiModel):
    """Значение словаря вакансий."""

    id: int | str | None
    name: str | None
    deprecated: bool | None


@dataclass(slots=True, frozen=True)
class JobDictionaryValuesResult(ApiModel):
    """Список значений словаря."""

    items: list[JobDictionaryValue]

    @classmethod
    def from_payload(cls, payload: object) -> JobDictionaryValuesResult:
        items_payload = (
            _expect_list(payload)
            if isinstance(payload, list)
            else _list(_expect_mapping(payload), "items", "result")
        )
        return cls(
            items=[
                JobDictionaryValue(
                    id=_int(item, "id") if _int(item, "id") is not None else _str(item, "id"),
                    name=_str(item, "name", "description"),
                    deprecated=_bool(item, "deprecated"),
                )
                for item in items_payload
            ],
        )


def _expect_mapping(payload: object) -> Payload:
    if not isinstance(payload, Mapping):
        raise ResponseMappingError("Ожидался JSON-объект.", payload=payload)
    return payload


def _expect_list(payload: object) -> list[Payload]:
    if not isinstance(payload, list):
        raise ResponseMappingError("Ожидался JSON-массив.", payload=payload)
    return [item for item in payload if isinstance(item, Mapping)]


def _list(payload: Payload, *keys: str) -> list[Payload]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, Mapping)]
    return []


def _mapping(payload: Payload, *keys: str) -> Payload:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, Mapping):
            return value
    return {}


def _str(payload: Payload, *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return None


def _int(payload: Payload, *keys: str) -> int | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
    return None


def _bool(payload: Payload, *keys: str) -> bool | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, bool):
            return value
    return None


def _enum[EnumT: Enum](enum_type: type[EnumT], value: str | None) -> EnumT | None:
    if value is None:
        return None
    try:
        return enum_type(value)
    except ValueError:
        return enum_type("__unknown__")


def _enum_value[EnumT: Enum](
    enum_type: type[EnumT],
    name: str,
    value: EnumT | str,
) -> str:
    if isinstance(value, enum_type):
        return str(value.value)
    try:
        return str(enum_type(value).value)
    except ValueError as exc:
        allowed = ", ".join(str(item.value) for item in enum_type)
        raise ValidationError(f"`{name}` должен быть одним из: {allowed}.") from exc
