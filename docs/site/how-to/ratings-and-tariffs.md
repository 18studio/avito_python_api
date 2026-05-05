# Рейтинги, отзывы и тарифы

Этот рецепт закрывает два близких сценария личного кабинета: контроль рейтинга и отзывов, а также чтение текущего тарифа аккаунта.

## Рейтинговый профиль

`rating_profile().get()` возвращает агрегированную информацию по рейтингу.

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    rating = avito.rating_profile().get()

print(rating.is_enabled)
print(rating.score)
print(rating.reviews_count)
```

## Список отзывов

Отзывы читаются через `review().list()`. Дефолтный вызов запрашивает первую страницу с `limit=50`. Для перехода по страницам или другого размера страницы передайте `page`, `offset` или `limit`.

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    reviews = avito.review().list(page=1, limit=20)

print(reviews.items[0].review_id)
print(reviews.items[0].text)
print(reviews.items[0].can_answer)
```

## Ответ на отзыв

Для создания ответа нужен числовой `review_id` и текст. Для повторяемых write-вызовов передавайте `idempotency_key`.

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    answer = avito.review_answer().create(
        review_id=123,
        text="Спасибо за отзыв",
        idempotency_key="review-answer-example-1",
    )

print(answer.answer_id)
print(answer.created_at)
```

## Удаление ответа

`answer_id` можно передать в фабрику `review_answer()` или явно в метод `delete()`.

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    deleted = avito.review_answer("456").delete(
        idempotency_key="review-delete-example-1",
    )

print(deleted.success)
```

## Текущий тариф

`tariff().get_tariff_info()` возвращает текущий и запланированный тарифные контракты.

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    tariff = avito.tariff().get_tariff_info()

print(tariff.current.level if tariff.current else None)
print(tariff.current.packages_count if tariff.current else None)
print(tariff.scheduled.level if tariff.scheduled else None)
```

Полный контракт смотрите в [reference по ratings](../reference/domains/ratings.md) и [reference по tariffs](../reference/domains/tariffs.md).
