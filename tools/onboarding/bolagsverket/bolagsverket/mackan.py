"""
bolagsverket.mackan
-------------------
Клиент для mackan.eu — бесплатного прокси к Bolagsverket API.

НЕ требует регистрации, договора или API-ключей.
Данные те же, что и в официальном Bolagsverket API (Värdefulla datamängder v1).

Ограничения:
  - Неофициальный сервис, не гарантирует uptime
  - Нет скачивания iXBRL-документов (только список)
  - Для продакшена рекомендуется официальный BolagsverketClient

Эндпоинт:
  GET https://mackan.eu/tools/bolagsverket/get_data.php?orgnr={orgnr}

Пример ответа mackan.eu:
  {
    "company_name":   "Spotify AB",
    "org_number":     "5590877446",
    "status":         "Aktiv",
    "legal_form":     "Aktiebolag",
    "registration_date": "2006-04-23",
    "business_description": "...",
    "address": {
      "street":      "Regeringsgatan 19",
      "postal_code": "111 53",
      "city":        "Stockholm",
      "country":     "Sverige"
    },
    "sni_codes": ["59200"],
    "annual_reports": [
      {"document_id": "abc", "period": "2023", "date": "2024-03-15"}
    ]
  }
"""

from __future__ import annotations

from typing import Optional

import requests

from .base import BaseCompanyClient
from .exceptions import ApiError, NotFoundError, RateLimitError
from .models import Address, AnnualReport, Company, SniCode
from .validators import validate
from .vat import generate_vat_info

# Эндпоинт mackan.eu
_MACKAN_URL = "https://mackan.eu/tools/bolagsverket/get_data.php"

# Те же SNI-метки что и в основном клиенте
_SNI_LABELS: dict[str, str] = {
    "01": "Растениеводство и животноводство",
    "02": "Лесоводство",
    "03": "Рыболовство и аквакультура",
    "10": "Производство продуктов питания",
    "13": "Текстильная промышленность",
    "16": "Деревообработка",
    "20": "Химическая промышленность",
    "22": "Производство резиновых и пластмассовых изделий",
    "25": "Производство металлических изделий",
    "26": "Производство электроники",
    "28": "Производство машин и оборудования",
    "33": "Ремонт и монтаж машин",
    "35": "Электро-, газо- и теплоснабжение",
    "36": "Водоснабжение",
    "38": "Сбор и утилизация отходов",
    "41": "Строительство зданий",
    "42": "Гражданское строительство",
    "43": "Специализированные строительные работы",
    "45": "Торговля и ремонт автомобилей",
    "46": "Оптовая торговля",
    "47": "Розничная торговля",
    "49": "Сухопутный транспорт",
    "52": "Складирование и вспомогательные транспортные услуги",
    "55": "Гостиничный бизнес",
    "56": "Общественное питание",
    "58": "Издательская деятельность",
    "62": "Разработка ПО и ИТ-консалтинг",
    "63": "Информационные услуги",
    "64": "Финансовые услуги",
    "65": "Страхование",
    "68": "Операции с недвижимостью",
    "69": "Юридические и бухгалтерские услуги",
    "70": "Управленческий консалтинг",
    "71": "Архитектура и инжиниринг",
    "72": "Научные исследования",
    "73": "Реклама и маркетинг",
    "74": "Прочая профессиональная деятельность",
    "77": "Аренда и лизинг",
    "78": "Трудоустройство и кадровые агентства",
    "80": "Охранная деятельность",
    "81": "Обслуживание зданий",
    "85": "Образование",
    "86": "Здравоохранение",
    "87": "Дома-интернаты",
    "88": "Социальные услуги",
    "90": "Творческая деятельность",
    "96": "Прочие персональные услуги",
}


