# CPA и CallTracking

Этот рецепт показывает, как читать CPA-звонки за период, открыть конкретный звонок CallTracking и скачать запись разговора без доступа к внутреннему transport.

## CPA-звонки за период

`cpa_call().list()` принимает нижнюю границу периода строкой в формате upstream API и возвращает типизированный список звонков.

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    calls = avito.cpa_call().list(
        date_time_from="2026-04-18T00:00:00Z",
        limit=100,
    )

print(calls.items[0].call_id)
print(calls.items[0].buyer_phone)
```

## Звонок CallTracking

Если известен `call_id`, используйте `call_tracking_call(call_id).get()`. Идентификатор можно передать в фабрику или явно в метод.

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    call = avito.call_tracking_call(10).get()

print(call.call.call_id if call.call else None)
print(call.call.talk_duration if call.call else None)
```

## Запись разговора

`download()` возвращает бинарную модель записи. Для логов и JSON-отчётов используйте `to_dict()`: бинарное содержимое сериализуется безопасно.

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    record = avito.call_tracking_call(10).download()
    payload = record.to_dict()

print(payload["content_base64"])
```

Полный контракт смотрите в [reference по cpa](../reference/domains/cpa.md). Исключения и поля metadata описаны в [reference по ошибкам](../reference/exceptions.md).
