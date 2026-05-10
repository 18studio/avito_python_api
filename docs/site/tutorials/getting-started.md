# Быстрый старт

Это руководство проведёт вас от установки пакета до первого рабочего запроса к Avito API.

**Что вы сделаете**: установите `avito-py`, создадите клиент и получите информацию о своём аккаунте.

**Время**: около 5 минут.

---

## Шаг 1. Установка

```bash
pip install avito-py
```

Требования: Python 3.12, 3.13 или 3.14.

---

## Шаг 2. Получение ключей API

Перейдите на [avito.ru/professionals/api](https://www.avito.ru/professionals/api) и создайте приложение. Вам понадобятся `client_id` и `client_secret`.

---

## Шаг 3. Настройка переменных окружения

Создайте файл `.env` в корне проекта:

```env
AVITO_CLIENT_ID=ваш-client-id
AVITO_CLIENT_SECRET=ваш-client-secret
```

Или экспортируйте переменные напрямую:

```bash
export AVITO_CLIENT_ID=ваш-client-id
export AVITO_CLIENT_SECRET=ваш-client-secret
```

---

## Шаг 4. Первый запрос

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    profile = avito.account().get_self()

print(profile.name)
print(profile.email)
```

Запустите скрипт:

```bash
python main.py
```

Вы увидите имя и email вашего аккаунта Avito.

## Альтернатива: первый вызов из CLI

Если вам нужен терминальный режим, сохраните локальный профиль и выполните тот
же read-only запрос без Python-скрипта:

```bash
avito account add main --client-id client-id --user-id 123
avito --profile main account get-self
```

При добавлении профиля CLI спросит `Client Secret` скрытым prompt. Для
автоматизации используйте `--json --no-input`:

```bash
avito --json --no-input --profile main account get-self
```

Полный практический рецепт: [CLI](../how-to/cli.md).

---

## Что дальше

- [Авторизация и конфигурация](../how-to/auth-and-config.md) — все способы создания клиента, env-переменные, `AvitoSettings`.
- [CLI](../how-to/cli.md) — локальные профили, JSON-вывод, status, doctor и completion.
- [Работа с объявлениями](../how-to/index.md) — получение, фильтрация, статистика.
- [Reference: AvitoClient](../reference/client.md) — полный список фабричных методов.

!!! tip "Используйте контекстный менеджер"
    Конструкция `with AvitoClient.from_env() as avito:` автоматически закрывает HTTP-соединения при выходе из блока. Альтернатива — вызвать `client.close()` вручную.
