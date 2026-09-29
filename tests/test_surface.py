import inspect

from maxpyin import AsyncMaxBot, MaxBot

REQUIRED = {
    "add_admins",
    "answer_callback",
    "close",
    "delete_chat",
    "delete_comment",
    "delete_message",
    "edit_chat",
    "edit_comment",
    "edit_me",
    "edit_message",
    "get_admins",
    "get_chat",
    "get_comment",
    "get_comments",
    "get_me",
    "get_members",
    "get_membership",
    "get_message",
    "get_messages",
    "get_pinned_message",
    "get_subscriptions",
    "get_updates",
    "get_upload_url",
    "leave_chat",
    "pin_message",
    "poll",
    "remove_admin",
    "remove_member",
    "send_action",
    "send_comment",
    "send_message",
    "set_commands",
    "subscribe",
    "unpin_message",
    "unsubscribe",
    "upload_file",
    "upload_media",
}


def _methods(cls: type) -> dict[str, object]:
    found = {}
    for name, value in inspect.getmembers(cls, inspect.isfunction):
        if name.startswith("_"):
            continue
        found[name] = value
    return found


def test_bots_share_public_methods() -> None:
    sync = _methods(MaxBot)
    async_methods = _methods(AsyncMaxBot)
    assert REQUIRED <= set(sync)
    assert set(sync) == set(async_methods)
    assert "get_chats" not in sync
    assert "add_members" not in sync


def test_public_methods_have_russian_docstrings() -> None:
    for cls in (MaxBot, AsyncMaxBot):
        assert cls.__doc__
        assert _has_cyrillic(cls.__doc__)
        for name, method in _methods(cls).items():
            doc = inspect.getdoc(method)
            assert doc, name
            assert _has_cyrillic(doc), name


def _has_cyrillic(text: str) -> bool:
    letters = {char.lower() for char in text}
    return bool(letters & set("абвгдеёжзийклмнопрстуфхцчшщъыьэюя"))
