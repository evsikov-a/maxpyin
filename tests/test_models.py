from maxpyin import UploadResult, User, parse_update
from maxpyin.models import Message


def test_user_keeps_unknown_fields() -> None:
    user = User.from_dict(
        {
            "user_id": 7,
            "first_name": "Бот",
            "is_bot": True,
            "commands": [{"name": "start", "description": "Старт"}],
            "future_flag": True,
        },
    )
    assert user.user_id == 7
    assert user.commands is not None
    assert user.commands[0].name == "start"
    assert user.extra == {"future_flag": True}


def test_parse_update_reads_message_and_callback() -> None:
    update = parse_update(
        {
            "update_type": "message_callback",
            "timestamp": 10,
            "callback": {
                "callback_id": "cb-1",
                "payload": "yes",
                "timestamp": 10,
                "user": {"user_id": 3, "first_name": "Анна"},
            },
            "message": {
                "timestamp": 9,
                "recipient": {
                    "chat_id": 4,
                    "chat_type": "dialog",
                    "user_id": 3,
                },
                "body": {"mid": "m1", "seq": 1, "text": "привет"},
            },
            "chat_title": "новый",
        },
    )
    assert update.callback is not None
    assert update.callback.callback_id == "cb-1"
    assert update.message is not None
    assert update.message.body is not None
    assert update.message.body.text == "привет"
    assert update.extra == {"chat_title": "новый"}


def test_message_nested_sender() -> None:
    message = Message.from_dict(
        {
            "timestamp": 1,
            "sender": {"user_id": 2, "first_name": "Анна", "rank": "gold"},
            "body": {"mid": "m", "seq": 1, "text": None, "stickers": 1},
        },
    )
    assert message.sender is not None
    assert message.sender.extra == {"rank": "gold"}
    assert message.body is not None
    assert message.body.extra == {"stickers": 1}


def test_image_upload_token() -> None:
    result = UploadResult.from_dict(
        {"photos": {"100": {"token": "img-token"}}},
    )
    assert result.media_token == "img-token"
    attachment = result.as_attachment("image")
    assert attachment["type"] == "image"
    assert attachment["payload"]["photos"]["100"]["token"] == "img-token"
