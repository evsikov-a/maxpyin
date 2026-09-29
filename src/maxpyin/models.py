"""Модели ответов Bot API MAX.

Неизвестные поля JSON сохраняются в ``extra``, чтобы новые поля
сервера не ломали разбор.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, TypeVar

from .exceptions import MaxApiError

T = TypeVar("T")


class SenderAction:
    """Действие бота в групповом чате. Метод ``send_action``."""

    TYPING_ON = "typing_on"
    SENDING_PHOTO = "sending_photo"
    SENDING_VIDEO = "sending_video"
    SENDING_AUDIO = "sending_audio"
    SENDING_FILE = "sending_file"


class UpdateType:
    """Частые значения поля ``update_type``."""

    MESSAGE_CREATED = "message_created"
    MESSAGE_CALLBACK = "message_callback"
    MESSAGE_EDITED = "message_edited"
    MESSAGE_REMOVED = "message_removed"
    BOT_STARTED = "bot_started"
    BOT_ADDED = "bot_added"
    BOT_REMOVED = "bot_removed"
    COMMENT_CREATED = "comment_created"
    COMMENT_EDITED = "comment_edited"
    COMMENT_REMOVED = "comment_removed"


class ChatPermission:
    """Права администратора группового чата или канала."""

    READ_ALL_MESSAGES = "read_all_messages"
    ADD_REMOVE_MEMBERS = "add_remove_members"
    ADD_ADMINS = "add_admins"
    CHANGE_CHAT_INFO = "change_chat_info"
    PIN_MESSAGE = "pin_message"
    WRITE = "write"
    CAN_CALL = "can_call"
    EDIT_LINK = "edit_link"
    POST_EDIT_DELETE_MESSAGE = "post_edit_delete_message"
    EDIT_MESSAGE = "edit_message"
    DELETE_MESSAGE = "delete_message"
    EDIT = "edit"
    DELETE = "delete"


def _split(
    data: Mapping[str, Any],
    names: tuple[str, ...],
) -> tuple[dict[str, Any], dict[str, Any]]:
    allowed = set(names)
    known: dict[str, Any] = {}
    extra: dict[str, Any] = {}
    for key, value in data.items():
        if key in allowed:
            known[key] = value
        else:
            extra[key] = value
    return known, extra


def _build(
    cls: type[T],
    data: Mapping[str, Any],
    names: tuple[str, ...],
    converters: dict[str, Any] | None = None,
) -> T:
    known, extra = _split(data, names)
    for key, converter in (converters or {}).items():
        if key in known:
            known[key] = converter(known[key])
    return cls(extra=extra, **known)  # type: ignore[call-arg]


def _optional_model(model: type[T], value: Any) -> T | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        return None
    return model.from_dict(value)  # type: ignore[attr-defined]


def _dict_tuple(value: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, dict))


def _string_tuple(value: Any) -> tuple[str, ...] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def _dict_or_none(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    return None


def _marker(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


@dataclass
class BotCommand:
    """Команда бота, которую пользователь видит после символа ``/``.

    Attributes:
        name: Имя команды без ведущего слэша.
        description: Подсказка рядом с командой.
    """

    name: str
    description: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BotCommand:
        """Собирает команду из объекта JSON.

        Args:
            data: Объект команды.

        Returns:
            Команда бота.

        Raises:
            TypeError: ``data`` не является объектом.
        """
        if not isinstance(data, Mapping):
            raise TypeError("Ожидался объект команды.")
        name = data.get("name")
        description = data.get("description")
        return cls(
            name=name if isinstance(name, str) else "",
            description=(
                description if isinstance(description, str) else None
            ),
        )

    def to_dict(self) -> dict[str, str]:
        """Возвращает команду в теле запроса.

        Returns:
            Объект с именем и, если задано, описанием.
        """
        payload = {"name": self.name}
        if self.description is not None:
            payload["description"] = self.description
        return payload


def _commands(value: Any) -> tuple[BotCommand, ...] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        return ()
    return tuple(
        BotCommand.from_dict(item)
        for item in value
        if isinstance(item, Mapping)
    )


@dataclass
class User:
    """Пользователь или бот MAX.

    Attributes:
        user_id: Идентификатор.
        first_name: Отображаемое имя.
        last_name: Фамилия. У бота обычно пусто.
        username: Публичный ник. Может отсутствовать.
        is_bot: Истина, если это бот.
        last_activity_time: Последняя активность, Unix-время в мс.
        name: Устаревшее имя профиля.
        description: Текст «о себе» или описание бота.
        avatar_url: Уменьшенный аватар.
        full_avatar_url: Аватар полного размера.
        commands: Команды бота. Приходят в ответе ``GET /me``.
        extra: Поля ответа, которых нет в модели.
    """

    user_id: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    is_bot: bool | None = None
    last_activity_time: int | None = None
    name: str | None = None
    description: str | None = None
    avatar_url: str | None = None
    full_avatar_url: str | None = None
    commands: tuple[BotCommand, ...] | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> User:
        """Собирает профиль из объекта JSON.

        Args:
            data: Объект пользователя или бота.

        Returns:
            Разобранный профиль.

        Raises:
            TypeError: ``data`` не является объектом.
        """
        if not isinstance(data, Mapping):
            raise TypeError("Ожидался объект пользователя.")
        return _build(
            cls,
            data,
            (
                "user_id",
                "first_name",
                "last_name",
                "username",
                "is_bot",
                "last_activity_time",
                "name",
                "description",
                "avatar_url",
                "full_avatar_url",
                "commands",
            ),
            {"commands": _commands},
        )


@dataclass
class Image:
    """Картинка: аватар чата или другое изображение API.

    Attributes:
        url: Адрес изображения.
        extra: Неизвестные поля.
    """

    url: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Image:
        """Собирает изображение из объекта JSON.

        Args:
            data: Объект изображения.

        Returns:
            Разобранное изображение.

        Raises:
            TypeError: ``data`` не является объектом.
        """
        if not isinstance(data, Mapping):
            raise TypeError("Ожидался объект изображения.")
        return _build(cls, data, ("url",))


@dataclass
class Recipient:
    """Получатель сообщения: диалог, чат или канал.

    Attributes:
        chat_id: Идентификатор чата.
        chat_type: ``dialog``, ``chat`` или ``channel``.
        user_id: Идентификатор пользователя в диалоге.
        extra: Неизвестные поля.
    """

    chat_id: int | None = None
    chat_type: str | None = None
    user_id: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Recipient:
        """Собирает получателя из объекта JSON.

        Args:
            data: Объект получателя.

        Returns:
            Разобранный получатель.

        Raises:
            TypeError: ``data`` не является объектом.
        """
        if not isinstance(data, Mapping):
            raise TypeError("Ожидался объект получателя.")
        return _build(cls, data, ("chat_id", "chat_type", "user_id"))


@dataclass
class MessageBody:
    """Текст и вложения сообщения.

    Attributes:
        mid: Идентификатор сообщения.
        seq: Порядковый номер в чате.
        text: Текст. Может быть пустым, если есть вложения.
        attachments: Вложения как словари API.
        markup: Разметка текста как словари API.
        extra: Неизвестные поля.
    """

    mid: str | None = None
    seq: int | None = None
    text: str | None = None
    attachments: tuple[dict[str, Any], ...] = ()
    markup: tuple[dict[str, Any], ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> MessageBody:
        """Собирает тело сообщения из объекта JSON.

        Args:
            data: Объект тела сообщения.

        Returns:
            Разобранное тело.

        Raises:
            TypeError: ``data`` не является объектом.
        """
        if not isinstance(data, Mapping):
            raise TypeError("Ожидалось тело сообщения.")
        return _build(
            cls,
            data,
            ("mid", "seq", "text", "attachments", "markup"),
            {"attachments": _dict_tuple, "markup": _dict_tuple},
        )


@dataclass
class LinkedMessage:
    """Ответ или пересланное сообщение.

    Attributes:
        type: ``reply`` или ``forward``.
        sender: Автор исходного сообщения.
        chat_id: Чат, откуда переслали сообщение.
        message: Тело исходного сообщения.
        extra: Неизвестные поля.
    """

    type: str | None = None
    sender: User | None = None
    chat_id: int | None = None
    message: MessageBody | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> LinkedMessage:
        """Собирает связь сообщений из объекта JSON.

        Args:
            data: Объект связи.

        Returns:
            Разобранная связь.

        Raises:
            TypeError: ``data`` не является объектом.
        """
        if not isinstance(data, Mapping):
            raise TypeError("Ожидалась ссылка на сообщение.")
        return _build(
            cls,
            data,
            ("type", "sender", "chat_id", "message"),
            {
                "sender": lambda value: _optional_model(User, value),
                "message": lambda value: _optional_model(
                    MessageBody,
                    value,
                ),
            },
        )


@dataclass
class MessageLink:
    """Ссылка, которую бот передаёт при отправке ответа или пересылки.

    Attributes:
        type: ``reply`` или ``forward``.
        mid: Идентификатор исходного сообщения.
    """

    type: str
    mid: str

    def to_dict(self) -> dict[str, str]:
        """Возвращает объект ``NewMessageLink``.

        Returns:
            Словарь для поля ``link``.
        """
        return {"type": self.type, "mid": self.mid}


@dataclass
class Message:
    """Сообщение в чате или пост в канале.

    Attributes:
        sender: Автор. Может отсутствовать у канала.
        recipient: Куда доставлено сообщение.
        timestamp: Время создания, Unix-время в мс.
        link: Ответ или пересылка.
        body: Текст и вложения.
        url: Публичная ссылка на пост канала.
        stat: Статистика поста, если сервер её прислал.
        extra: Неизвестные поля.
    """

    sender: User | None = None
    recipient: Recipient | None = None
    timestamp: int | None = None
    link: LinkedMessage | None = None
    body: MessageBody | None = None
    url: str | None = None
    stat: dict[str, Any] | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Message:
        """Собирает сообщение из объекта JSON.

        Args:
            data: Объект сообщения.

        Returns:
            Разобранное сообщение.

        Raises:
            TypeError: ``data`` не является объектом.
        """
        if not isinstance(data, Mapping):
            raise TypeError("Ожидался объект сообщения.")
        return _build(
            cls,
            data,
            (
                "sender",
                "recipient",
                "timestamp",
                "link",
                "body",
                "url",
                "stat",
            ),
            {
                "sender": lambda value: _optional_model(User, value),
                "recipient": lambda value: _optional_model(
                    Recipient,
                    value,
                ),
                "link": lambda value: _optional_model(
                    LinkedMessage,
                    value,
                ),
                "body": lambda value: _optional_model(MessageBody, value),
                "stat": _dict_or_none,
            },
        )


@dataclass
class Callback:
    """Нажатие кнопки ``callback``.

    Attributes:
        callback_id: Идентификатор для ``answer_callback``.
        payload: Значение, заданное на кнопке.
        timestamp: Время нажатия, Unix-время в мс.
        user: Кто нажал кнопку.
        extra: Неизвестные поля.
    """

    callback_id: str | None = None
    payload: str | None = None
    timestamp: int | None = None
    user: User | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Callback:
        """Собирает нажатие из объекта JSON.

        Args:
            data: Объект callback.

        Returns:
            Разобранное нажатие.

        Raises:
            TypeError: ``data`` не является объектом.
        """
        if not isinstance(data, Mapping):
            raise TypeError("Ожидался объект callback.")
        return _build(
            cls,
            data,
            ("callback_id", "payload", "timestamp", "user"),
            {"user": lambda value: _optional_model(User, value)},
        )


@dataclass
class Update:
    """Событие бота из long polling или Webhook.

    Attributes:
        update_type: Тип события, например ``message_created``.
        timestamp: Время события, Unix-время в мс.
        message: Сообщение, если событие его содержит.
        callback: Нажатие кнопки для ``message_callback``.
        user: Пользователь события, например при ``bot_started``.
        chat_id: Чат события, если он пришёл отдельным полем.
        user_id: Пользователь, если сервер прислал только идентификатор.
        user_locale: Язык пользователя, IETF BCP 47.
        payload: Стартовые данные ``bot_started``.
        extra: Остальные поля конкретного события.
    """

    update_type: str = ""
    timestamp: int | None = None
    message: Message | None = None
    callback: Callback | None = None
    user: User | None = None
    chat_id: int | None = None
    user_id: int | None = None
    user_locale: str | None = None
    payload: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Update:
        """Собирает событие из объекта JSON.

        Args:
            data: Объект Update.

        Returns:
            Разобранное событие.

        Raises:
            TypeError: ``data`` не является объектом.
        """
        if not isinstance(data, Mapping):
            raise TypeError("Ожидался объект обновления.")
        return _build(
            cls,
            data,
            (
                "update_type",
                "timestamp",
                "message",
                "callback",
                "user",
                "chat_id",
                "user_id",
                "user_locale",
                "payload",
            ),
            {
                "message": lambda value: _optional_model(Message, value),
                "callback": lambda value: _optional_model(Callback, value),
                "user": lambda value: _optional_model(User, value),
            },
        )


def parse_update(data: Mapping[str, Any]) -> Update:
    """Разбирает тело Webhook или элемент списка ``updates``.

    Args:
        data: JSON-объект события.

    Returns:
        Разобранное событие.

    Raises:
        TypeError: ``data`` не является объектом.
    """
    return Update.from_dict(data)


@dataclass
class UpdatePage:
    """Страница long polling.

    Attributes:
        updates: События этой страницы.
        marker: Указатель для следующего запроса.
        extra: Неизвестные поля.
    """

    updates: tuple[Update, ...] = ()
    marker: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> UpdatePage:
        """Собирает страницу обновлений из объекта JSON.

        Args:
            data: Ответ ``GET /updates``.

        Returns:
            Страница событий.

        Raises:
            TypeError: ``data`` не является объектом.
        """
        if not isinstance(data, Mapping):
            raise TypeError("Ожидалась страница обновлений.")
        raw = data.get("updates")
        updates: tuple[Update, ...] = ()
        if isinstance(raw, list):
            updates = tuple(
                Update.from_dict(item)
                for item in raw
                if isinstance(item, Mapping)
            )
        known, extra = _split(data, ("updates", "marker"))
        return cls(
            updates=updates,
            marker=_marker(known.get("marker")),
            extra=extra,
        )


@dataclass
class Chat:
    """Групповой чат, канал или диалог.

    Attributes:
        chat_id: Идентификатор чата.
        type: ``chat``, ``channel`` или ``dialog``.
        status: ``active``, ``removed``, ``left`` или ``closed``.
        title: Название. У диалога может быть пустым.
        icon: Аватар чата.
        last_event_time: Время последнего события, мс.
        participants_count: Число участников.
        owner_id: Владелец чата или канала.
        participants: Активность участников, если сервер её прислал.
        is_public: Открыт ли чат или канал.
        link: Публичная ссылка.
        description: Описание.
        dialog_with_user: Собеседник, только для диалога.
        messages_count: Число сообщений или постов.
        pinned_message: Закреплённое сообщение.
        extra: Неизвестные поля.
    """

    chat_id: int | None = None
    type: str | None = None
    status: str | None = None
    title: str | None = None
    icon: Image | None = None
    last_event_time: int | None = None
    participants_count: int | None = None
    owner_id: int | None = None
    participants: dict[str, Any] | None = None
    is_public: bool | None = None
    link: str | None = None
    description: str | None = None
    dialog_with_user: User | None = None
    messages_count: int | None = None
    pinned_message: Message | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Chat:
        """Собирает чат из объекта JSON.

        Args:
            data: Объект чата.

        Returns:
            Разобранный чат.

        Raises:
            TypeError: ``data`` не является объектом.
        """
        if not isinstance(data, Mapping):
            raise TypeError("Ожидался объект чата.")
        return _build(
            cls,
            data,
            (
                "chat_id",
                "type",
                "status",
                "title",
                "icon",
                "last_event_time",
                "participants_count",
                "owner_id",
                "participants",
                "is_public",
                "link",
                "description",
                "dialog_with_user",
                "messages_count",
                "pinned_message",
            ),
            {
                "icon": lambda value: _optional_model(Image, value),
                "participants": (
                    lambda value: value if isinstance(value, dict) else None
                ),
                "dialog_with_user": lambda value: _optional_model(
                    User,
                    value,
                ),
                "pinned_message": lambda value: _optional_model(
                    Message,
                    value,
                ),
            },
        )


@dataclass
class ChatMember:
    """Участник группового чата или канала.

    Attributes:
        user_id: Идентификатор участника.
        first_name: Имя.
        last_name: Фамилия.
        username: Ник.
        is_bot: Истина, если участник — бот.
        last_activity_time: Активность в MAX, мс.
        name: Устаревшее имя.
        description: Описание профиля.
        avatar_url: Уменьшенный аватар.
        full_avatar_url: Полный аватар.
        last_access_time: Последняя активность в этом чате, мс.
        is_owner: Владелец чата или канала.
        is_admin: Администратор.
        join_time: Когда вступил, Unix-время.
        permissions: Права, если участник администратор.
        extra: Неизвестные поля.
    """

    user_id: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    is_bot: bool | None = None
    last_activity_time: int | None = None
    name: str | None = None
    description: str | None = None
    avatar_url: str | None = None
    full_avatar_url: str | None = None
    last_access_time: int | None = None
    is_owner: bool | None = None
    is_admin: bool | None = None
    join_time: int | None = None
    permissions: tuple[str, ...] | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ChatMember:
        """Собирает участника из объекта JSON.

        Args:
            data: Объект участника.

        Returns:
            Разобранный участник.

        Raises:
            TypeError: ``data`` не является объектом.
        """
        if not isinstance(data, Mapping):
            raise TypeError("Ожидался объект участника.")
        return _build(
            cls,
            data,
            (
                "user_id",
                "first_name",
                "last_name",
                "username",
                "is_bot",
                "last_activity_time",
                "name",
                "description",
                "avatar_url",
                "full_avatar_url",
                "last_access_time",
                "is_owner",
                "is_admin",
                "join_time",
                "permissions",
            ),
            {"permissions": _string_tuple},
        )


@dataclass
class ChatMemberPage:
    """Страница участников чата.

    Attributes:
        members: Участники этой страницы.
        marker: Указатель следующей страницы.
        extra: Неизвестные поля.
    """

    members: tuple[ChatMember, ...] = ()
    marker: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ChatMemberPage:
        """Собирает страницу участников из объекта JSON.

        Args:
            data: Ответ метода участников.

        Returns:
            Страница участников.

        Raises:
            TypeError: ``data`` не является объектом.
        """
        if not isinstance(data, Mapping):
            raise TypeError("Ожидался список участников.")
        raw = data.get("members")
        members: tuple[ChatMember, ...] = ()
        if isinstance(raw, list):
            members = tuple(
                ChatMember.from_dict(item)
                for item in raw
                if isinstance(item, Mapping)
            )
        _, extra = _split(data, ("members", "marker"))
        return cls(
            members=members,
            marker=_marker(data.get("marker")),
            extra=extra,
        )


@dataclass
class ChatAdmin:
    """Назначение администратора чата или канала.

    Attributes:
        user_id: Кого назначить.
        permissions: Набор прав из ``ChatPermission``.
        alias: Подпись администратора в чате.
    """

    user_id: int
    permissions: tuple[str, ...]
    alias: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Возвращает назначение в теле запроса.

        Returns:
            Объект администратора.
        """
        payload: dict[str, Any] = {
            "user_id": self.user_id,
            "permissions": list(self.permissions),
        }
        if self.alias is not None:
            payload["alias"] = self.alias
        return payload