class MackAnClient(BaseCompanyClient):
    """
    Клиент mackan.eu — бесплатный прокси без API-ключей.

    Использует тот же интерфейс, что и BolagsverketClient.
    Подходит для разработки, прототипирования и небольших объёмов запросов.

    Пример:
        client = MackAnClient()
        company = client.get_company("5560000001")
        print(company.name, company.vat_number)

    Для продакшена:
        client = BolagsverketClient("client_id", "secret")
    """

    SOURCE = "mackan.eu (Bolagsverket Värdefulla datamängder v1 proxy)"

    def __init__(self, timeout: int = 15, validate_orgnr: bool = True):
        """
        Параметры:
            timeout        — таймаут HTTP-запросов в секундах (по умолчанию 15)
            validate_orgnr — проверять org.nr перед запросом (по умолчанию True)
        """
        self._timeout = timeout
        self._validate = validate_orgnr
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/json",
            "User-Agent": "bolagsverket-py/1.1 (python library)",
        })

    @property
    def source_name(self) -> str:
        return self.SOURCE

    # ── Публичные методы ──────────────────────

    def get_company(self, orgnr: str, include_docs: bool = False) -> Company:
        """
        Возвращает данные компании через mackan.eu.

        Параметры:
            orgnr        — organisationsnummer
            include_docs — если True, включает список годовых отчётов

        Raises:
            ValidationError / NotFoundError / RateLimitError / ApiError
        """
        clean = self._clean_orgnr(orgnr)
        raw = self._fetch(clean)
        return self._parse(clean, raw, include_docs=include_docs)

    def get_documents(self, orgnr: str) -> list[AnnualReport]:
        """
        Возвращает список годовых отчётов компании.

        Параметры:
            orgnr — organisationsnummer
        """
        clean = self._clean_orgnr(orgnr)
        raw = self._fetch(clean)
        return _parse_documents(raw)

    # ── Внутренние методы ─────────────────────

    def _clean_orgnr(self, orgnr: str) -> str:
        if self._validate:
            return validate(orgnr)
        return orgnr.replace("-", "").replace(" ", "")

    def _fetch(self, orgnr: str) -> dict:
        """Выполняет GET-запрос к mackan.eu и возвращает JSON."""
        try:
            resp = self._session.get(
                _MACKAN_URL,
                params={"orgnr": orgnr},
                timeout=self._timeout,
            )
        except requests.ConnectionError as exc:
            raise ApiError(0, f"Не удалось подключиться к mackan.eu: {exc}") from exc
        except requests.Timeout:
            raise ApiError(0, "Таймаут при запросе к mackan.eu") from None

        if resp.status_code == 404:
            raise NotFoundError(orgnr)
        if resp.status_code == 429:
            raise RateLimitError("Превышен лимит запросов mackan.eu. Подождите немного.")
        if not resp.ok:
            raise ApiError(resp.status_code, resp.text[:300])

        data = resp.json()

        # mackan.eu возвращает {"error": "..."} при ненайденной компании
        if isinstance(data, dict) and data.get("error"):
            raise NotFoundError(orgnr)

        return data

    def _parse(self, orgnr: str, raw: dict, include_docs: bool) -> Company:
        """Преобразует ответ mackan.eu в объект Company.

        Поддерживает два формата:
          - Упрощённый: {"company_name": ..., "address": {...}, ...}
          - Нативный Bolagsverket: {"organisationer": [{...}]}
        """
        # Если ответ в нативном формате Bolagsverket — разворачиваем
        org_list = raw.get("organisationer")
        if org_list and isinstance(org_list, list) and org_list:
            return self._parse_native(orgnr, org_list[0], raw)

        # Упрощённый формат (legacy)
        addr_raw = raw.get("address") or raw.get("adress") or {}
        address = Address(
            street=_pick(addr_raw, "street", "gatuadress"),
            postal_code=_pick(addr_raw, "postal_code", "postnummer"),
            city=_pick(addr_raw, "city", "postort"),
            country=_pick(addr_raw, "country", "land"),
        )
        raw_sni = raw.get("sni_codes") or raw.get("sniKoder") or []
        sni_codes = [
            SniCode(code=str(c), sector=_SNI_LABELS.get(str(c)[:2], ""))
            for c in raw_sni
        ]
        is_vat = _pick_bool(raw, "vat_registered", "registreradForMoms", "momsRegistrerad")
        vat_info = generate_vat_info(orgnr, is_registered=is_vat)
        return Company(
            org_number=_pick(raw, "org_number", "organisationsnummer") or orgnr,
            name=_pick(raw, "company_name", "namn"),
            legal_form=_pick(raw, "legal_form", "organisationsform"),
            status=_pick(raw, "status"),
            registration_date=_pick(raw, "registration_date", "registreringsdatum"),
            business_description=_pick(raw, "business_description", "verksamhetsbeskrivning"),
            address=address,
            sni_codes=sni_codes,
            annual_reports=_parse_documents(raw) if include_docs else [],
            is_vat_registered=is_vat,
            vat_info=vat_info,
            raw={**raw, "_source": self.SOURCE},
        )

    def _parse_native(self, orgnr: str, org: dict, raw: dict) -> Company:
        """Парсинг нативного формата Bolagsverket API."""
        # Название
        namn_lista = (org.get("organisationsnamn") or {}).get("organisationsnamnLista") or []
        name = namn_lista[0].get("namn") if namn_lista else None

        # Статус (verksamOrganisation.kod == "JA" → Aktiv)
        verk = (org.get("verksamOrganisation") or {}).get("kod", "")
        status = "Aktiv" if verk == "JA" else "Avregistrerad"

        # Datum
        reg_date = (org.get("organisationsdatum") or {}).get("registreringsdatum")

        # Organisationsform
        legal_form = (org.get("organisationsform") or {}).get("klartext")

        # Beskrivning
        business_desc = (org.get("verksamhetsbeskrivning") or {}).get("beskrivning")

        # Adress
        pa = (org.get("postadressOrganisation") or {}).get("postadress") or {}
        address = Address(
            street=pa.get("utdelningsadress"),
            postal_code=_fmt_postnr(pa.get("postnummer")),
            city=(pa.get("postort") or "").title() or None,
            country="SE",
        )

        # SNI
        sni_list = (org.get("naringsgrenOrganisation") or {}).get("sni") or []
        sni_codes = [
            SniCode(code=s["kod"].strip(), sector=s.get("klartext", ""))
            for s in sni_list
            if s.get("kod", "").strip()
        ]

        is_vat = None
        vat_info = generate_vat_info(orgnr, is_registered=is_vat)

        return Company(
            org_number=orgnr,
            name=name,
            legal_form=legal_form,
            status=status,
            registration_date=reg_date,
            business_description=business_desc,
            address=address,
            sni_codes=sni_codes,
            annual_reports=[],
            is_vat_registered=is_vat,
            vat_info=vat_info,
            raw={**raw, "_source": self.SOURCE},
        )


