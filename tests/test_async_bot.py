import json

import httpx
import pytest

from maxpyin import AsyncMaxBot, MaxAuthError

MESSAGE = {
    "recipient": {"chat_id": 10, "chat_type": "chat", "user_id": 2},
    "timestamp": 1,
    "body": {"mid": "m1", "seq": 1, "text": "привет"},
}


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://platform-api2.max.ru",
    )


async def test_async_send_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "test-token"
        body = json.loads(request.content.decode())
        assert body["text"] == "Привет"
        return httpx.Response(200, json={"message": MESSAGE})

    client = _client(handler)
    bot = AsyncMaxBot("test-token", client=client)
    try:
        message = await bot.send_message("Привет", chat_id=10)
    finally:
        await client.aclose()
    assert message.body is not None
    assert message.body.text == "привет"


async def test_async_auth_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "нет доступа"})

    client = _client(handler)
    bot = AsyncMaxBot("test-token", client=client)
    try:
        with pytest.raises(MaxAuthError):
            await bot.get_me()
    finally:
        await client.aclose()


async def test_async_poll_one_update() -> None:
    calls_made = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls_made["count"] += 1
        return httpx.Response(
            200,
            json={
                "updates": [
                    {
                        "update_type": "message_created",
                        "timestamp": 1,
                        "message": MESSAGE,
                    },
                ],
                "marker": 3,
            },
        )

    client = _client(handler)
    bot = AsyncMaxBot("test-token", client=client)
    try:
        stream = bot.poll(types=["message_created"])
        update = await anext(stream)
        await stream.aclose()
    finally:
        await client.aclose()
    assert update.update_type == "message_created"
    assert calls_made["count"] == 1
