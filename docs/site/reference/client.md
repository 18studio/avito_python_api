# AvitoClient и AsyncAvitoClient

`AvitoClient` — единственная публичная точка входа SDK. Он владеет
конфигурацией, auth-provider и transport-слоем, а наружу отдаёт только доменные
объекты.

`AsyncAvitoClient` предоставляет тот же фасад для async-кода. Он создаёт
loop-bound ресурсы в `async with`, закрывается через `aclose()` и возвращает
async-доменные объекты.

## Контракт

- `AvitoClient.from_env()` — основной путь для конфигурации из окружения.
- `AsyncAvitoClient.from_env()` — async-аналог; использовать только через `async with`.
- `AvitoClient(client_id=..., client_secret=...)` — короткий явный путь для OAuth credentials.
- `AvitoClient(AvitoSettings(...))` — полный путь для расширенной конфигурации.
- Клиент поддерживает context manager и закрывает внутренние HTTP-клиенты в `close()`.
- После `close()` публичные операции поднимают `ClientClosedError`.
- `debug_info()` возвращает безопасный диагностический снимок без OAuth-секретов.

## Фасад

::: avito.AvitoClient

::: avito.AsyncAvitoClient

## Безопасная диагностика

::: avito.AvitoClient.debug_info

::: avito.AsyncAvitoClient.debug_info
