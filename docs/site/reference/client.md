# AvitoClient

`AvitoClient` — единственная публичная точка входа SDK. Он владеет
конфигурацией, auth-provider и transport-слоем, а наружу отдаёт только доменные
объекты.

## Контракт

- `AvitoClient.from_env()` — основной путь для конфигурации из окружения.
- `AvitoClient(client_id=..., client_secret=...)` — короткий явный путь для OAuth credentials.
- `AvitoClient(AvitoSettings(...))` — полный путь для расширенной конфигурации.
- Клиент поддерживает context manager и закрывает внутренние HTTP-клиенты в `close()`.
- После `close()` публичные операции поднимают `ClientClosedError`.
- `debug_info()` возвращает безопасный диагностический снимок без OAuth-секретов.

## Фасад

::: avito.AvitoClient

## Безопасная диагностика

::: avito.AvitoClient.debug_info
