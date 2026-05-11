"""
bolagsverket
============
Python-библиотека для работы с Bolagsverket API (Värdefulla datamängder).

Быстрый старт:
    from bolagsverket import BolagsverketClient

    client = BolagsverketClient("client_id", "client_secret")
    company = client.get_company("5590877446")

    print(company.name)            # "Spotify AB"
    print(company.is_active)       # True
    print(company.is_construction) # False
    print(company.age_years)       # 20.1
"""

"""
bolagsverket
============
Python-библиотека для работы с данными шведских компаний.

Источники данных:
  BolagsverketClient — официальный Bolagsverket API (OAuth2-ключи)
  MackAnClient       — mackan.eu прокси (без ключей)
  get_client()       — автовыбор источника

Быстрый старт (с ключами):
    from bolagsverket import get_client
    client = get_client()   # читает BV_CLIENT_ID / BV_CLIENT_SECRET из env
    company = client.get_company("5560000001")

Без ключей:
    from bolagsverket import MackAnClient
    client = MackAnClient()
    company = client.get_company("5560000001")
    print(company.name, company.vat_number)
"""

from .client import BolagsverketClient
from .mackan import MackAnClient
from .factory import get_client
from .base import BaseCompanyClient
from .exceptions import (
    ApiError,
    AuthError,
    BolagsverketError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from .models import Address, AnnualReport, Company, SniCode
from .validators import is_valid, legal_form_hint, normalize, validate
from .vat import (
    VatInfo,
    format_vat_eu,
    generate_vat_info,
    generate_vat_number,
    is_valid_vat_format,
    parse_vat_number,
)

__version__ = "1.2.0"
__author__ = "bolagsverket-py"

__all__ = [
    # Клиенты
    "BolagsverketClient",
    "MackAnClient",
    "BaseCompanyClient",
    "get_client",
    # Модели
    "Company",
    "Address",
    "SniCode",
    "AnnualReport",
    # VAT / Moms
    "VatInfo",
    "generate_vat_number",
    "generate_vat_info",
    "parse_vat_number",
    "is_valid_vat_format",
    "format_vat_eu",
    # Исключения
    "BolagsverketError",
    "AuthError",
    "NotFoundError",
    "RateLimitError",
    "ApiError",
    "ValidationError",
    # Валидаторы
    "validate",
    "normalize",
    "is_valid",
    "legal_form_hint",
]
