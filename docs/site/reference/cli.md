# CLI

`avito` — командная строка `avito-py`. Она использует тот же публичный SDK:
API-команды создают `AvitoClient`, вызывают публичную factory и публичный
доменный метод, а затем печатают результат через общий renderer.

`python -m avito` запускает то же CLI-приложение.

## Грамматика команд

```text
avito [global flags] <resource> <action> [arguments] [flags]
```

Глобальные флаги гарантированно поддержаны перед resource/action:

```bash
avito --profile main account get-self
avito --json --no-input --profile main account get-balance --user-id 123
```

Флаги после вложенной команды являются флагами этой команды. Перенос root-флагов
в конец команды не является контрактом первого релиза.

Имена resources, actions и flags используют lowercase kebab-case. `resource-id`
запрещён: команды используют конкретные имена вроде `item-id`, `order-id`,
`chat-id`, `user-id`.

## Входные точки и справка

| Команда | Контракт |
|---|---|
| `avito --help` | Печатает root help без чтения account files и без сетевых вызовов. |
| `avito help` | Печатает тот же root help. |
| `avito help <resource>` | Печатает registry-backed справку по resource. |
| `avito help <resource> <action>` | Печатает справку по команде, включая registry metadata и флаги. |
| `avito --version` | Печатает версию пакета. |
| `avito version` | Печатает версию; с `--json` выводит объект `version`. |
| `python -m avito --help` | Использует ту же root-команду, что и `avito --help`. |

Registry-backed справка не создаёт `AvitoClient`, не читает локальные account
files и не делает HTTP-запросов.

## Глобальные флаги

| Флаг | Поведение |
|---|---|
| `--profile NAME` | Выбирает локальный профиль для API/helper-команд. Имеет приоритет над config. |
| `--config PATH` | Использует альтернативный `config.json` для локальной конфигурации. |
| `--json` | Печатает результат в stable JSON на stdout и JSON-ошибки на stderr. |
| `--plain` | Выбирает plain human output. |
| `--table` | Выбирает табличный human output, где команда его поддерживает. |
| `--wide` | Выбирает расширенный табличный output, где команда его поддерживает. |
| `--quiet` | Скрывает необязательный успешный output; ошибки остаются на stderr. |
| `--no-input` | Запрещает prompt. Если команде нужен ввод, она завершается ошибкой. |
| `--no-color` | Отключает цветной вывод. |
| `--verbose` | Включает дополнительные пользовательские детали без секретов. |
| `--debug` | Включает sanitized debug details в ошибках. |
| `--timeout SECONDS` | Передаётся в SDK-вызов, если публичный метод принимает `timeout`. |

`--json`, `--plain`, `--table` и `--wide` взаимоисключающие. Комбинация двух или
более таких флагов завершается с exit code `2`.

`NO_COLOR=1` также отключает цветной output.

## Режимы вывода

Результаты команд печатаются в stdout. Ошибки, предупреждения, progress и
debug-диагностика печатаются в stderr.

Human output:

- одиночные объекты печатаются как сгруппированные key/value строки;
- коллекции печатаются как таблицы, если есть стабильные колонки;
- write-команды печатают короткий результат действия;
- `--quiet` скрывает необязательный успешный текст.

JSON output:

- stdout содержит только JSON-результат;
- warnings, progress и debug details не попадают в stdout;
- JSON errors печатаются в stderr;
- SDK-модели сериализуются только через публичный `model_dump()` / `to_dict()`.

Пример:

```bash
avito --json --no-input --profile main account get-self
```

## Коды завершения

