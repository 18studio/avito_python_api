# Reference

Справочник фиксирует публичный контракт SDK: фасад `AvitoClient`, настройки,
доменные объекты, модели, исключения, пагинацию и тестовые утилиты.

| Страница | Что искать |
|---|---|
| [AvitoClient и AsyncAvitoClient](client.md) | Sync/async инициализация, контекстные менеджеры, фабричные методы, `debug_info()` |
| [CLI](cli.md) | Команда `avito`, глобальные флаги, output modes, exit codes, локальные файлы, safety-флаги и coverage policy |
| [Асинхронный режим](../how-to/async.md) | Практический lifecycle `AsyncAvitoClient`, ASGI и async fake transport |
| [Конфигурация](config.md) | `AvitoSettings`, `AuthSettings`, env-переменные, per-operation overrides |
| [Покрытие API](coverage.md) | 204/204 Swagger operations из binding report |
| [Методы API](operations.md) | Карта Swagger operation → публичный SDK-метод |
| Домены | Публичные объекты и модели каждого доменного пакета |
| [Enum](enums.md) | Все публичные перечисления доменных пакетов |
| [Модели](models.md) | Сериализация, dataclass-контракт, публичные модели |
| [Исключения](exceptions.md) | Иерархия ошибок и диагностические поля |
| [Пагинация](pagination.md) | `PaginatedList[T]` и lazy-loading контракт |
| [Тестирование](testing.md) | `avito.testing` и fake transport для consumer-side тестов |
