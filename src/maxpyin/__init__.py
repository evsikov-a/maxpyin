"""Клиент Bot API мессенджера MAX.

Библиотека даёт два равноправных класса: синхронный ``MaxBot``
и асинхронный ``AsyncMaxBot``.
"""

from ._version import __version__
from .async_bot import AsyncMaxBot
from .bot import MaxBot
from .exceptions import (
    MaxApiError,
    MaxAuthError,
    MaxError,
    MaxNetworkError,
    MaxRateLimitError,
)
from .keyboards import (
    CallbackButton,
    ChatButton,
    InlineKeyboard,
    LinkButton,
    MessageButton,
    OpenAppButton,
    RequestContactButton,
    RequestGeoLocationButton,
)
from .models import (
    BotCommand,
    Callback,
    Chat,
    ChatAdmin,
    ChatMember,
    ChatPermission,
    CommentPage,
    Message,
    MessageLink,
    SenderAction,
    Subscription,
    SuccessResult,
    Update,
    UpdatePage,
    UpdateType,
    UploadResult,
    UploadSlot,
    User,
    parse_update,
)
from .transport import DEFAULT_BASE_URL

__all__ = [
    "DEFAULT_BASE_URL",
    "AsyncMaxBot",
    "BotCommand",
    "Callback",
    "CallbackButton",
    "Chat",
    "ChatAdmin",
    "ChatButton",
    "ChatMember",
    "ChatPermission",
    "CommentPage",
    "InlineKeyboard",
    "LinkButton",
    "MaxApiError",
    "MaxAuthError",
    "MaxBot",
    "MaxError",
    "MaxNetworkError",
    "MaxRateLimitError",
    "Message",
    "MessageButton",
    "MessageLink",
    "OpenAppButton",
    "RequestContactButton",
    "RequestGeoLocationButton",
    "SenderAction",
    "Subscription",
    "SuccessResult",
    "Update",
    "UpdatePage",
    "UpdateType",
    "UploadResult",
    "UploadSlot",
    "User",
    "__version__",
    "parse_update",
]
