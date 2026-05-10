# CLI

Этот рецепт показывает ежедневную работу через команду `avito`: настройку
локального профиля, первый API-вызов, JSON-вывод для автоматизации,
диагностику и shell completion.

CLI является тонкой оболочкой над SDK. API-команды создают `AvitoClient`,
вызывают публичную factory и публичный доменный метод, а затем сериализуют
публичные SDK-модели.

## Установка и проверка

```bash
pip install avito-py
avito --version
python -m avito --help
```

`avito` и `python -m avito` используют одно и то же CLI-приложение.

## Добавить профиль

Интерактивный ввод не кладёт секрет в историю shell:

```bash
avito account add main --client-id client-id --user-id 123
```

CLI спросит `Client Secret` скрытым prompt. Для CI и shell-скриптов используйте
stdin:

```bash
printf '%s\n' 'client-secret' | avito --no-input account add main \
  --client-id client-id \
  --client-secret-stdin \
  --user-id 123
```

Явные `--client-secret` и совместимый alias `--api-key` тоже поддержаны, но их
значения могут попасть в историю shell. Используйте их только там, где это
осознанно контролируется.

По умолчанию локальные файлы лежат в `~/.avito-py/`:

```text
~/.avito-py/
  config.json
  accounts.json
```

Это plaintext JSON-хранилище. Каталог создаётся с правами `0700`, файлы
записываются атомарно с правами `0600`. Первая CLI-версия не использует OS
keychain, поэтому защищайте домашний каталог и не добавляйте эти файлы в
репозиторий.

Каталог можно переопределить:

```bash
AVITO_PY_HOME=.avito-local avito account list
```

`AVITO_PY_HOME` имеет приоритет над совместимой переменной `MY_SDK_HOME`.

## Управлять профилями

```bash
avito account list
avito account use main
avito account current
avito account delete old-profile --confirm old-profile
```

`avito account remove` является совместимым alias для `account delete` и не
считается отдельной канонической командой.

Активный профиль можно задать явно на один вызов:

```bash
avito --profile main account current
```

Или сохранить в локальной конфигурации:

```bash
avito config set active-profile main
avito config get active-profile --show-source
avito config list --show-source
```

Приоритет профиля: root-флаг `--profile`, затем `config.json`, затем пустое
значение.

## Первый API-вызов

```bash
avito --profile main account get-self
avito --profile main account get-balance --user-id 123
```

API-команды используют только публичный `AvitoClient`. CLI не обращается к
transport, operation specs или auth internals напрямую.

Справка строится из той же registry metadata, что и команды:

```bash
avito help account
avito help account get-balance
```

## JSON для автоматизации

Для скриптов используйте `--json --no-input`, чтобы stdout содержал только
машиночитаемый результат, а ошибки уходили в stderr:

```bash
avito --json --no-input --profile main account get-self
avito --json --no-input config list --show-source
avito --json --no-input status
```

`--plain`, `--table`, `--wide` и `--json` взаимоисключающие. Если указать больше
одного режима вывода, CLI завершится с кодом `2`.

## Вспомогательные workflows

Публичные helper-команды не входят в Swagger one-to-one coverage, но вызывают
только публичные методы `AvitoClient`:

```bash
avito --profile main account-health show --user-id 123
avito --profile main listing-health show --user-id 123 --limit 20
avito --profile main chat-summary show --user-id 123
avito --profile main order-summary show
avito --profile main review-summary show
avito --profile main promotion-summary show --item-ids 456
avito capabilities show
```

Для автоматизации добавьте `--json --no-input`.

## Диагностика

`status` проверяет локальную готовность профиля без сетевого вызова:

```bash
avito status
avito --json status
```

`doctor` проверяет локальные JSON-файлы и права доступа:

```bash
avito doctor
```

Если найдены проблемы, команда печатает диагностический отчёт и завершает работу
с ошибкой конфигурации. Секреты в диагностике маскируются.

## Completion

```bash
avito completion bash
avito completion zsh
avito completion fish
```

Команды печатают инструкцию для выбранного shell. Добавьте её в профиль shell,
если completion нужен постоянно.

## Где точный контракт

Полный стабильный контракт CLI: [CLI reference](../reference/cli.md). Архитектура
registry, coverage linter, исключения и политика пагинации описаны в
[CLI architecture](../explanations/cli-architecture.md).
