"""Ошибки клиента Bot API MAX."""

from __future__ import annotations

from typing import Any


class MaxError(Exception):
    """Базовая ошибка библиотеки maxpyin."""


class MaxApiError(MaxError):
    """Сервер API отклонил запрос или прислал неверный ответ.

    Attributes:
        status_code: HTTP-код ответа.
        code: Машинный код ошибки, если сервер его прислал.
        payload: Разобранное тело ответа.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        code: str | None = None,
        payload: Any = None,
    ) -> None:
        """Сохраняет код ответа и текст ошибки.

        Args:
            message: Пояснение, которое увидит вызывающий код.
            status_code: HTTP-код ответа.
            code: Машинный код ошибки API.
            payload: Тело ответа как JSON или текст.
        """
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code
        self.code = code
        self.payload = payload


class MaxAuthError(MaxApiError):
    """Сервер отклонил токен доступа. HTTP-код 401."""


class MaxRateLimitError(MaxApiError):
    """Лимит запросов исчерпан, повторы не помогли. HTTP-код 429."""


class MaxNetworkError(MaxError):
    """Сеть оборвалась или сервер не ответил вовремя."""

    def __init__(self, message: str) -> None:
        """Создаёт сетевую ошибку.

        Args:
            message: Что именно не удалось выполнить.
        """
        super().__init__(message)
