"""Сборка запросов Bot API без сетевого ввода-вывода."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

from .keyboards import serialize_attachment, serialize_link
from .models import BotCommand, ChatAdmin, SenderAction

_UPLOAD_TYPES = frozenset({"image", "video", "audio", "file"})
_TEXT_FORMATS = frozenset({"markdown", "html"})
_ACTIONS = frozenset(
    {
        SenderAction.TYPING_ON,
        SenderAction.SENDING_PHOTO,
        SenderAction.SENDING_VIDEO,
        SenderAction.SENDING_AUDIO,
        SenderAction.SENDING_FILE,
    },
)
_SECRET = re.compile(r"[A-Za-z0-9_-]{5,256}")


@dataclass(frozen=True)
class ApiCall:
    """Подготовленный HTTP-запрос к Bot API.

    Attributes:
        method: Глагол HTTP.
        path: Путь относительно базового URL.
        params: Query-параметры. Пустые значения уже отброшены.
        json_body: Тело JSON или ``None``, если тела нет.
        timeout: Тайм-аут этого запроса в секундах.
    """

    method: str
    path: str
    params: dict[str, Any] = field(default_factory=dict)
    json_body: dict[str, Any] | None = None
    timeout: float | None = None


def _compact(data: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


def _csv(values: Sequence[Any] | None) -> str | None:
    if not values:
        return None
    return ",".join(str(item) for item in values)


def _require_int(name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} должен быть целым числом.")
    return value


def _require_str(name: str, value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} должен быть непустой строкой.")
    return value


def _optional_int(name: str, value: int | None) -> int | None:
    if value is None:
        return None
    return _require_int(name, value)


def _bounded(
    name: str,
    value: int | None,
    low: int,
    high: int,
) -> int | None:
    if value is None:
        return None
    number = _require_int(name, value)
    if number < low or number > high:
        raise ValueError(f"{name} должен быть от {low} до {high}.")
    return number


def _positive(name: str, value: int | None) -> int | None:
    if value is None:
        return None
    number = _require_int(name, value)
    if number < 0:
        raise ValueError(f"{name} не может быть отрицательным.")
    return number


def _check_format(text_format: str | None) -> None:
    if text_format is not None and text_format not in _TEXT_FORMATS:
        raise ValueError("Формат текста должен быть markdown или html.")


def _message_id_path(message_id: str, suffix: str = "") -> str:
    safe_id = quote(_require_str("message_id", message_id), safe="")
    return f"/messages/{safe_id}{suffix}"


def _chat_path(chat_id: int, suffix: str = "") -> str:
    return f"/chats/{_require_int('chat_id', chat_id)}{suffix}"


def _command_payload(
    item: BotCommand | tuple[str, str] | Mapping[str, Any],
) -> dict[str, str]:
    if isinstance(item, BotCommand):
        name, description = item.name, item.description
    elif isinstance(item, tuple) and len(item) == 2:
        name, description = item
    elif isinstance(item, Mapping):
        name = item.get("name")
        description = item.get("description")
    else:
        raise TypeError(
            "Команда должна быть BotCommand, парой или словарём.",
        )
    if not isinstance(name, str) or not name:
        raise ValueError("У команды должно быть непустое имя.")
    payload = {"name": name}
    if isinstance(description, str):
        payload["description"] = description
    return payload


def _commands_payload(
    commands: Sequence[BotCommand | tuple[str, str] | Mapping[str, Any]],
) -> list[dict[str, str]]:
    if len(commands) > 32:
        raise ValueError("Команд не может быть больше 32.")
    return [_command_payload(item) for item in commands]


def _message_body(
    *,
    text: str | None,
    attachments: Sequence[Any] | None,
    link: Any,
    notify: bool | None,
    text_format: str | None,
) -> dict[str, Any]:
    _check_format(text_format)
    body: dict[str, Any] = {}
    if text is not None:
        body["text"] = text
    if attachments is not None:
        body["attachments"] = [
            serialize_attachment(item) for item in attachments
        ]
    if link is not None:
        body["link"] = serialize_link(link)
    if notify is not None:
        body["notify"] = notify
    if text_format is not None:
        body["format"] = text_format
    return body


def _admin_payload(item: ChatAdmin | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(item, ChatAdmin):
        payload = item.to_dict()
    elif isinstance(item, Mapping):
        payload = dict(item)
    else:
        raise TypeError("Администратор должен быть ChatAdmin или словарём.")
    permissions = payload.get("permissions")
    if not isinstance(payload.get("user_id"), int) or isinstance(
        payload.get("user_id"),
        bool,
    ):
        raise ValueError("У администратора должен быть целый user_id.")
    if not isinstance(permissions, (list, tuple)) or not permissions:
        raise ValueError("У администратора нужен непустой список прав.")
    return payload


def get_me() -> ApiCall:
    """Собирает запрос ``GET /me``."""
    return ApiCall("GET", "/me")


def edit_me(
    *,
    first_name: str | None = None,
    last_name: str | None = None,
    name: str | None = None,
    description: str | None = None,
    commands: Sequence[BotCommand | tuple[str, str] | Mapping[str, Any]]
    | None = None,
    photo: Mapping[str, Any] | None = None,
) -> ApiCall:
    """Собирает запрос ``PATCH /me``.

    Args:
        first_name: Новое отображаемое имя.
        last_name: Новая фамилия.
        name: Устаревшее имя профиля.
        description: Новое описание.
        commands: Команды бота. Пустой список удаляет их.
        photo: Аватар: объект с ``url`` или ``token``.

    Returns:
        Подготовленный запрос.

    Raises:
        ValueError: Не передано ни одного поля.
    """
    body = _compact(
        {
            "first_name": first_name,
            "last_name": last_name,
            "name": name,
            "description": description,
            "photo": dict(photo) if photo is not None else None,
        },
    )
    if commands is not None:
        body["commands"] = _commands_payload(commands)
    if not body:
        raise ValueError("Нужно передать хотя бы одно поле профиля.")
    return ApiCall("PATCH", "/me", json_body=body)


def set_commands(
    commands: Sequence[BotCommand | tuple[str, str] | Mapping[str, Any]],
) -> ApiCall:
    """Собирает запрос ``PATCH /me/commands``.

    Args:
        commands: Новый список команд. Пустой список удаляет команды.

    Returns:
        Подготовленный запрос.
    """
    return ApiCall(
        "PATCH",
        "/me/commands",
        json_body={"commands": _commands_payload(commands)},
    )


def get_chat(chat_id: int) -> ApiCall:
    """Собирает запрос ``GET /chats/{chatId}``.

    Args:
        chat_id: Идентификатор чата или канала.

    Returns:
        Подготовленный запрос.
    """
    return ApiCall("GET", _chat_path(chat_id))


def edit_chat(
    chat_id: int,
    *,
    title: str | None = None,
    description: str | None = None,
    notify: bool | None = None,
    icon: Mapping[str, Any] | None = None,
    pin: str | None = None,
) -> ApiCall:
    """Собирает запрос ``PATCH /chats/{chatId}``.

    Args:
        chat_id: Идентификатор чата.
        title: Новое название.
        description: Новое описание.
        notify: Присылать ли уведомление об изменении.
        icon: Аватар: объект с ``url`` или ``token``.
        pin: Идентификатор сообщения, которое нужно закрепить.

    Returns:
        Подготовленный запрос.

    Raises:
        ValueError: Не передано ни одного поля.
    """
    body = _compact(
        {
            "title": title,
            "description": description,
            "notify": notify,
            "icon": dict(icon) if icon is not None else None,
            "pin": pin,
        },
    )
    if not body:
        raise ValueError("Нужно передать хотя бы одно поле чата.")
    return ApiCall("PATCH", _chat_path(chat_id), json_body=body)


def delete_chat(chat_id: int) -> ApiCall:
    """Собирает запрос ``DELETE /chats/{chatId}``.

    Args:
        chat_id: Идентификатор чата.

    Returns:
        Подготовленный запрос.
    """
    return ApiCall("DELETE", _chat_path(chat_id))


def send_action(chat_id: int, action: str) -> ApiCall:
    """Собирает запрос ``POST /chats/{chatId}/actions``.

    Args:
        chat_id: Идентификатор группового чата.
        action: Одно из значений ``SenderAction``.

    Returns:
        Подготовленный запрос.

    Raises:
        ValueError: Действие не поддерживается.
    """
    if action not in _ACTIONS:
        raise ValueError("Неизвестное действие бота.")
    return ApiCall(
        "POST",
        _chat_path(chat_id, "/actions"),
        json_body={"action": action},
    )


def get_pinned_message(chat_id: int) -> ApiCall:
    """Собирает запрос ``GET /chats/{chatId}/pin``.

    Args:
        chat_id: Идентификатор чата или канала.

    Returns:
        Подготовленный запрос.
    """
    return ApiCall("GET", _chat_path(chat_id, "/pin"))


def pin_message(
    chat_id: int,
    message_id: str,
    *,
    notify: bool | None = None,
) -> ApiCall:
    """Собирает запрос ``PUT /chats/{chatId}/pin``.

    Args:
        chat_id: Идентификатор чата или канала.
        message_id: Какое сообщение закрепить.
        notify: Присылать ли уведомление участникам.

    Returns:
        Подготовленный запрос.
    """
    body = _compact(
        {
            "message_id": _require_str("message_id", message_id),
            "notify": notify,
        },
    )
    return ApiCall("PUT", _chat_path(chat_id, "/pin"), json_body=body)


def unpin_message(chat_id: int) -> ApiCall:
    """Собирает запрос ``DELETE /chats/{chatId}/pin``.

    Args:
        chat_id: Идентификатор чата или канала.

    Returns:
        Подготовленный запрос.
    """
    return ApiCall("DELETE", _chat_path(chat_id, "/pin"))


def get_members(
    chat_id: int,
    *,
    user_ids: Sequence[int] | None = None,
    marker: int | None = None,
    count: int | None = None,
) -> ApiCall:
    """Собирает запрос ``GET /chats/{chatId}/members``.

    Args:
        chat_id: Идентификатор чата или канала.
        user_ids: Чьё членство запросить. Тогда пагинация не нужна.
        marker: Указатель страницы.
        count: Сколько участников вернуть.

    Returns:
        Подготовленный запрос.
    """
    params = _compact(
        {
            "user_ids": _csv(user_ids),
            "marker": _optional_int("marker", marker),
            "count": _positive("count", count),
        },
    )
    return ApiCall("GET", _chat_path(chat_id, "/members"), params)


def remove_member(
    chat_id: int,
    user_id: int,
    *,
    block: bool | None = None,
) -> ApiCall:
    """Собирает запрос ``DELETE /chats/{chatId}/members``.

    Args:
        chat_id: Идентификатор чата или канала.
        user_id: Кого удалить.
        block: Заблокировать пользователя в чате.

    Returns:
        Подготовленный запрос.
    """
    params = _compact(
        {
            "user_id": _require_int("user_id", user_id),
            "block": block,
        },
    )
    return ApiCall("DELETE", _chat_path(chat_id, "/members"), params)


def get_admins(chat_id: int) -> ApiCall:
    """Собирает запрос ``GET /chats/{chatId}/members/admins``.

    Args:
        chat_id: Идентификатор чата или канала.

    Returns:
        Подготовленный запрос.
    """
    return ApiCall("GET", _chat_path(chat_id, "/members/admins"))


def add_admins(
    chat_id: int,
    admins: Sequence[ChatAdmin | Mapping[str, Any]],
) -> ApiCall:
    """Собирает запрос ``POST /chats/{chatId}/members/admins``.

    Args:
        chat_id: Идентификатор чата или канала.
        admins: Кого назначить и с какими правами.

    Returns:
        Подготовленный запрос.

    Raises:
        ValueError: Список администраторов пуст.
    """
    if not admins:
        raise ValueError("Нужно передать хотя бы одного администратора.")
    return ApiCall(
        "POST",
        _chat_path(chat_id, "/members/admins"),
        json_body={"admins": [_admin_payload(item) for item in admins]},
    )


def remove_admin(chat_id: int, user_id: int) -> ApiCall:
    """Собирает запрос снятия прав администратора.

    Args:
        chat_id: Идентификатор чата или канала.
        user_id: У кого забрать права.

    Returns:
        Подготовленный запрос.
    """
    user = _require_int("user_id", user_id)
    return ApiCall(
        "DELETE",
        _chat_path(chat_id, f"/members/admins/{user}"),
    )


def get_membership(chat_id: int) -> ApiCall:
    """Собирает запрос ``GET /chats/{chatId}/members/me``.

    Args:
        chat_id: Идентификатор чата или канала.

    Returns:
        Подготовленный запрос.
    """
    return ApiCall("GET", _chat_path(chat_id, "/members/me"))


def leave_chat(chat_id: int) -> ApiCall:
    """Собирает запрос ``DELETE /chats/{chatId}/members/me``.

    Args:
        chat_id: Идентификатор чата или канала.

    Returns:
        Подготовленный запрос.
    """
    return ApiCall("DELETE", _chat_path(chat_id, "/members/me"))


def send_message(
    text: str | None = None,
    *,
    user_id: int | None = None,
    chat_id: int | None = None,
    attachments: Sequence[Any] | None = None,
    link: Any = None,
    notify: bool | None = None,
    text_format: str | None = None,
    disable_link_preview: bool | None = None,
) -> ApiCall:
    """Собирает запрос ``POST /messages``.

    Args:
        text: Текст до 4000 символов.
        user_id: Получатель в личном диалоге.
        chat_id: Чат или канал.
        attachments: Вложения, клавиатуры или словари API.
        link: Ответ или пересылка.
        notify: Присылать ли push. Для канала нужно ``True``.
        text_format: ``markdown`` или ``html``.
        disable_link_preview: Не строить превью ссылок.

    Returns:
        Подготовленный запрос.

    Raises:
        ValueError: Нет адресата или содержимого.
    """
    if user_id is None and chat_id is None:
        raise ValueError("Нужно указать user_id или chat_id.")
    body = _message_body(
        text=text,
        attachments=attachments,
        link=link,
        notify=notify,
        text_format=text_format,
    )
    if not body:
        raise ValueError(
            "Нужно передать текст, вложение или ссылку на сообщение.",
        )
    params = _compact(
        {
            "user_id": _optional_int("user_id", user_id),
            "chat_id": _optional_int("chat_id", chat_id),
            "disable_link_preview": disable_link_preview,
        },
    )
    return ApiCall("POST", "/messages", params, body)


def edit_message(
    message_id: str,
    *,
    text: str | None = None,
    attachments: Sequence[Any] | None = None,
    link: Any = None,
    notify: bool | None = None,
    text_format: str | None = None,
) -> ApiCall:
    """Собирает запрос ``PUT /messages``.

    Args:
        message_id: Какое сообщение изменить.
        text: Новый текст. Пустой список вложений удаляет их.
        attachments: Новые вложения.
        link: Новая связь с другим сообщением.
        notify: Присылать ли уведомление об изменении.
        text_format: ``markdown`` или ``html``.

    Returns:
        Подготовленный запрос.

    Raises:
        ValueError: Нечего изменять.
    """
    body = _message_body(
        text=text,
        attachments=attachments,
        link=link,
        notify=notify,
        text_format=text_format,
    )
    if not body:
        raise ValueError("Нужно передать хотя бы одно поле сообщения.")
    return ApiCall(
        "PUT",
        "/messages",
        {"message_id": _require_str("message_id", message_id)},
        body,
    )


def delete_message(message_id: str) -> ApiCall:
    """Собирает запрос ``DELETE /messages``.

    Args:
        message_id: Какое сообщение удалить.

    Returns:
        Подготовленный запрос.
    """
    return ApiCall(
        "DELETE",
        "/messages",
        {"message_id": _require_str("message_id", message_id)},
    )


def get_message(message_id: str) -> ApiCall:
    """Собирает запрос ``GET /messages/{messageId}``.

    Args:
        message_id: Идентификатор сообщения.

    Returns:
        Подготовленный запрос.
    """
    return ApiCall("GET", _message_id_path(message_id))


def get_messages(
    *,
    chat_id: int | None = None,
    message_ids: Sequence[str] | None = None,
    from_time: int | None = None,
    to_time: int | None = None,
    count: int | None = None,
) -> ApiCall:
    """Собирает запрос ``GET /messages``.

    Args:
        chat_id: Чат, из которого читать историю.
        message_ids: Конкретные сообщения вместо истории.
        from_time: Верхняя граница времени, Unix-время в мс.
        to_time: Нижняя граница времени, Unix-время в мс.
        count: Сколько сообщений вернуть.

    Returns:
        Подготовленный запрос.

    Raises:
        ValueError: Не задан ни чат, ни список сообщений.
    """
    if chat_id is None and not message_ids:
        raise ValueError("Нужно указать chat_id или message_ids.")
    params = _compact(
        {
            "chat_id": _optional_int("chat_id", chat_id),
            "message_ids": _csv(message_ids),
            "from": _positive("from_time", from_time),
            "to": _positive("to_time", to_time),
            "count": _positive("count", count),
        },
    )
    return ApiCall("GET", "/messages", params)


def answer_callback(
    callback_id: str,
    *,
    text: str | None = None,
    attachments: Sequence[Any] | None = None,
    link: Any = None,
    notify: bool | None = None,
    text_format: str | None = None,
    notification: str | None = None,
    disable_link_preview: bool | None = None,
) -> ApiCall:
    """Собирает запрос ``POST /answers``.

    Args:
        callback_id: Идентификатор нажатия.
        text: Новый текст исходного сообщения.
        attachments: Новые вложения исходного сообщения.
        link: Новая связь исходного сообщения.
        notify: Уведомлять ли об изменении сообщения.
        text_format: ``markdown`` или ``html``.
        notification: Короткое всплывающее уведомление.
        disable_link_preview: Не строить превью ссылок.

    Returns:
        Подготовленный запрос.

    Raises:
        ValueError: Нет ни нового сообщения, ни уведомления.
    """
    message = _message_body(
        text=text,
        attachments=attachments,
        link=link,
        notify=notify,
        text_format=text_format,
    )
    if not message and notification is None:
        raise ValueError(
            "Нужно передать уведомление или новое содержимое сообщения.",
        )
    body: dict[str, Any] = {}
    if message:
        body["message"] = message
    if notification is not None:
        body["notification"] = notification
    params = _compact(
        {
            "callback_id": _require_str("callback_id", callback_id),
            "disable_link_preview": disable_link_preview,
        },
    )
    return ApiCall("POST", "/answers", params, body)


def get_upload_url(upload_type: str) -> ApiCall:
    """Собирает запрос ``POST /uploads``.

    Args:
        upload_type: ``image``, ``video``, ``audio`` или ``file``.

    Returns:
        Подготовленный запрос.

    Raises:
        ValueError: Тип файла не поддерживается.
    """
    if upload_type not in _UPLOAD_TYPES:
        raise ValueError(
            "Тип загрузки должен быть image, video, audio или file.",
        )
    return ApiCall("POST", "/uploads", {"type": upload_type})


def send_comment(
    message_id: str,
    text: str,
    *,
    text_format: str | None = None,
) -> ApiCall:
    """Собирает запрос ``POST /messages/{messageId}/comments``.

    Args:
        message_id: Пост канала.
        text: Текст комментария.
        text_format: ``markdown`` или ``html``.

    Returns:
        Подготовленный запрос.
    """
    _check_format(text_format)
    if not isinstance(text, str):
        raise ValueError("Текст комментария должен быть строкой.")
    body: dict[str, Any] = {"text": text}
    if text_format is not None:
        body["format"] = text_format
    return ApiCall(
        "POST",
        _message_id_path(message_id, "/comments"),
        json_body=body,
    )


def get_comments(
    message_id: str,
    *,
    comment_ids: Sequence[str] | None = None,
    before: int | None = None,
    after: int | None = None,
    count: int | None = None,
) -> ApiCall:
    """Собирает запрос списка комментариев к посту.

    Args:
        message_id: Пост канала.
        comment_ids: Конкретные комментарии. Пагинация тогда не нужна.
        before: Верхняя граница времени, Unix-время в мс.
        after: Нижняя граница времени, Unix-время в мс.
        count: Сколько комментариев вернуть, от 1 до 100.

    Returns:
        Подготовленный запрос.
    """
    params = _compact(
        {
            "comment_ids": _csv(comment_ids),
            "before": _positive("before", before),
            "after": _positive("after", after),
            "count": _bounded("count", count, 1, 100),
        },
    )
    return ApiCall(
        "GET",
        _message_id_path(message_id, "/comments"),
        params,
    )


def get_comment(message_id: str, comment_id: str) -> ApiCall:
    """Собирает запрос одного комментария.

    Args:
        message_id: Пост канала.
        comment_id: Идентификатор комментария.

    Returns:
        Подготовленный запрос.
    """
    comment = quote(_require_str("comment_id", comment_id), safe="")
    return ApiCall(
        "GET",
        _message_id_path(message_id, f"/comments/{comment}"),
    )


def edit_comment(
    message_id: str,
    comment_id: str,
    *,
    text: str | None = None,
    link: Any = None,
    text_format: str | None = None,
) -> ApiCall:
    """Собирает запрос ``PUT /messages/{messageId}/comments``.

    Args:
        message_id: Пост канала.
        comment_id: Какой комментарий изменить.
        text: Новый текст.
        link: Новая связь. Пересылка комментариев не поддерживается.
        text_format: ``markdown`` или ``html``.

    Returns:
        Подготовленный запрос.

    Raises:
        ValueError: Нечего изменять.
    """
    body = _message_body(
        text=text,
        attachments=None,
        link=link,
        notify=None,
        text_format=text_format,
    )
    if not body:
        raise ValueError("Нужно передать хотя бы одно поле комментария.")
    return ApiCall(
        "PUT",
        _message_id_path(message_id, "/comments"),
        {"comment_id": _require_str("comment_id", comment_id)},
        body,
    )


def delete_comment(message_id: str, comment_id: str) -> ApiCall:
    """Собирает запрос ``DELETE /messages/{messageId}/comments``.

    Args:
        message_id: Пост канала.
        comment_id: Какой комментарий удалить.

    Returns:
        Подготовленный запрос.
    """
    return ApiCall(
        "DELETE",
        _message_id_path(message_id, "/comments"),
        {"comment_id": _require_str("comment_id", comment_id)},
    )


def get_subscriptions() -> ApiCall:
    """Собирает запрос ``GET /subscriptions``."""
    return ApiCall("GET", "/subscriptions")


def subscribe(
    url: str,
    *,
    update_types: Sequence[str] | None = None,
    secret: str | None = None,
) -> ApiCall:
    """Собирает запрос ``POST /subscriptions``.

    Args:
        url: HTTPS-адрес Webhook на порту 443.
        update_types: Какие события доставлять.
        secret: Секрет для заголовка ``X-Max-Bot-Api-Secret``.

    Returns:
        Подготовленный запрос.

    Raises:
        ValueError: URL или секрет не подходят под правила API.
    """
    if not isinstance(url, str) or not url.startswith("https://"):
        raise ValueError("URL подписки должен начинаться с https://.")
    body: dict[str, Any] = {"url": url}
    if update_types is not None:
        body["update_types"] = list(update_types)
    if secret is not None:
        if _SECRET.fullmatch(secret) is None:
            raise ValueError(
                "Секрет подписки: 5–256 символов A-Z, a-z, 0-9, _ и -.",
            )
        body["secret"] = secret
    return ApiCall("POST", "/subscriptions", json_body=body)


def unsubscribe(url: str) -> ApiCall:
    """Собирает запрос ``DELETE /subscriptions``.

    Args:
        url: Адрес подписки, которую нужно снять.

    Returns:
        Подготовленный запрос.
    """
    if not isinstance(url, str) or not url:
        raise ValueError("Нужно передать URL подписки.")
    return ApiCall("DELETE", "/subscriptions", {"url": url})


def get_updates(
    *,
    marker: int | None = None,
    limit: int | None = None,
    timeout: int | None = None,
    types: Sequence[str] | None = None,
) -> ApiCall:
    """Собирает запрос ``GET /updates``.

    Args:
        marker: Указатель из прошлого ответа. Без него сервер
            вернёт только последнее событие.
        limit: Сколько событий вернуть, от 1 до 1000.
        timeout: Долгий опрос в секундах, от 0 до 90.
        types: Какие типы событий принимать.

    Returns:
        Подготовленный запрос. Тайм-аут HTTP больше тайм-аута опроса.
    """
    if timeout is None:
        poll_timeout: int | None = 30
    else:
        poll_timeout = _bounded("timeout", timeout, 0, 90)
    params = _compact(
        {
            "marker": _optional_int("marker", marker),
            "limit": _bounded("limit", limit, 1, 1000),
            "timeout": None if timeout is None else poll_timeout,
            "types": _csv(types),
        },
    )
    read_timeout = float(poll_timeout or 0) + 15.0
    return ApiCall("GET", "/updates", params, timeout=read_timeout)
