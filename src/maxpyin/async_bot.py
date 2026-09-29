"""Асинхронный клиент Bot API мессенджера MAX."""

from __future__ import annotations

import ssl
from collections.abc import AsyncIterator, Mapping, Sequence
from pathlib import Path
from typing import Any, BinaryIO

import httpx

from . import calls
from .bot import read_upload_source
from .calls import ApiCall
from .models import (
    BotCommand,
    Chat,
    ChatAdmin,
    ChatMember,
    ChatMemberPage,
    CommentPage,
    Message,
    MessagePage,
    SubscriptionList,
    SuccessResult,
    Update,
    UpdatePage,
    UploadResult,
    UploadSlot,
    User,
    as_chat,
    as_commands,
    as_comment_page,
    as_member,
    as_member_page,
    as_message,
    as_message_page,
    as_optional_message,
    as_subscriptions,
    as_success,
    as_update_page,
    as_upload_slot,
    as_user,
)
from .transport import (
    DEFAULT_BASE_URL,
    AsyncTransport,
    normalize_base_url,
    normalize_retries,
    normalize_timeout,
    normalize_token,
)


class AsyncMaxBot:
    """Асинхронный клиент Bot API мессенджера MAX.

    Парный синхронный класс — ``MaxBot``. Набор методов
    одинаковый: профиль бота, чаты, сообщения, комментарии, файлы,
    подписки и long polling. Токен уходит только в заголовке
    ``Authorization``. Используйте экземпляр внутри одной event loop.

    Длинный опрос удобен для разработки. В продакшене оставьте
    Webhook: при активной подписке ``poll`` события не получит.
    """

    def __init__(
        self,
        token: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        verify: ssl.SSLContext | str | bool = True,
        timeout: float = 30.0,
        max_retries: int = 2,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """Создаёт клиент.

        Args:
            token: Токен бота из кабинета MAX.
            base_url: Адрес API. По умолчанию ``platform-api2.max.ru``.
            verify: Проверка TLS. Можно передать путь к сертификату
                Минцифры, если системное хранилище его не знает.
            timeout: Тайм-аут обычного запроса, секунды.
            max_retries: Сколько раз повторить ответ 429 или 503.
            client: Свой ``httpx.AsyncClient``. Ему уже нужен ``base_url``,
                а ``verify`` и ``base_url`` конструктора тогда не
                применяются. Чужой клиент библиотека не закрывает.

        Raises:
            ValueError: Пустой токен или неверные числовые настройки.
        """
        self._token = normalize_token(token)
        self._base_url = normalize_base_url(base_url)
        self._timeout = normalize_timeout(timeout)
        self._max_retries = normalize_retries(max_retries)
        self._owns_client = client is None
        if client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                verify=verify,
                timeout=self._timeout,
            )
        else:
            self._client = client
        self._transport = AsyncTransport(
            self._client,
            self._token,
            self._timeout,
            self._max_retries,
        )

    async def __aenter__(self) -> AsyncMaxBot:
        """Входит в асинхронный контекст и возвращает этот клиент.

        Returns:
            Этот же экземпляр.
        """
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: Any,
    ) -> None:
        """Закрывает HTTP-клиент при выходе из контекста.

        Args:
            exc_type: Тип исключения внутри блока.
            exc: Само исключение.
            traceback: Трассировка исключения.
        """
        await self.close()

    async def close(self) -> None:
        """Закрывает HTTP-клиент, если его создал этот объект."""
        if self._owns_client:
            await self._client.aclose()

    async def _execute(self, call: ApiCall) -> Any:
        return await self._transport.request(call)

    async def get_me(self) -> User:
        """Возвращает профиль бота, которому принадлежит токен.

        Returns:
            Имя, ник, описание, аватар и команды.

        Raises:
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_user(await self._execute(calls.get_me()))

    async def edit_me(
        self,
        *,
        first_name: str | None = None,
        last_name: str | None = None,
        name: str | None = None,
        description: str | None = None,
        commands: Sequence[BotCommand | tuple[str, str] | Mapping[str, Any]]
        | None = None,
        photo: Mapping[str, Any] | None = None,
    ) -> User:
        """Меняет профиль бота. Метод ``PATCH /me``.

        Args:
            first_name: Новое отображаемое имя.
            last_name: Новая фамилия.
            name: Устаревшее поле имени.
            description: Новое описание.
            commands: Команды. Пустой список удаляет их.
            photo: Аватар, объект с ``url`` или ``token``.

        Returns:
            Обновлённый профиль.

        Raises:
            ValueError: Не передано ни одного поля.
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_user(
            await self._execute(
                calls.edit_me(
                    first_name=first_name,
                    last_name=last_name,
                    name=name,
                    description=description,
                    commands=commands,
                    photo=photo,
                ),
            ),
        )

    async def set_commands(
        self,
        commands: Sequence[BotCommand | tuple[str, str] | Mapping[str, Any]],
    ) -> tuple[BotCommand, ...]:
        """Заменяет команды, которые видны после символа ``/``.

        Пустой список удаляет все команды. Отдельный метод
        ``PATCH /me/commands``, не общий профиль.

        Args:
            commands: Новый список, не больше 32 штук.

        Returns:
            Команды, которые сервер сохранил.

        Raises:
            ValueError: Слишком много команд или пустое имя.
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_commands(await self._execute(calls.set_commands(commands)))

    async def get_chat(self, chat_id: int) -> Chat:
        """Возвращает групповой чат, канал или диалог.

        Args:
            chat_id: Идентификатор чата.

        Returns:
            Карточка чата.

        Raises:
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_chat(await self._execute(calls.get_chat(chat_id)))

    async def edit_chat(
        self,
        chat_id: int,
        *,
        title: str | None = None,
        description: str | None = None,
        notify: bool | None = None,
        icon: Mapping[str, Any] | None = None,
        pin: str | None = None,
    ) -> Chat:
        """Меняет название, описание, аватар или закреп чата.

        Args:
            chat_id: Идентификатор чата.
            title: Новое название.
            description: Новое описание.
            notify: Уведомлять ли участников.
            icon: Аватар, объект с ``url`` или ``token``.
            pin: Сообщение, которое нужно закрепить.

        Returns:
            Обновлённая карточка чата.

        Raises:
            ValueError: Не передано ни одного поля.
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_chat(
            await self._execute(
                calls.edit_chat(
                    chat_id,
                    title=title,
                    description=description,
                    notify=notify,
                    icon=icon,
                    pin=pin,
                ),
            ),
        )

    async def delete_chat(self, chat_id: int) -> SuccessResult:
        """Удаляет групповой чат.

        Args:
            chat_id: Идентификатор чата.

        Returns:
            Подтверждение операции.

        Raises:
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_success(await self._execute(calls.delete_chat(chat_id)))

    async def send_action(self, chat_id: int, action: str) -> SuccessResult:
        """Показывает в чате действие бота, например набор текста.

        Args:
            chat_id: Идентификатор группового чата.
            action: Значение из ``SenderAction``.

        Returns:
            Подтверждение операции.

        Raises:
            ValueError: Действие не поддерживается.
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_success(
            await self._execute(calls.send_action(chat_id, action)),
        )

    async def get_pinned_message(self, chat_id: int) -> Message | None:
        """Возвращает закреплённое сообщение чата или канала.

        Args:
            chat_id: Идентификатор чата или канала.

        Returns:
            Сообщение или ``None``, если закрепления нет.

        Raises:
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_optional_message(
            await self._execute(calls.get_pinned_message(chat_id)),
        )

    async def pin_message(
        self,
        chat_id: int,
        message_id: str,
        *,
        notify: bool | None = None,
    ) -> SuccessResult:
        """Закрепляет сообщение в чате или канале.

        Args:
            chat_id: Где закрепить.
            message_id: Какое сообщение закрепить.
            notify: Присылать ли уведомление.

        Returns:
            Подтверждение операции.

        Raises:
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_success(
            await self._execute(
                calls.pin_message(chat_id, message_id, notify=notify),
            ),
        )

    async def unpin_message(self, chat_id: int) -> SuccessResult:
        """Снимает закреплённое сообщение.

        Args:
            chat_id: Чат или канал.

        Returns:
            Подтверждение операции.

        Raises:
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_success(await self._execute(calls.unpin_message(chat_id)))

    async def get_members(
        self,
        chat_id: int,
        *,
        user_ids: Sequence[int] | None = None,
        marker: int | None = None,
        count: int | None = None,
    ) -> ChatMemberPage:
        """Возвращает участников чата или канала.

        Args:
            chat_id: Идентификатор чата.
            user_ids: Запросить только этих пользователей.
            marker: Указатель страницы.
            count: Размер страницы.

        Returns:
            Страница участников.

        Raises:
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_member_page(
            await self._execute(
                calls.get_members(
                    chat_id,
                    user_ids=user_ids,
                    marker=marker,
                    count=count,
                ),
            ),
        )

    async def remove_member(
        self,
        chat_id: int,
        user_id: int,
        *,
        block: bool | None = None,
    ) -> SuccessResult:
        """Удаляет участника из чата или канала.

        Args:
            chat_id: Откуда удалить.
            user_id: Кого удалить.
            block: Заблокировать в этом чате.

        Returns:
            Подтверждение операции.

        Raises:
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_success(
            await self._execute(
                calls.remove_member(chat_id, user_id, block=block),
            ),
        )

    async def get_admins(self, chat_id: int) -> ChatMemberPage:
        """Возвращает администраторов чата или канала.

        Args:
            chat_id: Идентификатор чата.

        Returns:
            Страница администраторов.

        Raises:
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_member_page(await self._execute(calls.get_admins(chat_id)))

    async def add_admins(
        self,
        chat_id: int,
        admins: Sequence[ChatAdmin | Mapping[str, Any]],
    ) -> SuccessResult:
        """Назначает администраторов чата или канала.

        Args:
            chat_id: Куда назначить.
            admins: Люди и их права ``ChatPermission``.

        Returns:
            Подтверждение операции.

        Raises:
            ValueError: Список пуст или права не заданы.
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_success(
            await self._execute(calls.add_admins(chat_id, admins)),
        )

    async def remove_admin(self, chat_id: int, user_id: int) -> SuccessResult:
        """Снимает права администратора.

        Args:
            chat_id: Чат или канал.
            user_id: У кого забрать права.

        Returns:
            Подтверждение операции.

        Raises:
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_success(
            await self._execute(calls.remove_admin(chat_id, user_id)),
        )

    async def get_membership(self, chat_id: int) -> ChatMember:
        """Возвращает членство самого бота в чате или канале.

        Args:
            chat_id: Идентификатор чата.

        Returns:
            Карточка бота как участника.

        Raises:
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_member(await self._execute(calls.get_membership(chat_id)))

    async def leave_chat(self, chat_id: int) -> SuccessResult:
        """Удаляет бота из чата или канала.

        Args:
            chat_id: Откуда выйти.

        Returns:
            Подтверждение операции.

        Raises:
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_success(await self._execute(calls.leave_chat(chat_id)))

    async def send_message(
        self,
        text: str | None = None,
        *,
        user_id: int | None = None,
        chat_id: int | None = None,
        attachments: Sequence[Any] | None = None,
        link: Any = None,
        notify: bool | None = None,
        text_format: str | None = None,
        disable_link_preview: bool | None = None,
    ) -> Message:
        """Отправляет сообщение пользователю, в чат или в канал.

        Нужен ``user_id`` или ``chat_id``. В канал можно писать,
        только если бот — администратор.

        Args:
            text: Текст до 4000 символов.
            user_id: Получатель личного диалога.
            chat_id: Чат или канал.
            attachments: Вложения и клавиатура.
            link: Ответ или пересылка, объект ``MessageLink``.
            notify: Присылать ли push. Для канала оставьте истину.
            text_format: ``markdown`` или ``html``.
            disable_link_preview: Не строить превью ссылок.

        Returns:
            Отправленное сообщение.

        Raises:
            ValueError: Нет адресата или содержимого.
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_message(
            await self._execute(
                calls.send_message(
                    text,
                    user_id=user_id,
                    chat_id=chat_id,
                    attachments=attachments,
                    link=link,
                    notify=notify,
                    text_format=text_format,
                    disable_link_preview=disable_link_preview,
                ),
            ),
        )

    async def edit_message(
        self,
        message_id: str,
        *,
        text: str | None = None,
        attachments: Sequence[Any] | None = None,
        link: Any = None,
        notify: bool | None = None,
        text_format: str | None = None,
    ) -> SuccessResult:
        """Редактирует сообщение, которое отправил бот.

        Пустой список ``attachments`` удаляет все вложения.
        ``None`` оставляет вложения как есть.

        Args:
            message_id: Какое сообщение изменить.
            text: Новый текст.
            attachments: Новые вложения.
            link: Новая связь с другим сообщением.
            notify: Уведомлять ли об изменении.
            text_format: ``markdown`` или ``html``.

        Returns:
            Подтверждение операции.

        Raises:
            ValueError: Нечего изменять.
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_success(
            await self._execute(
                calls.edit_message(
                    message_id,
                    text=text,
                    attachments=attachments,
                    link=link,
                    notify=notify,
                    text_format=text_format,
                ),
            ),
        )

    async def delete_message(self, message_id: str) -> SuccessResult:
        """Удаляет сообщение.

        В диалоге бот удаляет только свои сообщения. В чате и канале
        нужны права администратора. Не больше двух удалений в секунду
        в один чат.

        Args:
            message_id: Какое сообщение удалить.

        Returns:
            Подтверждение операции.

        Raises:
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_success(
            await self._execute(calls.delete_message(message_id)),
        )

    async def get_message(self, message_id: str) -> Message:
        """Возвращает одно сообщение по идентификатору.

        Args:
            message_id: Идентификатор ``mid``.

        Returns:
            Сообщение.

        Raises:
            MaxAuthError: Токен отклонён.
            MaxApiError: Сообщение не найдено или нет доступа.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_message(await self._execute(calls.get_message(message_id)))

    async def get_messages(
        self,
        *,
        chat_id: int | None = None,
        message_ids: Sequence[str] | None = None,
        from_time: int | None = None,
        to_time: int | None = None,
        count: int | None = None,
    ) -> MessagePage:
        """Возвращает историю чата или конкретные сообщения.

        Args:
            chat_id: Чат, из которого читать историю.
            message_ids: Конкретные идентификаторы.
            from_time: Верхняя граница времени, Unix-время в мс.
            to_time: Нижняя граница времени, Unix-время в мс.
            count: Сколько сообщений вернуть.

        Returns:
            Страница сообщений.

        Raises:
            ValueError: Не задан ни чат, ни список идентификаторов.
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_message_page(
            await self._execute(
                calls.get_messages(
                    chat_id=chat_id,
                    message_ids=message_ids,
                    from_time=from_time,
                    to_time=to_time,
                    count=count,
                ),
            ),
        )

    async def answer_callback(
        self,
        callback_id: str,
        *,
        text: str | None = None,
        attachments: Sequence[Any] | None = None,
        link: Any = None,
        notify: bool | None = None,
        text_format: str | None = None,
        notification: str | None = None,
        disable_link_preview: bool | None = None,
    ) -> SuccessResult:
        """Отвечает на нажатие кнопки.

        Можно обновить исходное сообщение, показать короткое
        уведомление или сделать оба действия сразу.

        Args:
            callback_id: Поле ``callback.callback_id`` события.
            text: Новый текст исходного сообщения.
            attachments: Новые вложения исходного сообщения.
            link: Новая связь исходного сообщения.
            notify: Уведомлять ли об изменении.
            text_format: ``markdown`` или ``html``.
            notification: Всплывающий текст для пользователя.
            disable_link_preview: Не строить превью ссылок.

        Returns:
            Подтверждение операции.

        Raises:
            ValueError: Нет ни уведомления, ни нового сообщения.
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_success(
            await self._execute(
                calls.answer_callback(
                    callback_id,
                    text=text,
                    attachments=attachments,
                    link=link,
                    notify=notify,
                    text_format=text_format,
                    notification=notification,
                    disable_link_preview=disable_link_preview,
                ),
            ),
        )

    async def get_upload_url(self, upload_type: str) -> UploadSlot:
        """Запрашивает URL, на который можно отправить один файл.

        Args:
            upload_type: ``image``, ``video``, ``audio`` или ``file``.

        Returns:
            Адрес загрузки и, иногда, готовый токен.

        Raises:
            ValueError: Тип файла не поддерживается.
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_upload_slot(
            await self._execute(calls.get_upload_url(upload_type)),
        )

    async def upload_file(
        self,
        url: str,
        source: bytes | bytearray | BinaryIO | str | Path,
        *,
        filename: str | None = None,
    ) -> UploadResult:
        """Отправляет файл по URL из ``get_upload_url``.

        Файл уходит целиком как ``multipart/form-data``, поле ``data``.
        Если загрузка оборвётся, её нужно начать заново.

        Args:
            url: Поле ``url`` слота загрузки.
            source: Байты, открытый файл или путь.
            filename: Имя файла в форме.

        Returns:
            Токен, которым файл прикрепляется к сообщению.

        Raises:
            TypeError: Источник неизвестного вида.
            MaxApiError: Сервер отклонил файл.
            MaxNetworkError: Нет ответа от сервера.
        """
        content, name = read_upload_source(source, filename)
        return UploadResult.from_dict(
            await self._transport.upload(url, name, content),
        )

    async def upload_media(
        self,
        upload_type: str,
        source: bytes | bytearray | BinaryIO | str | Path,
        *,
        filename: str | None = None,
    ) -> UploadResult:
        """Запрашивает URL и сразу отправляет на него файл.

        Свежий токен иногда ещё не обработан. Если ``send_message``
        ответит, что вложение не готово, повторите отправку позже
        и переиспользуйте тот же токен.

        Args:
            upload_type: ``image``, ``video``, ``audio`` или ``file``.
            source: Байты, открытый файл или путь.
            filename: Имя файла в форме.

        Returns:
            Результат с методом ``as_attachment``.

        Raises:
            ValueError: Тип файла не поддерживается.
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        slot = await self.get_upload_url(upload_type)
        result = await self.upload_file(slot.url, source, filename=filename)
        if result.media_token is None and slot.token is not None:
            result.token = slot.token
        return result

    async def send_comment(
        self,
        message_id: str,
        text: str,
        *,
        text_format: str | None = None,
    ) -> Message:
        """Пишет комментарий к посту канала.

        Бот должен быть администратором канала с правами
        ``read_all_messages`` и ``write``.

        Args:
            message_id: Идентификатор поста.
            text: Текст комментария.
            text_format: ``markdown`` или ``html``.

        Returns:
            Созданный комментарий.

        Raises:
            MaxAuthError: Токен отклонён.
            MaxApiError: Нет прав или комментарии выключены.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_message(
            await self._execute(
                calls.send_comment(
                    message_id,
                    text,
                    text_format=text_format,
                ),
            ),
        )

    async def get_comments(
        self,
        message_id: str,
        *,
        comment_ids: Sequence[str] | None = None,
        before: int | None = None,
        after: int | None = None,
        count: int | None = None,
    ) -> CommentPage:
        """Возвращает комментарии к посту канала.

        Args:
            message_id: Идентификатор поста.
            comment_ids: Конкретные комментарии.
            before: Верхняя граница времени, Unix-время в мс.
            after: Нижняя граница времени, Unix-время в мс.
            count: Размер страницы, от 1 до 100.

        Returns:
            Страница комментариев.

        Raises:
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_comment_page(
            await self._execute(
                calls.get_comments(
                    message_id,
                    comment_ids=comment_ids,
                    before=before,
                    after=after,
                    count=count,
                ),
            ),
        )

    async def get_comment(self, message_id: str, comment_id: str) -> Message:
        """Возвращает один комментарий к посту.

        Args:
            message_id: Идентификатор поста.
            comment_id: Идентификатор комментария.

        Returns:
            Комментарий.

        Raises:
            MaxAuthError: Токен отклонён.
            MaxApiError: Комментарий не найден.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_message(
            await self._execute(calls.get_comment(message_id, comment_id)),
        )

    async def edit_comment(
        self,
        message_id: str,
        comment_id: str,
        *,
        text: str | None = None,
        link: Any = None,
        text_format: str | None = None,
    ) -> SuccessResult:
        """Редактирует комментарий бота к посту канала.

        Args:
            message_id: Идентификатор поста.
            comment_id: Какой комментарий изменить.
            text: Новый текст.
            link: Новая связь. Пересылка комментариев недоступна.
            text_format: ``markdown`` или ``html``.

        Returns:
            Подтверждение операции.

        Raises:
            ValueError: Нечего изменять.
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_success(
            await self._execute(
                calls.edit_comment(
                    message_id,
                    comment_id,
                    text=text,
                    link=link,
                    text_format=text_format,
                ),
            ),
        )

    async def delete_comment(
        self,
        message_id: str,
        comment_id: str,
    ) -> SuccessResult:
        """Удаляет комментарий к посту канала.

        Нужны права ``read_all_messages`` и ``delete``. Восстановить
        комментарий нельзя.

        Args:
            message_id: Идентификатор поста.
            comment_id: Какой комментарий удалить.

        Returns:
            Подтверждение операции.

        Raises:
            MaxAuthError: Токен отклонён.
            MaxApiError: Нет прав на удаление.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_success(
            await self._execute(calls.delete_comment(message_id, comment_id)),
        )

    async def get_subscriptions(self) -> SubscriptionList:
        """Возвращает Webhook-подписки бота.

        Returns:
            Текущие подписки.

        Raises:
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_subscriptions(await self._execute(calls.get_subscriptions()))

    async def subscribe(
        self,
        url: str,
        *,
        update_types: Sequence[str] | None = None,
        secret: str | None = None,
    ) -> SuccessResult:
        """Включает доставку событий на HTTPS Webhook.

        Endpoint должен отвечать 200 по порту 443 сертификатом
        доверенного центра или Минцифры. Пока подписка активна,
        long polling молчит. Секрет приходит в заголовке
        ``X-Max-Bot-Api-Secret``.

        Args:
            url: Адрес вида ``https://example.com/webhook``.
            update_types: Какие события присылать.
            secret: Секрет из 5–256 символов ``A-Z``, ``a-z``,
                цифр, ``_`` и ``-``.

        Returns:
            Подтверждение подписки.

        Raises:
            ValueError: URL или секрет не подходят под правила API.
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_success(
            await self._execute(
                calls.subscribe(
                    url,
                    update_types=update_types,
                    secret=secret,
                ),
            ),
        )

    async def unsubscribe(self, url: str) -> SuccessResult:
        """Отключает Webhook-подписку.

        Args:
            url: Адрес, который больше не должен получать события.

        Returns:
            Подтверждение отписки.

        Raises:
            ValueError: URL пустой.
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_success(await self._execute(calls.unsubscribe(url)))

    async def get_updates(
        self,
        *,
        marker: int | None = None,
        limit: int | None = None,
        timeout: int | None = None,
        types: Sequence[str] | None = None,
    ) -> UpdatePage:
        """Получает страницу событий через long polling.

        Без ``marker`` сервер отдаёт только последнее событие.
        Для непрерывного чтения используйте ``poll``.

        Args:
            marker: Указатель из прошлого ответа.
            limit: Сколько событий вернуть, от 1 до 1000.
            timeout: Сколько секунд держать соединение, от 0 до 90.
            types: Фильтр типов, например ``message_created``.

        Returns:
            События и маркер следующей страницы.

        Raises:
            ValueError: ``limit`` или ``timeout`` вне диапазона.
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        return as_update_page(
            await self._execute(
                calls.get_updates(
                    marker=marker,
                    limit=limit,
                    timeout=timeout,
                    types=types,
                ),
            ),
        )

    async def poll(
        self,
        *,
        marker: int | None = None,
        limit: int = 100,
        timeout: int = 30,
        types: Sequence[str] | None = None,
    ) -> AsyncIterator[Update]:
        """Бесконечно отдаёт события long polling.

        Генератор сам подставляет ``marker`` из предыдущего ответа.
        Остановите его закрытием генератора или исключением.
        При активном Webhook сервер события этим методом не отдаст.

        Args:
            marker: С какого места продолжить. ``None`` начинает
                с последнего события.
            limit: Размер страницы, от 1 до 1000.
            timeout: Долгий опрос, секунды, от 0 до 90.
            types: Какие события принимать.

        Yields:
            Очередное событие.

        Raises:
            ValueError: ``limit`` или ``timeout`` вне диапазона.
            MaxAuthError: Токен отклонён.
            MaxApiError: API вернуло ошибку.
            MaxNetworkError: Нет ответа от сервера.
        """
        current = marker
        while True:
            page = await self.get_updates(
                marker=current,
                limit=limit,
                timeout=timeout,
                types=types,
            )
            for update in page.updates:
                yield update
            if page.marker is not None:
                current = page.marker
