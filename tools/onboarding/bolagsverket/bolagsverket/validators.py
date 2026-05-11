"""
bolagsverket.validators
-----------------------
Валидация и нормализация organisationsnummer.
"""

from .exceptions import ValidationError


def normalize(orgnr: str) -> str:
    """
    Нормализует organisationsnummer — убирает дефисы и пробелы.

    Примеры:
        "559-087-7446" → "5590877446"
        "559 087 7446" → "5590877446"
        "5590877446"   → "5590877446"
    """
    return orgnr.replace("-", "").replace(" ", "")


def validate(orgnr: str) -> str:
    """
    Проверяет и нормализует organisationsnummer.

    Выполняет:
      1. Нормализацию (убирает дефисы/пробелы)
      2. Проверку формата (ровно 10 цифр)
      3. Проверку контрольной цифры по алгоритму Luhn

    Возвращает нормализованный номер (10 цифр, строка).
    Raises ValidationError при ошибке формата.
    Raises ValidationError при неверной контрольной цифре.
    """
    clean = normalize(orgnr)

    if not clean.isdigit() or len(clean) != 10:
        raise ValidationError(
            f"Неверный формат organisationsnummer: '{orgnr}'. "
            "Ожидается 10 цифр (дефисы допустимы)."
        )

    if not _luhn_check(clean):
        raise ValidationError(
            f"Неверная контрольная цифра в organisationsnummer '{orgnr}'. "
            f"Ожидалась {_luhn_expected(clean)}."
        )

    return clean


def is_valid(orgnr: str) -> bool:
    """Возвращает True, если organisationsnummer корректен (без исключений)."""
    try:
        validate(orgnr)
        return True
    except ValidationError:
        return False


def legal_form_hint(orgnr: str) -> str:
    """
    Возвращает вероятную правовую форму по первой цифре org.nr.
    Только подсказка — не гарантия.
    """
    clean = normalize(orgnr)
    if not clean:
        return "Неизвестно"
    hints = {
        "1": "Dödsbo (наследственное имущество)",
        "2": "Государство / муниципалитет / приход",
        "3": "Иностранная компания",
        "5": "Aktiebolag (AB)",
        "6": "Enskild firma (ИП)",
        "7": "Ekonomisk förening / Bostadsrättsförening",
        "8": "Ideell förening / Stiftelse",
        "9": "Handelsbolag / Kommanditbolag",
    }
    return hints.get(clean[0], "Неизвестно")


# ── Внутренние функции ────────────────────────

def _luhn_expected(clean: str) -> int:
    """Возвращает ожидаемую контрольную цифру по алгоритму Luhn."""
    digits = [int(d) for d in clean[:-1]]
    total = 0
    for i, d in enumerate(digits):
        v = d * 2 if i % 2 == 0 else d
        total += v // 10 + v % 10
    return (10 - total % 10) % 10


def _luhn_check(clean: str) -> bool:
    """Возвращает True, если контрольная цифра совпадает."""
    return _luhn_expected(clean) == int(clean[-1])
