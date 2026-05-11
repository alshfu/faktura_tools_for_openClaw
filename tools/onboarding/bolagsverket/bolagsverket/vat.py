"""
bolagsverket.vat
----------------
Генерация и валидация шведских номеров плательщика НДС
(momsregistreringsnummer / VAT-nummer).

Формат: SE + 10-значный organisationsnummer + 01
Пример: org.nr 5560000001 → SE556000000101

Шведский VAT-номер всегда заканчивается на "01" для юридических лиц.
Суффикс "01" означает первый (и обычно единственный) VAT-регистрационный
номер для данной организации. Физлица-ИП используют свой personnummer
в том же формате.

EU VIES проверка: https://ec.europa.eu/taxation_customs/vies/
Skatteverket:     https://www.skatteverket.se/
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .validators import normalize, validate
from .exceptions import ValidationError

# Регулярное выражение для формата SE{10 цифр}01
_VAT_RE = re.compile(r"^SE(\d{10})01$", re.IGNORECASE)

# Стандартный суффикс для юридических лиц Швеции
_LEGAL_SUFFIX = "01"


# ─────────────────────────────────────────────
#  Датакласс результата
# ─────────────────────────────────────────────

@dataclass
class VatInfo:
    """
    Информация о VAT-номере компании.

    Поля:
        org_number      — нормализованный organisationsnummer (10 цифр)
        vat_number      — полный VAT-номер в формате SE{orgnr}01
        is_registered   — зарегистрирована ли компания как плательщик момс
                          None = информация отсутствует (требует проверки)
        suffix          — суффикс VAT (всегда "01" для юрлиц Швеции)
        eu_format       — VAT в формате с пробелами: "SE 556 000 000 101"
        skatteverket_url — прямая ссылка на проверку в Skatteverket

    Пример:
        info = generate_vat_info("5560000001", is_registered=True)
        print(info.vat_number)   # → "SE556000000101"
        print(info.eu_format)    # → "SE 556 000 000 101"
    """
    org_number:       str
    vat_number:       str
    is_registered:    Optional[bool]
    suffix:           str = "01"
    eu_format:        str = ""
    skatteverket_url: str = ""

    def __post_init__(self):
        if not self.eu_format:
            self.eu_format = _format_eu(self.vat_number)
        if not self.skatteverket_url:
            self.skatteverket_url = (
                "https://www.skatteverket.se/foretagochorganisationer/"
                "skatter/momsochpunktskatteregistrering/"
                "momsregistrering.4.18e1b10334ebe8bc80002929.html"
            )

    def to_dict(self) -> dict:
        return {
            "organisationsnummer": self.org_number,
            "vat_nummer":          self.vat_number,
            "eu_format":           self.eu_format,
            "moms_registrerad":    self.is_registered,
            "suffix":              self.suffix,
            "skatteverket_url":    self.skatteverket_url,
        }


# ─────────────────────────────────────────────
#  Публичные функции
# ─────────────────────────────────────────────

def generate_vat_number(orgnr: str) -> str:
    """
    Генерирует шведский VAT-номер из organisationsnummer.

    Формат: SE + 10 цифр + 01

    Параметры:
        orgnr — organisationsnummer (10 цифр, дефисы допустимы)

    Возвращает:
        VAT-номер, например "SE556000000101"

    Raises:
        ValidationError — если orgnr некорректен

    Примеры:
        >>> generate_vat_number("5560000001")
        'SE556000000101'
        >>> generate_vat_number("556-000-0001")
        'SE556000000101'
    """
    clean = validate(orgnr)
    return f"SE{clean}{_LEGAL_SUFFIX}"


def generate_vat_info(
    orgnr: str,
    is_registered: Optional[bool] = None,
) -> VatInfo:
    """
    Создаёт полный объект VatInfo для компании.

    Параметры:
        orgnr         — organisationsnummer
        is_registered — True если компания зарегистрирована как плательщик момс,
                        False если нет, None если статус неизвестен

    Возвращает:
        VatInfo с полным набором данных

    Raises:
        ValidationError — если orgnr некорректен

    Примеры:
        >>> info = generate_vat_info("5560000001", is_registered=True)
        >>> info.vat_number
        'SE556000000101'
        >>> info.is_registered
        True
    """
    clean = validate(orgnr)
    vat = f"SE{clean}{_LEGAL_SUFFIX}"
    return VatInfo(
        org_number=clean,
        vat_number=vat,
        is_registered=is_registered,
    )


def parse_vat_number(vat: str) -> str:
    """
    Извлекает organisationsnummer из VAT-номера.

    Параметры:
        vat — VAT-номер в формате SE{10 цифр}01

    Возвращает:
        organisationsnummer (10 цифр)

    Raises:
        ValidationError — если формат VAT-номера неверен

    Примеры:
        >>> parse_vat_number("SE556000000101")
        '5560000001'
        >>> parse_vat_number("se 556 000 000 101")
        '5560000001'
    """
    normalized = _normalize_vat_input(vat)
    match = _VAT_RE.match(normalized)
    if not match:
        raise ValidationError(
            f"Неверный формат VAT-номера: '{vat}'. "
            "Ожидается SE + 10 цифр + 01, например SE556000000101"
        )
    return match.group(1)


def is_valid_vat_format(vat: str) -> bool:
    """
    Проверяет, соответствует ли строка формату шведского VAT-номера.

    Параметры:
        vat — строка для проверки

    Возвращает:
        True если формат корректен, False иначе

    Примеры:
        >>> is_valid_vat_format("SE556000000101")
        True
        >>> is_valid_vat_format("GB123456789")
        False
    """
    try:
        parse_vat_number(vat)
        return True
    except ValidationError:
        return False


def format_vat_eu(vat_or_orgnr: str) -> str:
    """
    Форматирует VAT-номер или org.nr в читаемый EU-формат с пробелами.

    Параметры:
        vat_or_orgnr — VAT-номер (SE...01) или organisationsnummer

    Возвращает:
        Строку вида "SE 556 000 000 101"

    Примеры:
        >>> format_vat_eu("SE556000000101")
        'SE 556 000 000 101'
        >>> format_vat_eu("5560000001")
        'SE 556 000 000 101'
    """
    cleaned = _normalize_vat_input(vat_or_orgnr)
    if _VAT_RE.match(cleaned):
        return _format_eu(cleaned)
    # Предполагаем, что это org.nr
    vat = generate_vat_number(vat_or_orgnr)
    return _format_eu(vat)


# ─────────────────────────────────────────────
#  Внутренние утилиты
# ─────────────────────────────────────────────

def _normalize_vat_input(vat: str) -> str:
    """Убирает пробелы и переводит в верхний регистр."""
    return vat.replace(" ", "").upper()


def _format_eu(vat: str) -> str:
    """
    Форматирует VAT-номер с пробелами для читаемости.

    SE556000000101 → SE 556 000 000 101
    """
    # SE + digits + 01
    # SE [3] [3] [3] [3] = SE NNN NNN NNN NNN
    digits = vat[2:]  # убираем "SE"
    groups = [digits[i:i+3] for i in range(0, len(digits), 3)]
    return "SE " + " ".join(groups)