# ── Вспомогательные функции ───────────────────

def _parse_documents(raw: dict) -> list[AnnualReport]:
    """Извлекает годовые отчёты из ответа mackan.eu."""
    docs_raw = raw.get("annual_reports") or raw.get("dokument") or []
    result = []
    for d in docs_raw:
        result.append(AnnualReport(
            document_id=_pick(d, "document_id", "dokumentid") or "",
            doc_type=_pick(d, "type", "typ"),
            period=_pick(d, "period"),
            submitted_date=_pick(d, "date", "datum"),
        ))
    return result


def _pick(data: dict, *keys: str) -> Optional[str]:
    """Возвращает первое найденное значение из словаря по списку ключей."""
    for key in keys:
        val = data.get(key)
        if val is not None:
            return val
    return None


def _fmt_postnr(raw: Optional[str]) -> Optional[str]:
    """'37450' → '374 50'"""
    if not raw:
        return None
    s = raw.strip()
    if len(s) == 5 and s.isdigit():
        return f"{s[:3]} {s[3:]}"
    return s


def _pick_bool(data: dict, *keys: str) -> Optional[bool]:
    """Возвращает первое найденное булево значение."""
    for key in keys:
        val = data.get(key)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            lower = val.lower()
            if lower in ("true", "1", "yes", "registrerad"):
                return True
            if lower in ("false", "0", "no", "ej registrerad"):
                return False
    return None
