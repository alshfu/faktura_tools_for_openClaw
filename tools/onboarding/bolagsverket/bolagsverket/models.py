"""
bolagsverket.models
-------------------
Датаклассы для всех структур данных, возвращаемых API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .vat import VatInfo


# ─────────────────────────────────────────────
#  Вспомогательные структуры
# ─────────────────────────────────────────────

@dataclass
class Address:
    """Зарегистрированный адрес компании."""
    street: Optional[str] = None       # gatuadress
    postal_code: Optional[str] = None  # postnummer
    city: Optional[str] = None         # postort
    country: Optional[str] = None      # land

    def __str__(self) -> str:
        parts = [p for p in [self.street, self.postal_code, self.city] if p]
        return ", ".join(parts)


@dataclass
class SniCode:
    """Один SNI-код с расшифровкой."""
    code: str
    sector: str = ""  # расшифровка сектора

    def is_construction(self) -> bool:
        """Возвращает True, если код относится к строительству (41–43)."""
        return self.code.startswith(("41", "42", "43"))

    def __str__(self) -> str:
        return f"{self.code} — {self.sector}" if self.sector else self.code


@dataclass
class AnnualReport:
    """Один годовой отчёт (årsredovisning)."""
    document_id: str
    doc_type: Optional[str] = None
    period: Optional[str] = None
    submitted_date: Optional[str] = None


# ─────────────────────────────────────────────
#  Главная модель
# ─────────────────────────────────────────────

@dataclass
class Company:
    """
    Полная информация о компании.

    Атрибуты обогащены скриптом (возраст, флаг строительства)
    в дополнение к тому, что вернул API.
    """

    # Идентификация
    org_number: str
    name: Optional[str] = None
    legal_form: Optional[str] = None
    status: Optional[str] = None

    # Даты
    registration_date: Optional[str] = None

    # Описание
    business_description: Optional[str] = None

    # Адрес
    address: Address = field(default_factory=Address)

    # Отраслевые коды
    sni_codes: list[SniCode] = field(default_factory=list)

    # Годовые отчёты (заполняется при запросе с docs=True)
    annual_reports: list[AnnualReport] = field(default_factory=list)

    # VAT / Moms (заполняется клиентом на основе данных API)
    is_vat_registered: Optional[bool] = None   # зарегистрирован ли плательщиком НДС
    vat_info: Optional[object] = field(default=None, repr=False)  # VatInfo | None

    # Необработанный ответ API
    raw: dict = field(default_factory=dict, repr=False)

    # ── Вычисляемые свойства ──────────────────

    @property
    def age_years(self) -> Optional[float]:
        """Возраст компании в годах. None, если дата регистрации неизвестна."""
        if not self.registration_date:
            return None
        try:
            reg = date.fromisoformat(self.registration_date)
            delta = date.today() - reg
            return round(delta.days / 365.25, 1)
        except ValueError:
            return None

    @property
    def is_active(self) -> bool:
        """True, если статус компании — Aktiv."""
        return (self.status or "").lower() == "aktiv"

    @property
    def is_construction(self) -> bool:
        """True, если хотя бы один SNI-код относится к строительству (41–43)."""
        return any(c.is_construction() for c in self.sni_codes)

    @property
    def construction_codes(self) -> list[SniCode]:
        """Список строительных SNI-кодов."""
        return [c for c in self.sni_codes if c.is_construction()]

    @property
    def vat_number(self) -> Optional[str]:
        """
        Momsregistreringsnummer в формате SE{orgnr}01.
        Возвращается только если компания зарегистрирована как плательщик момс.
        Если статус неизвестен — возвращает потенциальный номер с пометкой.
        """
        if self.is_vat_registered is False:
            return None
        return f"SE{self.org_number}01"

    @property
    def vat_number_eu_format(self) -> Optional[str]:
        """VAT-номер в EU-формате с пробелами: 'SE 556 000 000 101'."""
        vat = self.vat_number
        if not vat:
            return None
        digits = vat[2:]
        groups = [digits[i:i+3] for i in range(0, len(digits), 3)]
        return "SE " + " ".join(groups)

    # ── Сериализация ──────────────────────────

    def to_dict(self, include_raw: bool = True) -> dict:
        """Полная сериализация в словарь."""
        result = {
            "meta": {
                "fetched_at": datetime.now().isoformat(timespec="seconds"),
                "source": "Bolagsverket Värdefulla datamängder API v1",
            },
            "grunduppgifter": {
                "organisationsnummer": self.org_number,
                "namn": self.name,
                "organisationsform": self.legal_form,
                "status": self.status,
                "registreringsdatum": self.registration_date,
                "alder_ar": self.age_years,
                "verksamhetsbeskrivning": self.business_description,
            },
            "adress": {
                "gatuadress": self.address.street,
                "postnummer": self.address.postal_code,
                "postort": self.address.city,
                "land": self.address.country,
            },
            "sni": {
                "koder": [
                    {"kod": c.code, "sektor": c.sector}
                    for c in self.sni_codes
                ],
                "ar_byggforetag": self.is_construction,
                "byggkoder": [c.code for c in self.construction_codes],
            },
            "moms": {
                "moms_registrerad":    self.is_vat_registered,
                "vat_nummer":          self.vat_number,
                "eu_format":           self.vat_number_eu_format,
                "notering":            (
                    "Registrerad" if self.is_vat_registered is True
                    else "Ej registrerad" if self.is_vat_registered is False
                    else "Status okänd – verifiera via Skatteverket"
                ),
            },
        }

        if self.annual_reports:
            result["arsredovisningar"] = {
                "antal": len(self.annual_reports),
                "dokument": [
                    {
                        "dokumentid": r.document_id,
                        "typ": r.doc_type,
                        "period": r.period,
                        "datum": r.submitted_date,
                    }
                    for r in self.annual_reports
                ],
            }

        if include_raw:
            result["raw_api_response"] = self.raw

        return result
