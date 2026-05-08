# Async API

`AsyncAvitoClient` повторяет доменную поверхность `AvitoClient`, но все сетевые
методы вызываются через `await`. Клиент обязательно открывается через `async with`:
в этот момент создаются `httpx.AsyncClient`, async locks и transport.

```python
from avito import AsyncAvitoClient


async def load_profile() -> str | None:
    async with AsyncAvitoClient.from_env() as avito:
        profile = await avito.account().get_self()
        return profile.name
```

## Переписать sync-вызов на async

Sync:

```python
from avito import AvitoClient

with AvitoClient.from_env() as avito:
    orders = avito.order().list()
    label = avito.order_label(task_id=42).download()
```

Async:

```python
from avito import AsyncAvitoClient

async with AsyncAvitoClient.from_env() as avito:
    orders = await avito.order().list()
    label = await avito.order_label(task_id=42).download()
```

Для пагинации sync `PaginatedList` и async `AsyncPaginatedList` отличаются:
async-контейнер не является `list`, поэтому используйте `async for` или
`await materialize()`.

```python
async with AsyncAvitoClient.from_env() as avito:
    page = await avito.ad(user_id=123).list(limit=100)
    items = await page.materialize()
```

## Тестирование без HTTP

```python
from avito.testing import AsyncFakeTransport


async def test_orders_summary() -> None:
    fake = (
        AsyncFakeTransport()
        .add_json("GET", "/order-management/1/orders", {"orders": []})
    )
    client = fake.as_client(user_id=123)

    summary = await client.order_summary()

    assert summary.total_orders == 0
    await client.aclose()
```

## Ограничения

- `AsyncPaginatedList` не поддерживает list API и конкурентную итерацию одного
  экземпляра.
- Бинарные ответы, включая PDF-этикетки заказов, загружаются целиком в память.
  Streaming API в версии 2.1.0 нет.
- Один `AsyncAvitoClient` нельзя переносить между event loop. Создавайте клиент в
  том loop, где он будет использоваться.

## Использование под ASGI (FastAPI / aiohttp / Starlette)

### FastAPI lifespan

Создавайте клиент в lifespan, храните его в `app.state` и закрывайте на shutdown.

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request

from avito import AsyncAvitoClient


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with AsyncAvitoClient.from_env() as avito:
        app.state.avito = avito
        yield


app = FastAPI(lifespan=lifespan)


def get_avito(request: Request) -> AsyncAvitoClient:
    return request.app.state.avito


@app.get("/orders/summary")
async def orders_summary(avito: AsyncAvitoClient = Depends(get_avito)) -> dict[str, object]:
    summary = await avito.order_summary()
    return summary.to_dict()
```

### aiohttp cleanup_ctx

```python
from collections.abc import AsyncIterator

from aiohttp import web

from avito import AsyncAvitoClient

avito_key = web.AppKey("avito", AsyncAvitoClient)


async def avito_client_ctx(app: web.Application) -> AsyncIterator[None]:
    async with AsyncAvitoClient.from_env() as avito:
        app[avito_key] = avito
        yield


async def orders_summary(request: web.Request) -> web.Response:
    summary = await request.app[avito_key].order_summary()
    return web.json_response(summary.to_dict())


app = web.Application()
app.cleanup_ctx.append(avito_client_ctx)
app.router.add_get("/orders/summary", orders_summary)
```

### Per-worker isolation

Под Gunicorn/Uvicorn создавайте один `AsyncAvitoClient` на worker process. Не
создавайте клиент в master process до fork и не передавайте его между процессами:
у каждого worker свой event loop, connection pool и набор async locks.

### Запрещённый паттерн

```python
from avito import AsyncAvitoClient

avito = AsyncAvitoClient.from_env()


async def handler() -> dict[str, object]:
    await avito.__aenter__()  # ❌ loop-bound ресурсы создаются в request handler
    return (await avito.order_summary()).to_dict()
```

Такой код привязывает внутренний `httpx.AsyncClient` к первому loop, который
коснулся handler. В тестах, background scheduler или другом worker loop это
приведёт к cross-loop ошибкам и утечкам соединений.

### Background tasks

`asyncio.create_task()` и FastAPI `BackgroundTasks`, которые исполняются в том же
event loop, могут использовать app-level клиент из lifespan. Для process pool,
отдельного worker или внешнего scheduler создавайте отдельный `AsyncAvitoClient`
внутри этого процесса и его loop.
