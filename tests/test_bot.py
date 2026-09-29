import json

import httpx
import pytest

from maxpyin import (
    CallbackButton,
    InlineKeyboard,
    MaxApiError,
    MaxAuthError,
    MaxBot,
    MaxRateLimitError,
    calls,
)

MESSAGE = {
    "sender": {"user_id": 2, "first_name": "Анна", "is_bot": False},
    "recipient": {"chat_id": 10, "chat_type": "dialog", "user_id": 2},
    "timestamp": 1,
    "body": {"mid": "m1", "seq": 1, "text": "привет"},
}


def _bot(handler, retries: int = 2) -> tuple[MaxBot, httpx.Client]:
    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://platform-api2.max.ru",
    )
    return MaxBot("test-token", client=client, max_retries=retries), client


def test_send_message_uses_header_and_keyboard() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["auth"] = request.headers["authorization"]
        seen["query"] = dict(request.url.params)
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"message": MESSAGE})

    bot, client = _bot(handler)
    try:
        keyboard = InlineKeyboard().add(CallbackButton("Да", "yes"))
        message = bot.send_message(
            "Привет",
            chat_id=10,
            attachments=[keyboard],
        )
    finally:
        client.close()
    assert message.body is not None
    assert message.body.mid == "m1"
    assert seen["method"] == "POST"
    assert seen["path"] == "/messages"
    assert seen["auth"] == "test-token"
    assert "access_token" not in seen["query"]
    assert seen["query"]["chat_id"] == "10"
    assert seen["body"]["text"] == "Привет"
    button = seen["body"]["attachments"][0]["payload"]["buttons"][0][0]
    assert button == {"type": "callback", "text": "Да", "payload": "yes"}


def test_auth_error_is_not_retried() -> None:
    calls_made = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls_made["count"] += 1
        return httpx.Response(
            401,
            json={"code": "verify.token", "message": "Токен недействителен"},
        )

    bot, client = _bot(handler)
    try:
        with pytest.raises(MaxAuthError) as caught:
            bot.get_me()
    finally:
        client.close()
    assert calls_made["count"] == 1
    assert caught.value.code == "verify.token"
    assert caught.value.status_code == 401


def test_rate_limit_retries_then_raises() -> None:
    calls_made = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls_made["count"] += 1
        return httpx.Response(
            429,
            headers={"Retry-After": "0"},
            json={"message": "Слишком часто"},
        )

    bot, client = _bot(handler, retries=2)
    try:
        with pytest.raises(MaxRateLimitError):
            bot.get_me()
    finally:
        client.close()
    assert calls_made["count"] == 3


def test_success_false_is_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"success": False, "message": "нет прав"},
        )

    bot, client = _bot(handler)
    try:
        with pytest.raises(MaxApiError, match="нет прав"):
            bot.delete_message("m1")
    finally:
        client.close()


def test_upload_file_posts_multipart_to_returned_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/uploads":
            assert request.url.params["type"] == "file"
            return httpx.Response(
                200,
                json={"url": "https://upload.example/slot", "token": "pre"},
            )
        assert request.url.host == "upload.example"
        assert b'name="data"' in request.content
        assert b"notes.txt" in request.content
        assert b"hello-file" in request.content
        return httpx.Response(200, json={"token": "media-token"})

    bot, client = _bot(handler)
    try:
        uploaded = bot.upload_media(
            "file",
            b"hello-file",
            filename="notes.txt",
        )
    finally:
        client.close()
    assert uploaded.media_token == "media-token"
    assert uploaded.as_attachment("file")["payload"]["token"] == "media-token"


def test_poll_yields_one_page_without_second_request() -> None:
    calls_made = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls_made["count"] += 1
        assert request.url.params["types"] == "message_created"
        assert request.url.params["timeout"] == "30"
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
                "marker": 7,
            },
        )

    bot, client = _bot(handler)
    try:
        stream = bot.poll(types=["message_created"])
        update = next(stream)
        stream.close()
    finally:
        client.close()
    assert update.message is not None
    assert update.message.body is not None
    assert update.message.body.text == "привет"
    assert calls_made["count"] == 1


def test_comment_and_subscription_calls() -> None:
    deletion = calls.delete_comment("mid.1", "c-2")
    assert deletion.path == "/messages/mid.1/comments"
    assert deletion.params["comment_id"] == "c-2"
    created = calls.subscribe(
        "https://example.com/hook",
        update_types=["message_created"],
        secret="secret",
    )
    assert created.json_body is not None
    assert created.json_body["url"] == "https://example.com/hook"
    with pytest.raises(ValueError):
        calls.subscribe("http://example.com/hook")
