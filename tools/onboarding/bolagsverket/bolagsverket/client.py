"""
bolagsverket.client
-------------------
HTTP-клиент: выполняет запросы к API и преобразует ответы в модели.
"""

from __future__ import annotations

from typing import Optional

import requests

from .auth import TokenManager
from .base import BaseCompanyClient
from .exceptions import ApiError, AuthError, NotFoundError, RateLimitError
from .models import Address, AnnualReport, Company, SniCode
from .validators import validate
from .vat import generate_vat_info

BASE_URL = "https://api.bolagsverket.se/vd/v1"

# SNI → название сектора
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


class BolagsverketClient(BaseCompanyClient):
    """
    Основной клиент для работы с Bolagsverket API.

    Примеры:
        client = BolagsverketClient("client_id", "client_secret")

        # Получить данные компании
        company = client.get_company("5590877446")
        print(company.name)

        # Получить данные + годовые отчёты
        company = client.get_company("5590877446", include_docs=True)
        for report in company.annual_reports:
            print(report.period)

        # Только список документов
        docs = client.get_documents("5590877446")

        # Скачать документ
        zip_bytes = client.download_document("abc123")
    """

    SOURCE = "Bolagsverket Värdefulla datamängder API v1"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        timeout: int = 15,
        validate_orgnr: bool = True,
    ):
        """
        Параметры:
            client_id      — OAuth2 client_id от Bolagsverket
            client_secret  — OAuth2 client_secret от Bolagsverket
            timeout        — таймаут HTTP-запросов в секундах (по умолчанию 15)
            validate_orgnr — валидировать org.nr перед запросом (по умолчанию True)
        """
        self._auth = TokenManager(client_id, client_secret, timeout)
        self._timeout = timeout
        self._validate = validate_orgnr
        self._session = requests.Session()

    # ── Публичные методы ──────────────────────

    @property
    def source_name(self) -> str:
        return self.SOURCE

    def get_company(self, orgnr: str, include_docs: bool = False) -> Company:
        """
        Возвращает полную информацию о компании.

        Параметры:
            orgnr        — organisationsnummer (10 цифр, дефисы допустимы)
            include_docs — если True, дополнительно запрашивает список
                           годовых отчётов и добавляет их в Company.annual_reports

        Raises:
            ValidationError — если orgnr не прошёл проверку
            NotFoundError   — если компания не найдена
            AuthError       — при ошибке аутентификации
            RateLimitError  — при превышении лимита запросов
            ApiError        — при прочих ошибках API
        """
        clean = self._clean_orgnr(orgnr)
        raw = self._get(f"/organisationer/{clean}")
        company = self._parse_company(clean, raw)

        if include_docs:
            docs_raw = self._get(f"/organisationer/{clean}/dokumentlista")
            company.annual_reports = self._parse_documents(docs_raw)

        return company

    def get_documents(self, orgnr: str) -> list[AnnualReport]:
        """
        Возвращает список годовых отчётов компании.

        Параметры:
            orgnr — organisationsnummer

        Raises:
            ValidationError / NotFoundError / AuthError / RateLimitError / ApiError
        """
        clean = self._clean_orgnr(orgnr)
        raw = self._get(f"/organisationer/{clean}/dokumentlista")
        return self._parse_documents(raw)

    def download_document(self, document_id: str) -> bytes:
        """
        Скачивает годовой отчёт по document_id.

        Возвращает содержимое ZIP-архива в байтах (формат iXBRL).

        Пример:
            data = client.download_document("abc123")
            with open("report.zip", "wb") as f:
                f.write(data)
        """
        token = self._auth.get_token()
        url = f"{BASE_URL}/dokument/{document_id}"
        resp = self._session.get(url, headers=self._headers(token), timeout=self._timeout)
        self._raise_for_status(resp, document_id)
        return resp.content

    def is_construction_company(self, orgnr: str) -> bool:
        """
        Быстрая проверка: относится ли компания к строительной отрасли (SNI 41–43).

        Параметры:
            orgnr — organisationsnummer
        """
        company = self.get_company(orgnr)
        return company.is_construction

    # ── Внутренние методы ─────────────────────

    def _clean_orgnr(self, orgnr: str) -> str:
        if self._validate:
            return validate(orgnr)
        return orgnr.replace("-", "").replace(" ", "")

    def _get(self, path: str) -> dict:
        token = self._auth.get_token()
        url = f"{BASE_URL}{path}"
        resp = self._session.get(url, headers=self._headers(token), timeout=self._timeout)
        self._raise_for_status(resp, path)
        return resp.json()

    @staticmethod
    def _headers(token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    @staticmethod
    def _raise_for_status(resp: requests.Response, context: str = "") -> None:
        if resp.ok:
            return
        code = resp.status_code
        body = resp.text[:300]
        if code == 401:
            raise AuthError(f"HTTP 401 при запросе '{context}'")
        if code == 404:
            raise NotFoundError(context)
        if code == 429:
            raise RateLimitError("Превышен лимит запросов (429). Подождите 60 сек.")
        raise ApiError(code, body)

    # ── Парсинг ───────────────────────────────

    @staticmethod
    def _parse_company(orgnr: str, raw: dict) -> Company:
        addr_raw = raw.get("adress", {})
        address = Address(
            street=addr_raw.get("gatuadress"),
            postal_code=addr_raw.get("postnummer"),
            city=addr_raw.get("postort"),
            country=addr_raw.get("land"),
        )

        sni_codes = [
            SniCode(
                code=code,
                sector=_SNI_LABELS.get(code[:2], ""),
            )
            for code in raw.get("sniKoder", [])
        ]

        # Статус момс из SCB-данных:
        # Поле "registreradForMoms", "momsRegistrerad" или флаги активности
        # SCB помечает компанию как активную если она зарег. для moms/arbetsgivare/F-skatt
        is_vat = _parse_vat_status(raw)

        vat_info = generate_vat_info(orgnr, is_registered=is_vat)

        return Company(
            org_number=raw.get("organisationsnummer", orgnr),
            name=raw.get("namn"),
            legal_form=raw.get("organisationsform"),
            status=raw.get("status"),
            registration_date=raw.get("registreringsdatum"),
            business_description=raw.get("verksamhetsbeskrivning"),
            address=address,
            sni_codes=sni_codes,
            is_vat_registered=is_vat,
            vat_info=vat_info,
            raw=raw,
        )

    @staticmethod
    def _parse_documents(raw: dict) -> list[AnnualReport]:
        return [
            AnnualReport(
                document_id=d.get("dokumentid", ""),
                doc_type=d.get("typ"),
                period=d.get("period"),
                submitted_date=d.get("datum"),
            )
            for d in raw.get("dokument", [])
        ]


def _parse_vat_status(raw: dict) -> Optional[bool]:
    """
    Извлекает статус регистрации момс из ответа API.

    Bolagsverket/SCB могут возвращать разные поля в зависимости от версии:
      - registreradForMoms  (bool)
      - momsRegistrerad     (bool)
      - momsStatus          ("Registrerad" / "Ej registrerad")
      - foretagsstatus      (активна ли вообще компания)

    Возвращает True/False/None (если поля нет — статус неизвестен).
    """
    # Прямые булевы поля
    for key in ("registreradForMoms", "momsRegistrerad", "vatRegistered"):
        val = raw.get(key)
        if isinstance(val, bool):
            return val

    # Строковые поля
    moms_status = raw.get("momsStatus", "")
    if isinstance(moms_status, str):
        lower = moms_status.lower()
        if "registrerad" in lower and "ej" not in lower:
            return True
        if "ej registrerad" in lower or lower == "false":
            return False

    # Статус компании как косвенный признак:
    # Активные компании скорее всего зарегистрированы для момс,
    # но это предположение — возвращаем None (неизвестно)
    return None