@dataclass
class MessagePage:
    """Список сообщений чата.

    Attributes:
        messages: Сообщения.
        extra: Неизвестные поля.
    """

    messages: tuple[Message, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> MessagePage:
        """Собирает список сообщений из объекта JSON.

        Args:
            data: Ответ ``GET /messages``.

        Returns:
            Список сообщений.

        Raises:
            TypeError: ``data`` не является объектом.
        """
        if not isinstance(data, Mapping):
            raise TypeError("Ожидался список сообщений.")
        raw = data.get("messages")
        messages: tuple[Message, ...] = ()
        if isinstance(raw, list):
            messages = tuple(
                Message.from_dict(item)
                for item in raw
                if isinstance(item, Mapping)
            )
        _, extra = _split(data, ("messages",))
        return cls(messages=messages, extra=extra)


@dataclass
class CommentPage:
    """Страница комментариев к посту канала.

    Attributes:
        comments: Комментарии страницы.
        marker: Указатель следующей страницы.
        extra: Неизвестные поля.
    """

    comments: tuple[Message, ...] = ()
    marker: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CommentPage:
        """Собирает комментарии из объекта JSON.

        Сервер может положить список в ``comments`` или ``messages``.

        Args:
            data: Ответ ``GET /messages/{messageId}/comments``.

        Returns:
            Страница комментариев.

        Raises:
            TypeError: ``data`` не является объектом.
        """
        if not isinstance(data, Mapping):
            raise TypeError("Ожидался список комментариев.")
        raw = data.get("comments")
        if not isinstance(raw, list):
            raw = data.get("messages")
        comments: tuple[Message, ...] = ()
        if isinstance(raw, list):
            comments = tuple(
                Message.from_dict(item)
                for item in raw
                if isinstance(item, Mapping)
            )
        _, extra = _split(data, ("comments", "messages", "marker"))
        return cls(
            comments=comments,
            marker=_marker(data.get("marker")),
            extra=extra,
        )


@dataclass
class Subscription:
    """Webhook-подписка бота.

    Attributes:
        url: Адрес endpoint.
        time: Когда подписка создана, Unix-время.
        update_types: Типы событий, которые она принимает.
        extra: Неизвестные поля.
    """

    url: str | None = None
    time: int | None = None
    update_types: tuple[str, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Subscription:
        """Собирает подписку из объекта JSON.

        Args:
            data: Объект подписки.

        Returns:
            Разобранная подписка.

        Raises:
            TypeError: ``data`` не является объектом.
        """
        if not isinstance(data, Mapping):
            raise TypeError("Ожидался объект подписки.")
        return _build(
            cls,
            data,
            ("url", "time", "update_types"),
            {
                "update_types": lambda value: _string_tuple(value) or (),
            },
        )


@dataclass
class SubscriptionList:
    """Все текущие Webhook-подписки бота.

    Attributes:
        subscriptions: Подписки.
        extra: Неизвестные поля.
    """

    subscriptions: tuple[Subscription, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SubscriptionList:
        """Собирает список подписок из объекта JSON.

        Args:
            data: Ответ ``GET /subscriptions``.

        Returns:
            Список подписок.

        Raises:
            TypeError: ``data`` не является объектом.
        """
        if not isinstance(data, Mapping):
            raise TypeError("Ожидался список подписок.")
        raw = data.get("subscriptions")
        items: tuple[Subscription, ...] = ()
        if isinstance(raw, list):
            items = tuple(
                Subscription.from_dict(item)
                for item in raw
                if isinstance(item, Mapping)
            )
        _, extra = _split(data, ("subscriptions",))
        return cls(subscriptions=items, extra=extra)


@dataclass
class SuccessResult:
    """Результат метода, который сообщает только об успехе.

    Attributes:
        success: Истина, если сервер подтвердил операцию.
        message: Текст ошибки, если он есть при успехе.
        extra: Остальные поля ответа.
    """

    success: bool = True
    message: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> SuccessResult:
        """Собирает результат из объекта JSON или пустого ответа.

        Args:
            data: Тело ответа. ``None``, если тела не было.

        Returns:
            Результат операции.
        """
        if not isinstance(data, Mapping) or not data:
            return cls(success=True)
        message = data.get("message")
        _, extra = _split(data, ("success", "message"))
        return cls(
            success=bool(data.get("success", True)),
            message=message if isinstance(message, str) else None,
            extra=extra,
        )


@dataclass
class UploadSlot:
    """Адрес, на который нужно отправить байты файла.

    Attributes:
        url: URL одноразовой загрузки.
        token: Токен, если сервер выдал его сразу.
        extra: Неизвестные поля.
    """

    url: str
    token: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> UploadSlot:
        """Собирает слот загрузки из объекта JSON.

        Args:
            data: Ответ ``POST /uploads``.

        Returns:
            Слот загрузки.

        Raises:
            TypeError: В ответе нет строкового ``url``.
        """
        url = data.get("url") if isinstance(data, Mapping) else None
        if not isinstance(url, str):
            raise TypeError("Ожидался URL загрузки.")
        known, extra = _split(data, ("url", "token"))
        token = known.get("token")
        return cls(
            url=known["url"],
            token=token if isinstance(token, str) else None,
            extra=extra,
        )


@dataclass
class UploadResult:
    """Ответ сервера после отправки байтов файла.

    Attributes:
        token: Токен вложения для видео, аудио и файла.
        photos: Токены изображений в формате ответа загрузки.
        extra: Неизвестные поля.
    """

    token: str | None = None
    photos: dict[str, Any] | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> UploadResult:
        """Собирает результат загрузки из объекта JSON.

        Args:
            data: Тело ответа сервера файлов. ``None``, если тела нет.

        Returns:
            Результат загрузки.

        Raises:
            TypeError: Тело не является объектом JSON.
        """
        if data is None:
            return cls()
        if not isinstance(data, Mapping):
            raise TypeError("Ожидался объект результата загрузки.")
        known, extra = _split(data, ("token", "photos"))
        token = known.get("token")
        photos = known.get("photos")
        return cls(
            token=token if isinstance(token, str) else None,
            photos=photos if isinstance(photos, dict) else None,
            extra=extra,
        )

    @property
    def media_token(self) -> str | None:
        """Возвращает токен файла или первого загруженного изображения.

        Returns:
            Токен или ``None``, если сервер его не прислал.
        """
        if self.token:
            return self.token
        if not self.photos:
            return None
        for value in self.photos.values():
            if isinstance(value, dict):
                token = value.get("token")
                if isinstance(token, str) and token:
                    return token
        return None

    def as_attachment(self, upload_type: str) -> dict[str, Any]:
        """Собирает вложение для ``send_message`` или ``edit_message``.

        Args:
            upload_type: ``image``, ``video``, ``audio`` или ``file``.

        Returns:
            Объект вложения с токеном.

        Raises:
            ValueError: Тип не поддерживается или токена нет.
        """
        if upload_type not in {"image", "video", "audio", "file"}:
            raise ValueError(
                "Тип вложения должен быть image, video, audio или file.",
            )
        if upload_type == "image" and self.photos:
            return {"type": "image", "payload": {"photos": self.photos}}
        token = self.media_token
        if not token:
            raise ValueError("В ответе загрузки нет токена файла.")
        return {"type": upload_type, "payload": {"token": token}}


def _expect_dict(data: Any, what: str) -> Mapping[str, Any]:
    if not isinstance(data, Mapping):
        raise MaxApiError(
            f"Ожидался объект «{what}».",
            status_code=200,
            payload=data,
        )
    return data


def as_user(data: Any) -> User:
    """Достаёт профиль бота или пользователя из ответа.

    Args:
        data: Тело ответа.

    Returns:
        Профиль.

    Raises:
        MaxApiError: Тело не является объектом.
    """
    return User.from_dict(_expect_dict(data, "пользователь"))


def as_chat(data: Any) -> Chat:
    """Достаёт чат из ответа.

    Args:
        data: Тело ответа.

    Returns:
        Чат.

    Raises:
        MaxApiError: Тело не является объектом.
    """
    return Chat.from_dict(_expect_dict(data, "чат"))


def as_message(data: Any) -> Message:
    """Достаёт сообщение из ответа или из обёртки ``message``.

    Args:
        data: Тело ответа.

    Returns:
        Сообщение.

    Raises:
        MaxApiError: Сообщения в ответе нет.
    """
    payload = _expect_dict(data, "сообщение")
    if (
        "message" in payload
        and "body" not in payload
        and "recipient" not in payload
    ):
        nested = payload.get("message")
        if not isinstance(nested, Mapping):
            raise MaxApiError(
                "В ответе нет объекта сообщения.",
                status_code=200,
                payload=data,
            )
        payload = nested
    return Message.from_dict(payload)


def as_optional_message(data: Any) -> Message | None:
    """Достаёт сообщение, если оно есть.

    Args:
        data: Тело ответа с полем ``message``.

    Returns:
        Сообщение или ``None``, если закрепления нет.

    Raises:
        MaxApiError: Тело не является объектом.
    """
    payload = _expect_dict(data, "сообщение")
    if "message" in payload and payload.get("message") is None:
        return None
    return as_message(payload)


def as_success(data: Any) -> SuccessResult:
    """Превращает ответ об успехе в ``SuccessResult``.

    Args:
        data: Тело ответа или ``None``.

    Returns:
        Результат операции.

    Raises:
        MaxApiError: Тело не объект и не пустое.
    """
    if data is None:
        return SuccessResult(success=True)
    if not isinstance(data, Mapping):
        raise MaxApiError(
            "Ожидался объект результата.",
            status_code=200,
            payload=data,
        )
    return SuccessResult.from_dict(data)


def as_member(data: Any) -> ChatMember:
    """Достаёт членство бота из ответа.

    Args:
        data: Тело ответа.

    Returns:
        Участник.

    Raises:
        MaxApiError: Тело не является объектом.
    """
    return ChatMember.from_dict(_expect_dict(data, "участник"))


def as_member_page(data: Any) -> ChatMemberPage:
    """Достаёт страницу участников из ответа.

    Args:
        data: Тело ответа.

    Returns:
        Страница участников.

    Raises:
        MaxApiError: Тело не является объектом.
    """
    return ChatMemberPage.from_dict(_expect_dict(data, "участники"))


def as_message_page(data: Any) -> MessagePage:
    """Достаёт список сообщений из ответа.

    Args:
        data: Тело ответа.

    Returns:
        Список сообщений.

    Raises:
        MaxApiError: Тело не является объектом.
    """
    return MessagePage.from_dict(_expect_dict(data, "сообщения"))


def as_update_page(data: Any) -> UpdatePage:
    """Достаёт страницу событий из ответа.

    Args:
        data: Тело ответа ``GET /updates``.

    Returns:
        Страница событий.

    Raises:
        MaxApiError: Тело не является объектом.
    """
    return UpdatePage.from_dict(_expect_dict(data, "обновления"))


def as_commands(data: Any) -> tuple[BotCommand, ...]:
    """Достаёт команды бота из ответа.

    Args:
        data: Объект с полем ``commands`` или сам список.

    Returns:
        Команды.

    Raises:
        MaxApiError: Форма ответа неожиданная.
    """
    if isinstance(data, list):
        items = data
    elif isinstance(data, Mapping):
        raw = data.get("commands")
        items = raw if isinstance(raw, list) else []
    else:
        raise MaxApiError(
            "Ожидался список команд.",
            status_code=200,
            payload=data,
        )
    return tuple(
        BotCommand.from_dict(item)
        for item in items
        if isinstance(item, Mapping)
    )


def as_comment_page(data: Any) -> CommentPage:
    """Достаёт страницу комментариев из ответа.

    Args:
        data: Тело ответа.

    Returns:
        Страница комментариев.

    Raises:
        MaxApiError: Тело не является объектом.
    """
    return CommentPage.from_dict(_expect_dict(data, "комментарии"))


def as_subscriptions(data: Any) -> SubscriptionList:
    """Достаёт подписки из ответа.

    Args:
        data: Тело ответа.

    Returns:
        Список подписок.

    Raises:
        MaxApiError: Тело не является объектом.
    """
    return SubscriptionList.from_dict(_expect_dict(data, "подписки"))


def as_upload_slot(data: Any) -> UploadSlot:
    """Достаёт URL загрузки из ответа.

    Args:
        data: Тело ответа ``POST /uploads``.

    Returns:
        Слот загрузки.

    Raises:
        MaxApiError: В ответе нет URL.
    """
    try:
        return UploadSlot.from_dict(data)
    except TypeError as exc:
        raise MaxApiError(
            "Сервер не вернул URL загрузки.",
            status_code=200,
            payload=data,
        ) from exc
