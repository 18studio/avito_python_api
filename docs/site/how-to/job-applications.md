# Вакансии, отклики и резюме

Этот рецепт показывает основной цикл раздела `jobs`: найти вакансии, получить отклики, изменить состояние отклика, посмотреть резюме и настроить webhook.

## Вакансии

`vacancy().list()` возвращает список вакансий, а `vacancy(vacancy_id).get()` открывает карточку конкретной вакансии.

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    vacancies = avito.vacancy().list()
    vacancy = avito.vacancy(101).get()

print(vacancies.items[0].title)
print(vacancy.url)
```

## Идентификаторы откликов

Для инкрементальной синхронизации используйте `application().get_ids()`: он возвращает id откликов, обновлённых после указанного момента.

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    ids = avito.application().get_ids(updated_at_from="2026-04-23T00:00:00+03:00")

print(ids.items[0].id)
print(ids.cursor)
```

## Данные откликов

Когда id уже известны, запросите подробные данные через `get_by_ids()`.

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    applications = avito.application().get_by_ids(ids=["app-1"])

print(applications.items[0].applicant_name)
print(applications.items[0].state)
```

## Обработка откликов

Можно получить справочник состояний, отметить отклик просмотренным и выполнить действие над откликом.

```python
from avito import AvitoClient
from avito.jobs import ApplicationViewedItem

with AvitoClient.from_env() as avito:
    states = avito.application().get_states()
    viewed = avito.application().update(
        applies=[ApplicationViewedItem(id="app-1", is_viewed=True)],
        idempotency_key="job-viewed-example-1",
    )
    invited = avito.application().apply(
        ids=["app-1"],
        action="invited",
        idempotency_key="job-invite-example-1",
    )

print(states.items[0].slug)
print(viewed.status)
print(invited.status)
```

## Резюме и контакты

`resume().list()` ищет резюме, `resume(resume_id).get()` открывает карточку, а `get_contacts()` возвращает контактные данные.

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    resumes = avito.resume().list(query="оператор")
    resume = avito.resume("res-1").get()
    contacts = avito.resume("res-1").get_contacts()

print(resumes.items[0].candidate_name)
print(resume.location)
print(contacts.phone)
```

## Webhook откликов

Webhook позволяет получать события по откликам без polling.

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    current = avito.job_webhook().get()
    updated = avito.job_webhook().update(
        url="https://example.com/job",
        secret="cb1e150b-c5bf-4c3e-acd1-20ec88bdb3a1",
        idempotency_key="job-webhook-example-1",
    )

print(current.url)
print(updated.is_active)
```

## Словари вакансий

Словари помогают выбирать значения для форм вакансий и фильтров.

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    dictionaries = avito.job_dictionary().list()
    values = avito.job_dictionary("profession").get()

print(dictionaries.items[0].id)
print(values.items[0].name)
```

Полный контракт смотрите в [reference по jobs](../reference/domains/jobs.md). Для write-операций вакансий используйте `idempotency_key`, особенно при повторных запусках фоновых задач.
