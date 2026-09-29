"""HTTP-транспорт Bot API: повторы при 429 и 503."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx

from ._version import __version__
from .calls import ApiCall
from .exceptions import (
    MaxApiError,
    MaxAuthError,
    MaxNetworkError,
    MaxRateLimitError,
)

DEFAULT_BASE_URL = "https://platform-api2.max.ru"
_RETRYABLE = frozenset({429, 503})
_USER_AGENT = f"maxpyin/{__version__}"


def normalize_token(token: str) -> str:
    """Проверяет токен бота.

    Args:
        token: Токен из кабинета чат-бота.

    Returns:
        Токен без пробелов по краям.

    Raises:
        ValueError: Токен пустой.
    """
    if not isinstance(token, str) or not token.strip():
        raise ValueError("Токен бота не должен быть пустым.")
    return token.strip()


def normalize_base_url(base_url: str) -> str:
    """Убирает завершающий слэш у базового URL.

    Args:
        base_url: Адрес API.

    Returns:
        URL без завершающего слэша.

    Raises:
        ValueError: URL пустой.
    """
    if not isinstance(base_url, str) or not base_url.strip():
        raise ValueError("Базовый URL не должен быть пустым.")
    return base_url.strip().rstrip("/")


def normalize_timeout(timeout: float) -> float:
    """Проверяет тайм-аут HTTP в секундах.

    Args:
        timeout: Сколько секунд ждать обычный запрос.

    Returns:
        Тайм-аут как ``float``.

    Raises:
        TypeError: Значение не число.
        ValueError: Тайм-аут не положительный.
    """
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise TypeError("timeout должен быть числом секунд.")
    if timeout <= 0:
        raise ValueError("timeout должен быть больше нуля.")
    return float(timeout)


def normalize_retries(max_retries: int) -> int:
    """Проверяет число повторных попыток.

    Args:
        max_retries: Сколько раз повторить запрос после первой неудачи.

    Returns:
        Неотрицательное число попыток.

    Raises:
        ValueError: Число попыток не подходит.
    """
    if isinstance(max_retries, bool) or not isinstance(max_retries, int):
        raise ValueError("max_retries должен быть целым числом от 0.")
    if max_retries < 0:
        raise ValueError("max_retries должен быть целым числом от 0.")
    return max_retries


def _read_payload(response: httpx.Response) -> Any:
    if not response.content:
        return None
    try:
        return response.json()
    except json.JSONDecodeError as exc:
        if response.status_code >= 400:
            return response.text
        raise MaxApiError(
            "Ответ сервера не является JSON.",
            status_code=response.status_code,
            payload=response.text,
        ) from exc


def _error_from(response: httpx.Response, payload: Any) -> MaxApiError:
    message = "Запрос отклонён."
    code = None
    if isinstance(payload, dict):
        raw_message = payload.get("message")
        if isinstance(raw_message, str) and raw_message:
            message = raw_message
        raw_code = payload.get("code")
        if isinstance(raw_code, str):
            code = raw_code
    elif isinstance(payload, str) and payload:
        message = payload
    error_type: type[MaxApiError] = MaxApiError
    if response.status_code == 401:
        error_type = MaxAuthError
    elif response.status_code == 429:
        error_type = MaxRateLimitError
    return error_type(
        message,
        status_code=response.status_code,
        code=code,
        payload=payload,
    )


def _failed(payload: Any) -> bool:
    return isinstance(payload, dict) and payload.get("success") is False


@dataclass
class _Decision:
    payload: Any = None
    error: MaxApiError | None = None
    retry: bool = False


def _assess(response: httpx.Response) -> _Decision:
    payload = _read_payload(response)
    if response.status_code in _RETRYABLE:
        return _Decision(
            error=_error_from(response, payload),
            retry=True,
        )
    if response.status_code >= 400 or _failed(payload):
        return _Decision(error=_error_from(response, payload))
    return _Decision(payload=payload)


def _delay(response: httpx.Response, attempt: int) -> float:
    raw = response.headers.get("Retry-After")
    if raw:
        try:
            parsed = float(raw)
        except ValueError:
            parsed = -1.0
        if parsed >= 0:
            return min(parsed, 8.0)
    return min(0.5 * (2**attempt), 8.0)


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": token,
        "User-Agent": _USER_AGENT,
    }


class SyncTransport:
    """Синхронная отправка запросов через ``httpx.Client``."""

    def __init__(
        self,
        client: httpx.Client,
        token: str,
        timeout: float,
        max_retries: int,
    ) -> None:
        """Сохраняет клиент и политику повторов.

        Args:
            client: Готовый HTTP-клиент с базовым URL.
            token: Токен для заголовка ``Authorization``.
            timeout: Тайм-аут обычного запроса, секунды.
            max_retries: Повторы после ответа 429 или 503.
        """
        self._client = client
        self._token = token
        self._timeout = timeout
        self._max_retries = max_retries

    def request(self, call: ApiCall) -> Any:
        """Выполняет запрос к API и возвращает JSON.

        Args:
            call: Подготовленный запрос.

        Returns:
            Разобранное тело ответа.

        Raises:
            MaxAuthError: Токен отклонён.
            MaxRateLimitError: Лимит не снялся после повторов.
            MaxApiError: Сервер вернул другую ошибку.
            MaxNetworkError: Сеть недоступна.
        """
        timeout = self._timeout if call.timeout is None else call.timeout

        def send() -> httpx.Response:
            try:
                return self._client.request(
                    call.method,
                    call.path,
                    params=call.params or None,
                    json=call.json_body,
                    headers=_headers(self._token),
                    timeout=timeout,
                )
            except httpx.TimeoutException as exc:
                raise MaxNetworkError(
                    "Истекло время ожидания ответа API.",
                ) from exc
            except httpx.RequestError as exc:
                raise MaxNetworkError(
                    "Не удалось выполнить запрос к API.",
                ) from exc

        return self._exchange(send)

    def upload(self, url: str, filename: str, content: bytes) -> Any:
        """Отправляет файл по URL из ``POST /uploads``.

        Args:
            url: Адрес загрузки.
            filename: Имя файла в форме.
            content: Байты файла.

        Returns:
            JSON сервера файлов.

        Raises:
            MaxApiError: Сервер отклонил файл.
            MaxNetworkError: Сеть недоступна.
        """
        files = {
            "data": (filename, content, "application/octet-stream"),
        }

        def send() -> httpx.Response:
            try:
                return self._client.post(
                    url,
                    files=files,
                    headers=_headers(self._token),
                    timeout=self._timeout,
                )
            except httpx.TimeoutException as exc:
                raise MaxNetworkError(
                    "Истекло время ожидания загрузки файла.",
                ) from exc
            except httpx.RequestError as exc:
                raise MaxNetworkError(
                    "Не удалось загрузить файл.",
                ) from exc

        return self._exchange(send)

    def _exchange(self, send: Callable[[], httpx.Response]) -> Any:
        attempt = 0
        while True:
            response = send()
            decision = _assess(response)
            if not decision.retry or attempt >= self._max_retries:
                if decision.error is not None:
                    raise decision.error
                return decision.payload
            time.sleep(_delay(response, attempt))
            attempt += 1


class AsyncTransport:
    """Асинхронная отправка запросов через ``httpx.AsyncClient``."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        token: str,
        timeout: float,
        max_retries: int,
    ) -> None:
        """Сохраняет клиент и политику повторов.

        Args:
            client: Готовый асинхронный HTTP-клиент.
            token: Токен для заголовка ``Authorization``.
            timeout: Тайм-аут обычного запроса, секунды.
            max_retries: Повторы после ответа 429 или 503.
        """
        self._client = client
        self._token = token
        self._timeout = timeout
        self._max_retries = max_retries

    async def request(self, call: ApiCall) -> Any:
        """Выполняет запрос к API и возвращает JSON.

        Args:
            call: Подготовленный запрос.

        Returns:
            Разобранное тело ответа.

        Raises:
            MaxAuthError: Токен отклонён.
            MaxRateLimitError: Лимит не снялся после повторов.
            MaxApiError: Сервер вернул другую ошибку.
            MaxNetworkError: Сеть недоступна.
        """
        timeout = self._timeout if call.timeout is None else call.timeout

        async def send() -> httpx.Response:
            try:
                return await self._client.request(
                    call.method,
                    call.path,
                    params=call.params or None,
                    json=call.json_body,
                    headers=_headers(self._token),
                    timeout=timeout,
                )
            except httpx.TimeoutException as exc:
                raise MaxNetworkError(
                    "Истекло время ожидания ответа API.",
                ) from exc
            except httpx.RequestError as exc:
                raise MaxNetworkError(
                    "Не удалось выполнить запрос к API.",
                ) from exc

        return await self._exchange(send)

    async def upload(self, url: str, filename: str, content: bytes) -> Any:
        """Отправляет файл по URL из ``POST /uploads``.

        Args:
            url: Адрес загрузки.
            filename: Имя файла в форме.
            content: Байты файла.

        Returns:
            JSON сервера файлов.

        Raises:
            MaxApiError: Сервер отклонил файл.
            MaxNetworkError: Сеть недоступна.
        """
        files = {
            "data": (filename, content, "application/octet-stream"),
        }

        async def send() -> httpx.Response:
            try:
                return await self._client.post(
                    url,
                    files=files,
                    headers=_headers(self._token),
                    timeout=self._timeout,
                )
            except httpx.TimeoutException as exc:
                raise MaxNetworkError(
                    "Истекло время ожидания загрузки файла.",
                ) from exc
            except httpx.RequestError as exc:
                raise MaxNetworkError(
                    "Не удалось загрузить файл.",
                ) from exc

        return await self._exchange(send)

    async def _exchange(
        self,
        send: Callable[[], Awaitable[httpx.Response]],
    ) -> Any:
        attempt = 0
        while True:
            response = await send()
            decision = _assess(response)
            if not decision.retry or attempt >= self._max_retries:
                if decision.error is not None:
                    raise decision.error
                return decision.payload
            await asyncio.sleep(_delay(response, attempt))
            attempt += 1
