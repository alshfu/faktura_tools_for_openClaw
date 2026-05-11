"""
bolagsverket.auth
-----------------
OAuth2 аутентификация с автоматическим кэшированием и обновлением токена.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import requests

from .exceptions import AuthError

TOKEN_URL = "https://api.bolagsverket.se/oauth/token"
_REFRESH_BEFORE_EXPIRY = 60  # обновлять токен за 60 сек до истечения


@dataclass
class TokenCache:
    """Хранит токен и момент его истечения."""
    access_token: str = ""
    expires_at: float = 0.0

    def is_valid(self) -> bool:
        return bool(self.access_token) and time.time() < self.expires_at - _REFRESH_BEFORE_EXPIRY


class TokenManager:
    """
    Управляет OAuth2-токеном для одного набора учётных данных.

    Пример:
        manager = TokenManager("my_client_id", "my_secret")
        token = manager.get_token()   # автоматически обновляется при необходимости
    """

    def __init__(self, client_id: str, client_secret: str, timeout: int = 15):
        self._client_id = client_id
        self._client_secret = client_secret
        self._timeout = timeout
        self._cache = TokenCache()

    def get_token(self) -> str:
        """Возвращает действующий Bearer-токен. Обновляет при необходимости."""
        if not self._cache.is_valid():
            self._refresh()
        return self._cache.access_token

    def invalidate(self) -> None:
        """Принудительно сбрасывает кэш — следующий вызов get_token() запросит новый токен."""
        self._cache = TokenCache()

    # ── Внутренние методы ─────────────────────

    def _refresh(self) -> None:
        try:
            resp = requests.post(
                TOKEN_URL,
                data={
                    "grant_type":    "client_credentials",
                    "client_id":     self._client_id,
                    "client_secret": self._client_secret,
                },
                timeout=self._timeout,
            )
        except requests.ConnectionError as exc:
            raise AuthError(f"Не удалось подключиться к серверу токенов: {exc}") from exc
        except requests.Timeout:
            raise AuthError("Таймаут при получении токена") from None

        if resp.status_code == 401:
            raise AuthError("Неверные client_id или client_secret (HTTP 401)")
        if not resp.ok:
            raise AuthError(f"Ошибка получения токена HTTP {resp.status_code}: {resp.text}")

        data = resp.json()
        self._cache = TokenCache(
            access_token=data["access_token"],
            expires_at=time.time() + data.get("expires_in", 3600),
        )
