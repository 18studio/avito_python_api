# Профиль, баланс и иерархия аккаунта

Этот рецепт показывает рабочий минимум для раздела `accounts`: получить профиль авторизованного пользователя, проверить баланс, прочитать историю операций и посмотреть данные иерархии аккаунтов.

## Профиль

Используйте `account().get_self()`, когда нужно определить пользователя, от имени которого работает токен.

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    profile = avito.account().get_self()

print(profile.user_id)
print(profile.email)
```

## Баланс

`get_balance()` использует единый порядок определения пользователя:

1. явный `user_id` в методе или фабрике;
2. `AVITO_USER_ID` / `AvitoSettings.user_id`;
3. `account().get_self()`, если `user_id` не задан.

Для приложений с одним аккаунтом проще задать `AVITO_USER_ID`. Для скриптов можно не передавать `user_id`, тогда SDK сам прочитает профиль текущего токена и использует `profile.user_id`.

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    balance = avito.account().get_balance()

print(balance.real)
print(balance.bonus)
print(balance.total)
```

Если `get_self()` не вернул идентификатор, SDK поднимет `ValidationError` с подсказкой передать `user_id` явно или настроить `AVITO_USER_ID`.

## История операций

История возвращается как `PaginatedList`: первая страница уже загружена, а остальные страницы читаются лениво при итерации или через `materialize()`.

```python
from datetime import datetime, timezone

from avito import AvitoClient

with AvitoClient.from_env() as avito:
    history = avito.account(user_id=7).get_operations_history(
        date_from=datetime(2026, 4, 1, tzinfo=timezone.utc),
        date_to=datetime(2026, 4, 30, tzinfo=timezone.utc),
    )
    operations = history.materialize()

print(operations[0].amount)
```

## Иерархия аккаунтов

Для компаний и агентских кабинетов используйте отдельный доменный объект `account_hierarchy()`.

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    hierarchy = avito.account_hierarchy(user_id=7)
    status = hierarchy.get_status()
    employees = hierarchy.list_employees()
    phones = hierarchy.list_company_phones()

print(status.is_active)
print(employees.items[0].name)
print(phones.items[0].phone)
```

## Объявления сотрудника

Операции иерархии принимают конкретные идентификаторы: `employee_id`, `item_ids`, `source_employee_id`. Для повторяемых write-вызовов передавайте `idempotency_key`.

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    hierarchy = avito.account_hierarchy(user_id=7)
    result = hierarchy.link_items(
        employee_id=10,
        item_ids=[101],
        idempotency_key="account-profile-example-1",
    )
    items = hierarchy.list_items_by_employee(employee_id=10, category_id=24)

print(result.success)
print(items[0].title)
```

Полный контракт моделей смотрите в [reference по домену accounts](../reference/domains/accounts.md), а общие правила пагинации — в [reference по пагинации](../reference/pagination.md).
