"""Построитель встроенной клавиатуры сообщения MAX."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


def serialize_attachment(item: Any) -> dict[str, Any]:
    """Превращает клавиатуру, кнопку или словарь во вложение API.

    Args:
        item: Словарь вложения или объект с методом ``to_dict``.

    Returns:
        Объект вложения для поля ``attachments``.

    Raises:
        TypeError: Объект нельзя представить вложением.
    """
    if isinstance(item, dict):
        return item
    to_dict = getattr(item, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
        if isinstance(payload, dict):
            return payload
    raise TypeError(
        "Вложение должно быть словарём или объектом с методом to_dict.",
    )


def serialize_link(link: Any) -> dict[str, Any]:
    """Превращает ссылку на сообщение в объект ``NewMessageLink``.

    Args:
        link: Словарь ссылки или объект с методом ``to_dict``.

    Returns:
        Объект ссылки для поля ``link``.

    Raises:
        TypeError: Объект нельзя представить ссылкой.
    """
    if isinstance(link, dict):
        return link
    to_dict = getattr(link, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
        if isinstance(payload, dict):
            return payload
    raise TypeError(
        "Ссылка на сообщение должна быть словарём или MessageLink.",
    )


@dataclass(frozen=True)
class CallbackButton:
    """Кнопка, которая присылает боту нажатие с заданным payload.

    Attributes:
        text: Подпись на кнопке.
        payload: Строка до 1024 байт, её вернёт событие
            ``message_callback``.
    """

    text: str
    payload: str

    def to_dict(self) -> dict[str, str]:
        """Возвращает кнопку в формате API.

        Returns:
            Объект кнопки с типом ``callback``.
        """
        return {
            "type": "callback",
            "text": self.text,
            "payload": self.payload,
        }


@dataclass(frozen=True)
class LinkButton:
    """Кнопка-ссылка. Открывает URL, не присылая callback.

    Attributes:
        text: Подпись на кнопке.
        url: Адрес, который откроет клиент.
    """

    text: str
    url: str

    def to_dict(self) -> dict[str, str]:
        """Возвращает кнопку в формате API.

        Returns:
            Объект кнопки с типом ``link``.
        """
        return {"type": "link", "text": self.text, "url": self.url}


@dataclass(frozen=True)
class RequestContactButton:
    """Кнопка, которая просит пользователя прислать свой контакт.

    Attributes:
        text: Подпись на кнопке.
    """

    text: str

    def to_dict(self) -> dict[str, str]:
        """Возвращает кнопку в формате API.

        Returns:
            Объект кнопки с типом ``request_contact``.
        """
        return {"type": "request_contact", "text": self.text}


@dataclass(frozen=True)
class RequestGeoLocationButton:
    """Кнопка запроса геопозиции пользователя.

    Attributes:
        text: Подпись на кнопке.
        quick: Если истина, клиент отправит точку без подтверждения.
    """

    text: str
    quick: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Возвращает кнопку в формате API.

        Returns:
            Объект кнопки с типом ``request_geo_location``.
        """
        payload: dict[str, Any] = {
            "type": "request_geo_location",
            "text": self.text,
        }
        if self.quick:
            payload["quick"] = True
        return payload


@dataclass(frozen=True)
class ChatButton:
    """Кнопка, которая создаёт новый чат с ботом-администратором.

    Attributes:
        text: Подпись на кнопке.
        chat_title: Название будущего чата.
        chat_description: Описание чата.
        start_payload: Данные, которые бот получит при создании чата.
        uuid: Идентификатор кнопки. Новый uuid создаёт новый чат.
    """

    text: str
    chat_title: str
    chat_description: str | None = None
    start_payload: str | None = None
    uuid: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Возвращает кнопку в формате API.

        Returns:
            Объект кнопки с типом ``chat``.
        """
        payload: dict[str, Any] = {
            "type": "chat",
            "text": self.text,
            "chat_title": self.chat_title,
        }
        if self.chat_description is not None:
            payload["chat_description"] = self.chat_description
        if self.start_payload is not None:
            payload["start_payload"] = self.start_payload
        if self.uuid is not None:
            payload["uuid"] = self.uuid
        return payload


@dataclass(frozen=True)
class MessageButton:
    """Кнопка, отправляющая в чат готовый текст от имени пользователя.

    Attributes:
        text: Текст, который уйдёт в чат.
    """

    text: str

    def to_dict(self) -> dict[str, str]:
        """Возвращает кнопку в формате API.

        Returns:
            Объект кнопки с типом ``message``.
        """
        return {"type": "message", "text": self.text}


@dataclass(frozen=True)
class OpenAppButton:
    """Кнопка запуска мини-приложения.

    Attributes:
        text: Подпись на кнопке.
        web_app: Ник бота или ссылка на мини-приложение.
        contact_id: Идентификатор бота, чьё приложение открыть.
        payload: Параметр запуска, он попадёт в initData.
    """

    text: str
    web_app: str | None = None
    contact_id: int | None = None
    payload: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Возвращает кнопку в формате API.

        Returns:
            Объект кнопки с типом ``open_app``.
        """
        body: dict[str, Any] = {"type": "open_app", "text": self.text}
        if self.web_app is not None:
            body["web_app"] = self.web_app
        if self.contact_id is not None:
            body["contact_id"] = self.contact_id
        if self.payload is not None:
            body["payload"] = self.payload
        return body


class InlineKeyboard:
    """Встроенная клавиатура. Каждая строка содержит до семи кнопок.

    Метод ``add`` добавляет одну строку и возвращает ту же клавиатуру,
    поэтому вызовы можно объединять в цепочку. В сообщение клавиатура
    попадает как вложение ``inline_keyboard``.
    """

    def __init__(self, rows: Sequence[Sequence[Any]] | None = None) -> None:
        """Создаёт пустую клавиатуру или копирует готовые строки.

        Args:
            rows: Начальные строки кнопок.
        """
        self._rows: list[list[Any]] = []
        if rows is not None:
            for row in rows:
                self.add(*row)

    def add(self, *buttons: Any) -> InlineKeyboard:
        """Добавляет строку кнопок.

        Args:
            *buttons: Кнопки этой строки слева направо.

        Returns:
            Эта же клавиатура.

        Raises:
            ValueError: В строке нет ни одной кнопки.
        """
        if not buttons:
            raise ValueError("В строке нужна хотя бы одна кнопка.")
        self._rows.append(list(buttons))
        return self

    def to_dict(self) -> dict[str, Any]:
        """Возвращает вложение ``inline_keyboard``.

        Returns:
            Объект для списка ``attachments``.
        """
        return {
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [serialize_attachment(button) for button in row]
                    for row in self._rows
                ],
            },
        }