| Code | Stable error code | Значение |
|---:|---|---|
| `0` | — | Успешное выполнение. |
| `1` | `SDK_METHOD_FAILED`, `CLI_INTERNAL_ERROR` | Общая ошибка или неожиданная внутренняя ошибка. |
| `2` | `CLI_USAGE_ERROR`, `INVALID_FLAG_COMBINATION`, `VALIDATION_FAILED` | Неверный синтаксис, несовместимые флаги или ошибка валидации CLI-аргумента. |
| `3` | `ACCOUNT_NOT_FOUND`, `COMMAND_UNSUPPORTED` | Объект или команда не найдены. |
| `4` | `PERMISSION_DENIED` | Недостаточно прав на локальный файл или upstream запретил действие. |
| `5` | `AUTH_REQUIRED`, `CONFIG_INVALID`, `CLI_CONFIGURATION_ERROR` | Нужна авторизация или локальная конфигурация некорректна. |
| `6` | `CONFLICT`, `ACCOUNT_EXISTS` | Конфликт состояния, например дублирующийся профиль. |
| `7` | `CLI_UPSTREAM_ERROR` | Upstream API вернул ошибку, не попавшую в более точный класс. |
| `8` | `EXTERNAL_DEPENDENCY_UNAVAILABLE`, `CLI_TRANSPORT_ERROR` | Недоступна внешняя зависимость или transport. |
| `70` | `CLI_INTERNAL_ERROR` | Зарезервировано для неожиданных внутренних сбоев. |

Форма human error:

```text
INVALID_FLAG_COMBINATION: Флаги --json, --plain, --table и --wide нельзя использовать вместе.
```

Форма JSON error:

```json
{
  "code": "INVALID_FLAG_COMBINATION",
  "exit_code": 2,
  "message": "Флаги --json, --plain, --table и --wide нельзя использовать вместе."
}
```

`--debug` может добавить sanitized `details`, но не печатает сырые секреты.

## Локальные файлы и переменные окружения

CLI home выбирается так:

1. `AVITO_PY_HOME`
2. `MY_SDK_HOME`
3. `~/.avito-py`

Файлы:

```text
~/.avito-py/
  config.json
  accounts.json
```

Требования к файловой системе:

- каталог создаётся лениво с правами `0700`;
- `config.json` и `accounts.json` записываются атомарно через временный файл и
  `os.replace`;
- файлы создаются с правами `0600`, где это поддерживает платформа;
- импорт CLI-модулей не создаёт файлы и каталоги.

`config.json` хранит активный профиль. `accounts.json` хранит локальные профили
и OAuth settings. Активность не дублируется флагом внутри account record.

Первая версия хранит secrets в plaintext JSON. Это не secret manager и не OS
keychain.

## Команды учетных записей

| Команда | Контракт |
|---|---|
| `avito account add ACCOUNT-NAME --client-id CLIENT-ID` | Добавляет локальный профиль без сетевого вызова. |
| `avito account list` | Показывает сохранённые профили и активный профиль. |
| `avito account use ACCOUNT-NAME` | Сохраняет активный профиль в config. |
| `avito account current` | Показывает активный профиль и замаскированные поля учетной записи. |
| `avito account delete ACCOUNT-NAME` | Удаляет профиль после подтверждения. |
| `avito account remove ACCOUNT-NAME` | Alias для `account delete`; не canonical command. |

Флаги `account add`:

| Флаг | Поведение |
|---|---|
| `--client-id CLIENT-ID` | Обязательный OAuth client id. |
| `--client-secret CLIENT-SECRET` | Явный secret; может попасть в историю shell. |
| `--api-key API-KEY` | Совместимый alias для `--client-secret`. |
| `--client-secret-stdin` | Читает secret одной строкой из stdin. |
| `--endpoint URL` | Alias для base URL Avito API. |
| `--user-id USER-ID` | Пользователь по умолчанию для SDK settings. |
| `--scope SCOPE` | OAuth scope. |

Если secret не передан и input разрешён, `account add` использует hidden prompt.
В `--no-input` режиме отсутствие secret даёт ошибку `AUTH_REQUIRED`.

`--client-secret`, `--api-key` и `--client-secret-stdin` взаимоисключающие.

Примеры:

```bash
avito account add main --client-id client-id --user-id 123
printf '%s\n' 'client-secret' | avito --no-input account add main \
  --client-id client-id \
  --client-secret-stdin
avito account use main
avito account delete old --confirm old
```

## Команды конфигурации

Поддержанный ключ первого релиза: `active-profile`.

```bash
avito config set active-profile main
avito config get active-profile
avito config get active-profile --show-source
avito config list --show-source
avito config unset active-profile
```

Source values:

- `cli` — значение пришло из root-флага `--profile`;
- `config` — значение прочитано из `config.json`;
- `default` — значение не задано.

