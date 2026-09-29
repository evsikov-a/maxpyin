# maxpyin

Синхронный и асинхронный клиент [Bot API мессенджера MAX](https://dev.max.ru/docs-api).
Один и тот же набор методов доступен через `MaxBot` и `AsyncMaxBot`.

Запросы идут на `https://platform-api2.max.ru`. Токен передаётся только
в заголовке `Authorization`.

## Установка

Нужен Python 3.10 или новее.

```bash
pip install maxpyin
```

Для разработки из этого репозитория:

```bash
pip install -e ".[dev]"
```

## Quickstart

Токен бота лежит в кабинете MAX: Чат-боты → нужный бот → Настройки.
Положите его в переменную окружения и не записывайте в код.

```bash
export MAX_BOT_TOKEN="сюда-токен"
```

### Синхронный echo

Бот отвечает тем же текстом и добавляет две кнопки. В личном диалоге
сообщение уходит по `user_id`, в чате и канале — по `chat_id`.

```python
import os

from maxpyin import CallbackButton, InlineKeyboard, MaxBot


def main() -> None:
    token = os.environ["MAX_BOT_TOKEN"]
    with MaxBot(token) as bot:
        print(bot.get_me().first_name)
        for update in bot.poll(
            types=["message_created", "message_callback"],
        ):
            callback = update.callback
            if (
                update.update_type == "message_callback"
                and callback is not None
                and callback.callback_id
            ):
                bot.answer_callback(
                    callback.callback_id,
                    notification="Принято",
                )
                continue
            message = update.message
            if (
                message is None
                or message.body is None
                or message.sender is None
                or message.sender.is_bot
                or message.recipient is None
            ):
                continue
            if message.recipient.chat_type == "dialog":
                user_id, chat_id = message.sender.user_id, None
            else:
                user_id, chat_id = None, message.recipient.chat_id
            keyboard = InlineKeyboard().add(
                CallbackButton("Да", "yes"),
                CallbackButton("Нет", "no"),
            )
            bot.send_message(
                message.body.text or "",
                user_id=user_id,
                chat_id=chat_id,
                attachments=[keyboard],
            )


if __name__ == "__main__":
    main()
```

`poll` подходит для разработки. В рабочем боте используйте Webhook:
пока подписка активна, long polling события не получает.

### Асинхронный echo

```python
import asyncio
import os

from maxpyin import AsyncMaxBot


async def main() -> None:
    token = os.environ["MAX_BOT_TOKEN"]
    async with AsyncMaxBot(token) as bot:
        me = await bot.get_me()
        print(me.username)
        async for update in bot.poll(types=["message_created"]):
            message = update.message
            if (
                message is None
                or message.body is None
                or message.sender is None
                or message.sender.is_bot
                or message.recipient is None
            ):
                continue
            if message.recipient.chat_type == "dialog":
                user_id, chat_id = message.sender.user_id, None
            else:
                user_id, chat_id = None, message.recipient.chat_id
            await bot.send_message(
                message.body.text or "",
                user_id=user_id,
                chat_id=chat_id,
            )


if __name__ == "__main__":
    asyncio.run(main())
```

### Клавиатура и callback

`CallbackButton` возвращает `payload` в событии `message_callback`.
`LinkButton` просто открывает адрес. Ответ на нажатие:

```python
from maxpyin import LinkButton

keyboard = InlineKeyboard().add(
    CallbackButton("Да", "yes"),
    LinkButton("Сайт", "https://example.com"),
)
bot.answer_callback(
    callback_id,
    text="Вы выбрали ответ",
    attachments=[keyboard],
    notification="Готово",
)
```

### Webhook

Подписка принимает только `https://` на порту 443. Секрет бот присылает
в заголовке `X-Max-Bot-Api-Secret`.

```python
from maxpyin import parse_update

bot.subscribe(
    "https://example.com/max/webhook",
    update_types=["message_created", "message_callback"],
    secret="replace-me",
)

update = parse_update(request_json)
bot.unsubscribe("https://example.com/max/webhook")
```

Свой HTTP-сервер библиотека не поднимает: разберите тело запроса
через `parse_update` в том фреймворке, который уже обслуживает сайт.

### Файл

Сначала библиотека получает URL загрузки, затем отправляет байты.
Токен из ответа кладётся во вложение.

```python
uploaded = bot.upload_media("file", "notes.txt")
bot.send_message(
    "Файл",
    chat_id=chat_id,
    attachments=[uploaded.as_attachment("file")],
)
```

Если сервер ответит, что вложение ещё не обработано, подождите
и отправьте сообщение с тем же токеном ещё раз.

### Сертификат Минцифры

Если проверка TLS не проходит, передайте корпоративный или
государственный корневой сертификат:

```python
bot = MaxBot(
    token,
    verify="/path/to/russian_trusted_root_ca.cer",
)
```

Другой адрес API задаётся параметром `base_url`.

## Что умеет клиент

Оба класса покрывают текущие методы бота:

- профиль и команды: `get_me`, `edit_me`, `set_commands`;
- чат: карточка, правка, удаление, действие «печатает», закреп,
  участники, администраторы, выход бота;
- сообщения: отправка, правка, удаление, одно сообщение и история;
- ответ на кнопку: `answer_callback`;
- загрузка `image`, `video`, `audio` и `file`;
- комментарии к посту канала;
- подписки Webhook и long polling.

`GET /chats` с июня 2026 не поддерживается, поэтому метода списка чатов
нет: `chat_id` приходит в событиях `bot_added` и `bot_started`.
Добавление участников методом `POST /chats/{chatId}/members` платформа
снимает, и библиотека его не вызывает.

Ответы 429 и 503 повторяются несколько раз. Число попыток задаёт
`max_retries` (по умолчанию 2 повтора после первого запроса).

## Ошибки

- `MaxAuthError` — HTTP 401, токен недействителен;
- `MaxRateLimitError` — HTTP 429, повторы закончились;
- `MaxApiError` — другая ошибка API, в том числе `success: false`;
- `MaxNetworkError` — таймаут или обрыв сети;
- `ValueError` — аргументы не проходят проверку до запроса.

У `MaxApiError` есть `status_code`, `code` и `payload`.

## Лицензия

MIT. Текст лежит в файле `LICENSE`.
