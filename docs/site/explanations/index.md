# Explanations

Explanations описывают причины архитектурных решений SDK: границы слоёв, retry-поведение, модель ошибок, безопасность диагностики и правила обратной совместимости.

| Статья | Что объясняет |
|---|---|
| [Архитектура SDK](architecture.md) | Как `AvitoClient`, домены, `OperationSpec`, executor, transport, auth и модели разделяют ответственность |
| [Целевая структура доменов](domain-architecture-v2.md) | Как API-домены используют dataclass-модели для сериализации, десериализации, нормализации и enum-ов |
| [OAuth и токены](auth-flow.md) | Почему token-flow скрыт за `AuthProvider` |
| [Transport и retry](transport-and-retries.md) | Почему retry живёт в transport-слое и как учитываются 429/5xx |
| [Модель ошибок](error-model.md) | Как HTTP-коды превращаются в typed exceptions |
| [Семантика пагинации](pagination-semantics.md) | Почему `PaginatedList` ленивый и когда загружаются страницы |
| [Dry-run и идемпотентность](dry-run-and-idempotency.md) | Как write-операции проверяются без сетевого вызова |
| [Стратегия тестирования](testing-strategy.md) | Как `FakeTransport`, contract-тесты и docs-harness проверяют SDK |
| [Покрытие API и deprecation](api-coverage-and-deprecations.md) | Как specs, reference и runtime warnings связаны между собой |
| [Swagger binding subsystem](swagger-binding-subsystem.md) | Как Swagger specs, bindings, strict lint, JSON report и contract runner сохраняют coverage-контекст |
| [Resolution конфигурации](config-resolution.md) | Как env, `.env` и defaults превращаются в `AvitoSettings` |
| [Security и redaction](security-and-redaction.md) | Какие секреты SDK не раскрывает в диагностике и ошибках |

Для практических сценариев используйте [how-to рецепты](../how-to/index.md), а для полного API-контракта — [reference](../reference/index.md).