С `--json` команды возвращают объект `config`.

## Status, doctor и completion

`status` проверяет локальную готовность профиля и account store без сетевых
вызовов:

```bash
avito status
avito --json status
```

В JSON поле `network_checked` равно `false`.

`doctor` проверяет локальные JSON-файлы и права доступа:

```bash
avito doctor
```

Если найдены проблемы, команда печатает отчёт и завершается ошибкой
конфигурации.

Completion:

```bash
avito completion bash
avito completion zsh
avito completion fish
```

## API-команды

API-команды registry-backed и вызывают только публичный SDK:

```bash
avito --profile main account get-self
avito --profile main account get-balance --user-id 123
avito --profile main ad get --user-id 123 --item-id 456
```

Флаги API-команды выбираются из Swagger binding metadata:

- `factory_args`;
- `method_args`.

Публичная Python signature используется для проверки и приведения этих выбранных
аргументов. CLI не публикует все параметры метода автоматически. Per-operation
`timeout` управляется только root-флагом `--timeout`; `retry` не является CLI
флагом первого релиза.

Поддержанное приведение значений:

- `str`, `int`, `float`, `bool`;
- `date` и `datetime`;
- enum по имени или значению;
- optional values;
- repeated flags и comma-separated lists;
- public input models только через typed CLI adapter, когда он явно добавлен.

## Вспомогательные workflows

Helper-команды не входят в Swagger one-to-one coverage. Они вызывают публичные
non-Swagger методы `AvitoClient`.

```bash
avito account-health show --user-id 123
avito listing-health show --user-id 123 --limit 20
avito chat-summary show --user-id 123
avito order-summary show
avito review-summary show
avito promotion-summary show --item-ids 456
avito capabilities show
```

`business_summary` является compatibility wrapper для `account_health` и не
получает отдельную canonical CLI-команду в первом релизе.

## Флаги безопасности

Write/destructive/expensive команды используют reviewed safety metadata из
registry. HTTP method может дать исходную классификацию, но не является
единственным источником политики.

| Флаг | Поведение |
|---|---|
| `--yes` | Выполнить destructive/expensive команду без prompt. |
| `--confirm VALUE` | Выполнить команду только при точном подтверждении. |
| `--dry-run` | Показать план без transport-вызова, только если SDK-метод поддерживает `dry_run`. |

`--yes` и `--confirm` взаимоисключающие. В `--no-input` режиме команда, которой
нужно подтверждение, завершается ошибкой вместо prompt.

CLI не имитирует dry-run для SDK-методов, которые всё равно сделали бы сетевой
вызов.

## Пагинация

SDK `PaginatedList[T]` ленивый. CLI ограничивает paginated output по умолчанию:
первая страница или SDK/default page size. Полная материализация требует явного
opt-in командой, которая документирует соответствующий флаг.

JSON-форма пагинации содержит `items` и metadata, когда она доступна. Progress и
warnings печатаются в stderr.

## Маскирование секретов

Один sanitizer применяется к:

- human output;
- JSON output;
- errors;
- `--verbose` и `--debug`;
- `status` и `doctor`;
- coverage/debug reports.

Редактируются вложенные поля, списки и exception metadata с ключами или
значениями, похожими на OAuth secrets: `client_secret`, `api_key`,
`refresh_token`, `access_token`, authorization headers и token-like values.

## Политика покрытия

CLI coverage строится из `discover_swagger_bindings()` и проверяется
`scripts/lint_cli_coverage.py`.

Инварианты:

```text
каждый sync Swagger binding -> одна canonical CLI-команда или documented exclusion
каждая canonical API CLI-команда -> один sync Swagger binding
каждый поддержанный helper workflow -> команда или documented exclusion
```

Aliases не считаются canonical coverage.

Intentional exclusions первого релиза:

- четыре token-client bindings без публичной `AvitoClient` factory;
- bindings, которым нужен typed CLI adapter, file/stdin/binary handling,
  complex public input model или уточнение factory/method metadata.

Strict gate:

```bash
poetry run python scripts/lint_cli_coverage.py --strict
make cli-lint
```

`make cli-lint` входит в `make check`.
