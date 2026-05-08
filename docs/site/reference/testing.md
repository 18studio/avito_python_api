# Тестирование

`avito.testing` — публичное пространство тестовых утилит для consumer-side
тестов без реального HTTP.

## Fake transport

::: avito.testing

## Контракт

- `FakeTransport` записывает выполненные запросы и отдаёт заранее заданные ответы.
- `json_response()` создаёт JSON-ответ для маршрута.
- `route_sequence()` задаёт последовательность ответов для retry и stateful-сценариев.
- `FakeTransport.as_client()` создаёт полностью инициализированный `AvitoClient`
  поверх fake transport без реального HTTP.
- `AsyncFakeTransport.as_client()` создаёт полностью инициализированный
  `AsyncAvitoClient` поверх `httpx.AsyncClient` и `httpx.MockTransport`.
- `FanoutPeakRecorder` измеряет пик одновременно выполняющихся async fake-запросов
  в consumer-side тестах агрегаторов.
- `RecordedRequest` позволяет проверять method, path, query params, headers и JSON body.

Пользовательские тесты должны работать через публичные утилиты `avito.testing`,
а не через приватные поля `AvitoClient`.
