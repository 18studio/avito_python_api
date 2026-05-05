# Целевая структура доменов

Эта страница фиксирует архитектуру доменных пакетов SDK. Все API-домены SDK
используют v2 layout: публичные методы находятся в `domain.py`, HTTP-контракты
в `operations.py` или `operations/`, а модели, enum-ы и payload mapping
принадлежат `models.py` или `models/`.

## Основной принцип

Данные API должны описываться в одном месте: в dataclass-моделях домена.

Модель отвечает за:

- десериализацию API JSON в SDK-модель через `from_payload()`;
- нормализацию типов: даты, числа, enum, nullable-поля, альтернативные имена ключей;
- публичную сериализацию через `to_dict()` и `model_dump()`;
- сериализацию request/query моделей через `to_payload()` и `to_params()`;
- enum-ы, относящиеся к этой модели или группе моделей.

Отдельные mapper-функции не являются способом преобразования JSON для
API-доменов. Domain-level `client.py`, `mappers.py` и standalone `enums.py`
в API-доменах запрещены.

## Структура простого домена

```text
avito/ratings/
  __init__.py
  domain.py
  operations.py
  models.py
```

Назначение файлов:

| Файл | Ответственность |
|---|---|
| `domain.py` | Публичные `DomainObject`-классы, reference-ready docstring-и, `@swagger_operation(...)`, бизнес-валидация и сбор публичных request-моделей |
| `operations.py` | Внутренние `OperationSpec`: HTTP method, path, operation context, retry policy и response/request model classes |
| `models.py` | Dataclass-модели, enum-ы, `from_payload()`, `to_payload()`, `to_params()` и нормализация |

В простом домене не используются отдельные `client.py`, `mappers.py` и
`enums.py`.

## Структура большого домена

Если домен содержит много независимых подсекций, модели и операции можно дробить по пакетам, сохраняя тот же принцип владения данными.

```text
avito/orders/
  __init__.py
  domain.py
  operations/
    __init__.py
    orders.py
    labels.py
    delivery.py
    stock.py
  models/
    __init__.py
    orders.py
    labels.py
    delivery.py
    stock.py
```

Enum должен лежать рядом с моделями, которые его используют:

```python
from dataclasses import dataclass
from enum import StrEnum
from avito.core.models import ApiModel
from avito.core.payload import JsonReader


class OrderStatus(StrEnum):
    CREATED = "created"
    PAID = "paid"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


@dataclass(slots=True, frozen=True)
class OrderInfo(ApiModel):
    order_id: str
    status: OrderStatus

    @classmethod
    def from_payload(cls, payload: object) -> "OrderInfo":
        reader = JsonReader(payload)
        return cls(
            order_id=reader.required_str("id", "order_id", "orderId"),
            status=reader.enum(OrderStatus, "status", unknown=OrderStatus.UNKNOWN),
        )
```

## Базовые модели

`core` предоставляет только инфраструктурные базовые классы. Они не знают о конкретных доменах Avito.

```python
from avito.core.serialization import SerializableModel


class ApiModel(SerializableModel):
    """Base class for public typed API response models."""


class RequestModel:
    def to_payload(self) -> dict[str, object]:
        return serialize_dataclass_payload(self)

    def to_params(self) -> dict[str, object]:
        return serialize_dataclass_payload(self)
```

Request-модель может использовать metadata для API-имён полей:

```python
from dataclasses import dataclass

from avito.core.fields import api_field
from avito.core.models import RequestModel


@dataclass(slots=True, frozen=True)
class CreateReviewAnswerRequest(RequestModel):
    review_id: int = api_field("reviewId")
    text: str = api_field("text")
```

## Описание операций

HTTP-контракт операции описывается отдельно от моделей, но не содержит JSON-маппинга.

```python
from avito.core.operations import OperationSpec
from avito.ratings.models import CreateReviewAnswerRequest, ReviewAnswerInfo


CREATE_REVIEW_ANSWER = OperationSpec(
    name="ratings.answers.create",
    method="POST",
    path="/ratings/v1/answers",
    request_model=CreateReviewAnswerRequest,
    response_model=ReviewAnswerInfo,
    retry_mode="enabled",
)
```

`OperationExecutor` выполняет запрос через `Transport`, а затем вызывает `response_model.from_payload(payload)`.

## Публичный доменный метод

Публичный метод остаётся явным: сигнатура, docstring и Swagger binding должны быть видны в коде и документации.

```python
from dataclasses import dataclass
from typing import cast

from avito.core.domain import DomainObject
from avito.core.swagger import swagger_operation
from avito.ratings import operations
from avito.ratings.models import CreateReviewAnswerRequest, ReviewAnswerInfo


@dataclass(slots=True, frozen=True)
class ReviewAnswer(DomainObject):
    __swagger_domain__ = "ratings"
    __sdk_factory__ = "review_answer"
    __sdk_factory_args__ = {"answer_id": "path.answer_id"}

    answer_id: int | str | None = None

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
    ) -> ReviewAnswerInfo:
        """Создаёт ответ на отзыв.

        Параметр `idempotency_key` задаёт ключ идемпотентности для безопасного повтора write-операции.

        Raises: AvitoError с полями operation, status, request_id, attempt, method и endpoint.
        """

        request = CreateReviewAnswerRequest(review_id=review_id, text=text)
        return cast(ReviewAnswerInfo, self._execute(
            operations.CREATE_REVIEW_ANSWER,
            request=request,
            idempotency_key=idempotency_key,
        ))
```

Публичные методы нельзя генерировать через `setattr`, `globals()` или другой runtime-patching. Новый слой операций сокращает внутреннее дублирование, но публичный SDK-контракт остаётся явным.

## Что выносится в core

`core` может содержать:

- `ApiModel`, `RequestModel` и shared serialization helpers;
- `JsonReader` для безопасного чтения JSON без знания доменных моделей;
- `api_field()` и другие helpers для dataclass metadata;
- `OperationSpec`, `OperationExecutor`, retry mode и path rendering;
- общие стратегии пагинации: offset, page, cursor;
- универсальную primitive-валидацию;
- transport, retries, exceptions, swagger discovery и swagger lint.

`core` не должен содержать:

- enum-ы конкретных доменов;
- request/response модели конкретных API-разделов;
- fallback-ключи конкретных API payload-ов;
- бизнес-валидацию вроде требования `item_id`, `order_id` или `review_id`;
- знание о том, какие поля входят в конкретный Avito endpoint.

## Инварианты

- Каждый публичный API-метод остаётся привязан к ровно одной Swagger operation через `@swagger_operation(...)`.
- Каждый публичный API-метод исполняет ровно один `OperationSpec`.
- Один `OperationSpec` описывает один transport-вызов, а его HTTP method/path
  совпадают с привязанной Swagger operation.
- JSON-маппинг response payload находится в `ResponseModel.from_payload()`.
- JSON-маппинг request/query payload находится в request dataclass.
- Enum-ы находятся в `models.py` или в подпакете `models/`, рядом с моделями.
- `client.py`, `mappers.py` и standalone `enums.py` отсутствуют в API-доменах.
