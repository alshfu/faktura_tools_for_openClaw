"""
bolagsverket.exceptions
-----------------------
Все исключения библиотеки.
"""


class BolagsverketError(Exception):
    """Базовое исключение библиотеки."""


class AuthError(BolagsverketError):
    """Ошибка аутентификации (401, неверные ключи)."""


class NotFoundError(BolagsverketError):
    """Компания не найдена (404)."""

    def __init__(self, orgnr: str):
        self.orgnr = orgnr
        super().__init__(f"Компания с org.nr '{orgnr}' не найдена")


class RateLimitError(BolagsverketError):
    """Превышен лимит запросов (429)."""


class ApiError(BolagsverketError):
    """Прочие ошибки API."""

    def __init__(self, status_code: int, body: str = ""):
        self.status_code = status_code
        self.body = body
        super().__init__(f"Ошибка API HTTP {status_code}: {body}")


class ValidationError(BolagsverketError):
    """Ошибка валидации organisationsnummer."""
