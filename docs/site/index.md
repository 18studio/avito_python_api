---
hide:
  - toc
---

# avito-py

<section class="avito-hero" markdown>

**`avito-py`** — Python SDK для работы с Avito API через sync/async фасады `AvitoClient` и `AsyncAvitoClient`.
Скрывает transport, OAuth и retry-логику. Возвращает типизированные `dataclass`-модели. Покрывает 204 операции Avito API.

```bash
pip install avito-py
```

<div class="avito-badges" markdown>

[![CI](https://github.com/18studio/avito_python_api/actions/workflows/ci.yml/badge.svg)](https://github.com/18studio/avito_python_api/actions/workflows/ci.yml)
[![Coverage Status](https://coveralls.io/repos/github/18studio/avito_python_api/badge.svg?branch=main)](https://coveralls.io/github/18studio/avito_python_api?branch=main)
[![PyPI Downloads](https://img.shields.io/pypi/dm/avito-py.svg)](https://pypi.org/project/avito-py/)
[![API coverage](https://img.shields.io/badge/API%20coverage-204%2F204-success)](reference/coverage.md)

</div>

</section>

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **Впервые здесь**

    ---

    От `pip install` до первого запроса за 5 минут.

    [:octicons-arrow-right-24: Начать](tutorials/getting-started.md)

-   :material-book-open-variant:{ .lg .middle } **Ищу конкретный сценарий**

    ---

    Пошаговые рецепты: авторизация, async lifecycle, мессенджер, заказы, пагинация, тестирование и другие.

    [:octicons-arrow-right-24: How-to рецепты](how-to/index.md)

-   :material-sync:{ .lg .middle } **Асинхронный режим**

    ---

    `AsyncAvitoClient`, `async with`, ASGI lifespan, async-пагинация и тестирование без HTTP.

    [:octicons-arrow-right-24: Async how-to](how-to/async.md)

-   :material-code-tags:{ .lg .middle } **Нужен точный контракт**

    ---

    Полный справочник по классам, методам, исключениям и моделям.

    [:octicons-arrow-right-24: Reference](reference/index.md)

-   :material-lightbulb-outline:{ .lg .middle } **Хочу понять архитектуру**

    ---

    Концепции, мотивация решений, объяснение retry, пагинации и модели ошибок.

    [:octicons-arrow-right-24: Explanations](explanations/index.md)

</div>

---

## Карта документации

| | Учебные | Практические | Справочные | Концептуальные |
|---|---|---|---|---|
| **Режим** | Tutorials | How-to | Reference | Explanations |
| **Цель** | Обучение через действие | Решить конкретную задачу | Точная информация | Понять «почему» |
| **Раздел** | [Tutorials](tutorials/index.md) | [How-to](how-to/index.md) | [Reference](reference/index.md) | [Explanations](explanations/index.md) |

Для async-кода начните с рецепта [Асинхронный режим](how-to/async.md), а точный контракт смотрите в [AvitoClient и AsyncAvitoClient](reference/client.md).
