"""
bolagsverket.factory
--------------------
Фабричные функции для создания клиентов.

Позволяют выбрать источник данных через единый интерфейс:
  - "bolagsverket" — официальный API (нужны ключи)
  - "mackan"       — прокси без ключей (mackan.eu)
  - "auto"         — автовыбор: Bolagsverket если есть ключи, иначе mackan.eu

Пример:
    from bolagsverket import get_client

    # Автовыбор по env-переменным
    client = get_client()

    # Явно mackan (без ключей)
    client = get_client(source="mackan")

    # Явно Bolagsverket
    client = get_client(source="bolagsverket", client_id="...", client_secret="...")
"""

from __future__ import annotations

import os
from typing import Literal, Optional, Union

from .base import BaseCompanyClient
from .client import BolagsverketClient
from .mackan import MackAnClient

Source = Literal["bolagsverket", "mackan", "auto"]


def get_client(
    source: Source = "auto",
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    timeout: int = 15,
    validate_orgnr: bool = True,
) -> BaseCompanyClient:
    """
    Создаёт и возвращает подходящий клиент для получения данных о компаниях.

    Параметры:
        source         — источник данных:
                         "bolagsverket" — официальный API (нужны ключи)
                         "mackan"       — mackan.eu без ключей
                         "auto"         — автовыбор (по умолчанию)
        client_id      — OAuth2 client_id (для Bolagsverket)
                         Если не передан, читается из env BV_CLIENT_ID
        client_secret  — OAuth2 client_secret
                         Если не передан, читается из env BV_CLIENT_SECRET
        timeout        — таймаут HTTP-запросов в секундах
        validate_orgnr — проверять org.nr перед запросом

    Возвращает:
        BolagsverketClient или MackAnClient

    Логика "auto":
        1. Если заданы client_id и client_secret → BolagsverketClient
        2. Если заданы env BV_CLIENT_ID и BV_CLIENT_SECRET → BolagsverketClient
        3. Иначе → MackAnClient (без ключей)

    Примеры:
        # Автовыбор (читает из env-переменных)
        client = get_client()

        # Mackan без ключей
        client = get_client(source="mackan")

        # Официальный API с ключами
        client = get_client(
            source="bolagsverket",
            client_id="abc",
            client_secret="xyz",
        )

        # Автовыбор с явными ключами
        client = get_client(client_id="abc", client_secret="xyz")
    """
    # Разрешаем ключи из env если не переданы явно
    resolved_id     = client_id     or os.getenv("BV_CLIENT_ID", "")
    resolved_secret = client_secret or os.getenv("BV_CLIENT_SECRET", "")

    if source == "mackan":
        return MackAnClient(timeout=timeout, validate_orgnr=validate_orgnr)

    if source == "bolagsverket":
        if not resolved_id or not resolved_secret:
            raise ValueError(
                "Для source='bolagsverket' необходимы client_id и client_secret.\n"
                "Передайте их явно или задайте env BV_CLIENT_ID / BV_CLIENT_SECRET."
            )
        return BolagsverketClient(
            client_id=resolved_id,
            client_secret=resolved_secret,
            timeout=timeout,
            validate_orgnr=validate_orgnr,
        )

    # source == "auto"
    if resolved_id and resolved_secret:
        return BolagsverketClient(
            client_id=resolved_id,
            client_secret=resolved_secret,
            timeout=timeout,
            validate_orgnr=validate_orgnr,
        )

    return MackAnClient(timeout=timeout, validate_orgnr=validate_orgnr)
