"""
tests/test_library.py
---------------------
Тесты библиотеки bolagsverket (без реальных API-вызовов).
Запуск: pytest tests/
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from bolagsverket import (
    BolagsverketClient,
    Company,
    NotFoundError,
    RateLimitError,
    ValidationError,
    is_valid,
    legal_form_hint,
    normalize,
    validate,
)
from bolagsverket.models import Address, AnnualReport, SniCode


# ─────────────────────────────────────────────
#  Тесты валидации
# ─────────────────────────────────────────────

class TestNormalize:
    def test_removes_dashes(self):
        assert normalize("559-087-7446") == "5590877446"

    def test_removes_spaces(self):
        assert normalize("559 087 7446") == "5590877446"

    def test_already_clean(self):
        assert normalize("5590877446") == "5590877446"


VALID_ORGNR  = "5590877444"   # контрольная цифра проверена алгоритмом Luhn
VALID_ORGNR2 = "5560000001"   # второй валидный номер
VALID_DASHES = "556-000-0001" # тот же с дефисами


class TestValidate:
    def test_valid_orgnr(self):
        result = validate(VALID_ORGNR)
        assert result == VALID_ORGNR

    def test_accepts_dashes(self):
        result = validate(VALID_DASHES)
        assert result == "5560000001"

    def test_too_short(self):
        with pytest.raises(ValidationError, match="формат"):
            validate("123456789")

    def test_not_digits(self):
        with pytest.raises(ValidationError, match="формат"):
            validate("55908ABCDE")

    def test_wrong_check_digit(self):
        with pytest.raises(ValidationError, match="контрольная"):
            validate("5590877440")  # последняя цифра изменена


class TestIsValid:
    def test_valid(self):
        assert is_valid(VALID_ORGNR) is True

    def test_invalid(self):
        assert is_valid("1234567890") is False


class TestLegalFormHint:
    def test_aktiebolag(self):
        assert "Aktiebolag" in legal_form_hint(VALID_ORGNR)

    def test_enskild_firma(self):
        assert "Enskild" in legal_form_hint("6012345678")

    def test_unknown(self):
        assert legal_form_hint("") == "Неизвестно"


# ─────────────────────────────────────────────
#  Тесты моделей
# ─────────────────────────────────────────────

class TestSniCode:
    def test_is_construction_true(self):
        assert SniCode("41200").is_construction() is True
        assert SniCode("42110").is_construction() is True
        assert SniCode("43910").is_construction() is True

    def test_is_construction_false(self):
        assert SniCode("62010").is_construction() is False
        assert SniCode("47110").is_construction() is False

    def test_str_with_sector(self):
        sni = SniCode("41200", sector="Строительство зданий")
        assert "41200" in str(sni)
        assert "Строительство" in str(sni)


class TestCompany:
    def _make_company(self, **kwargs) -> Company:
        defaults = dict(
            org_number="5590877446",
            name="Test AB",
            status="Aktiv",
            registration_date="2010-06-15",
            sni_codes=[],
        )
        defaults.update(kwargs)
        return Company(**defaults)

    def test_is_active_true(self):
        c = self._make_company(status="Aktiv")
        assert c.is_active is True

    def test_is_active_false(self):
        c = self._make_company(status="Avregistrerad")
        assert c.is_active is False

    def test_age_years(self):
        c = self._make_company(registration_date="2000-01-01")
        assert c.age_years > 20

    def test_age_none_when_no_date(self):
        c = self._make_company(registration_date=None)
        assert c.age_years is None

    def test_is_construction_true(self):
        c = self._make_company(sni_codes=[SniCode("41200"), SniCode("62010")])
        assert c.is_construction is True

    def test_is_construction_false(self):
        c = self._make_company(sni_codes=[SniCode("62010")])
        assert c.is_construction is False

    def test_construction_codes_filtered(self):
        c = self._make_company(sni_codes=[SniCode("41200"), SniCode("62010"), SniCode("43910")])
        codes = [s.code for s in c.construction_codes]
        assert "41200" in codes
        assert "43910" in codes
        assert "62010" not in codes

    def test_to_dict_structure(self):
        c = self._make_company(sni_codes=[SniCode("41200", "Строительство")])
        d = c.to_dict(include_raw=False)
        assert "grunduppgifter" in d
        assert "adress" in d
        assert "sni" in d
        assert "meta" in d
        assert "raw_api_response" not in d

    def test_to_dict_with_raw(self):
        c = self._make_company(raw={"some": "data"})
        d = c.to_dict(include_raw=True)
        assert d["raw_api_response"] == {"some": "data"}

    def test_to_dict_annual_reports(self):
        c = self._make_company()
        c.annual_reports = [AnnualReport("doc1", "Arsredovisning", "2023", "2024-03-01")]
        d = c.to_dict()
        assert d["arsredovisningar"]["antal"] == 1
        assert d["arsredovisningar"]["dokument"][0]["dokumentid"] == "doc1"


# ─────────────────────────────────────────────
#  Тесты клиента (моки)
# ─────────────────────────────────────────────

MOCK_COMPANY_RESPONSE = {
    "organisationsnummer": VALID_ORGNR,
    "namn": "Spotify AB",
    "organisationsform": "Aktiebolag",
    "status": "Aktiv",
    "registreringsdatum": "2006-04-23",
    "verksamhetsbeskrivning": "Musikstreaming",
    "adress": {
        "gatuadress": "Regeringsgatan 19",
        "postnummer": "111 53",
        "postort": "Stockholm",
        "land": "Sverige",
    },
    "sniKoder": ["59200"],
}

MOCK_DOCS_RESPONSE = {
    "dokument": [
        {"dokumentid": "doc1", "typ": "Arsredovisning", "period": "2023", "datum": "2024-03-01"},
        {"dokumentid": "doc2", "typ": "Arsredovisning", "period": "2022", "datum": "2023-04-10"},
    ]
}

MOCK_TOKEN_RESPONSE = {
    "access_token": "fake-token-xyz",
    "expires_in": 3600,
}


def make_mock_response(data: dict, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.ok = status < 400
    resp.json.return_value = data
    resp.text = json.dumps(data)
    return resp


class TestBolagsverketClient:
    @pytest.fixture
    def client(self):
        with patch("bolagsverket.auth.requests.post") as mock_post:
            mock_post.return_value = make_mock_response(MOCK_TOKEN_RESPONSE)
            c = BolagsverketClient("client_id", "client_secret")
            c._auth.get_token()  # прогреть кэш
        return c

    def test_get_company_basic(self, client):
        with patch.object(client._session, "get") as mock_get:
            mock_get.return_value = make_mock_response(MOCK_COMPANY_RESPONSE)
            company = client.get_company(VALID_ORGNR)

        assert company.name == "Spotify AB"
        assert company.org_number == VALID_ORGNR
        assert company.status == "Aktiv"
        assert company.is_active is True
        assert company.address.city == "Stockholm"

    def test_get_company_with_docs(self, client):
        with patch.object(client._session, "get") as mock_get:
            mock_get.side_effect = [
                make_mock_response(MOCK_COMPANY_RESPONSE),
                make_mock_response(MOCK_DOCS_RESPONSE),
            ]
            company = client.get_company(VALID_ORGNR, include_docs=True)

        assert len(company.annual_reports) == 2
        assert company.annual_reports[0].document_id == "doc1"

    def test_get_documents(self, client):
        with patch.object(client._session, "get") as mock_get:
            mock_get.return_value = make_mock_response(MOCK_DOCS_RESPONSE)
            docs = client.get_documents(VALID_ORGNR)

        assert len(docs) == 2
        assert docs[1].period == "2022"

    def test_not_found_raises(self, client):
        with patch.object(client._session, "get") as mock_get:
            mock_get.return_value = make_mock_response({}, status=404)
            with pytest.raises(NotFoundError):
                client.get_company(VALID_ORGNR)

    def test_rate_limit_raises(self, client):
        with patch.object(client._session, "get") as mock_get:
            mock_get.return_value = make_mock_response({}, status=429)
            with pytest.raises(RateLimitError):
                client.get_company(VALID_ORGNR)

    def test_is_construction_false(self, client):
        with patch.object(client._session, "get") as mock_get:
            mock_get.return_value = make_mock_response(MOCK_COMPANY_RESPONSE)
            result = client.is_construction_company(VALID_ORGNR)
        assert result is False  # SNI 59200 — не строительство

    def test_is_construction_true(self, client):
        construction_response = {**MOCK_COMPANY_RESPONSE, "sniKoder": ["41200"]}
        with patch.object(client._session, "get") as mock_get:
            mock_get.return_value = make_mock_response(construction_response)
            result = client.is_construction_company(VALID_ORGNR)
        assert result is True


# ─────────────────────────────────────────────
#  Тесты VAT / Moms
# ─────────────────────────────────────────────

from bolagsverket.vat import (
    VatInfo,
    generate_vat_number,
    generate_vat_info,
    parse_vat_number,
    is_valid_vat_format,
    format_vat_eu,
)


class TestGenerateVatNumber:
    def test_basic(self):
        assert generate_vat_number(VALID_ORGNR) == f"SE{VALID_ORGNR}01"

    def test_with_dashes(self):
        assert generate_vat_number(VALID_DASHES) == f"SE{VALID_ORGNR2}01"

    def test_prefix_se(self):
        vat = generate_vat_number(VALID_ORGNR)
        assert vat.startswith("SE")

    def test_suffix_01(self):
        vat = generate_vat_number(VALID_ORGNR)
        assert vat.endswith("01")

    def test_total_length(self):
        vat = generate_vat_number(VALID_ORGNR)
        assert len(vat) == 14  # SE + 10 digits + 01

    def test_invalid_orgnr_raises(self):
        with pytest.raises(ValidationError):
            generate_vat_number("000")


class TestGenerateVatInfo:
    def test_registered(self):
        info = generate_vat_info(VALID_ORGNR, is_registered=True)
        assert info.is_registered is True
        assert info.vat_number == f"SE{VALID_ORGNR}01"

    def test_not_registered(self):
        info = generate_vat_info(VALID_ORGNR, is_registered=False)
        assert info.is_registered is False

    def test_unknown(self):
        info = generate_vat_info(VALID_ORGNR)
        assert info.is_registered is None

    def test_eu_format_generated(self):
        info = generate_vat_info(VALID_ORGNR)
        assert info.eu_format.startswith("SE ")
        assert " " in info.eu_format

    def test_to_dict_keys(self):
        info = generate_vat_info(VALID_ORGNR, is_registered=True)
        d = info.to_dict()
        assert "vat_nummer" in d
        assert "eu_format" in d
        assert "moms_registrerad" in d
        assert d["moms_registrerad"] is True


class TestParseVatNumber:
    def test_basic(self):
        orgnr = parse_vat_number(f"SE{VALID_ORGNR}01")
        assert orgnr == VALID_ORGNR

    def test_lowercase(self):
        orgnr = parse_vat_number(f"se{VALID_ORGNR}01")
        assert orgnr == VALID_ORGNR

    def test_with_spaces(self):
        vat = f"SE {VALID_ORGNR[:3]} {VALID_ORGNR[3:6]} {VALID_ORGNR[6:]} 01"
        orgnr = parse_vat_number(vat)
        assert orgnr == VALID_ORGNR

    def test_invalid_format_raises(self):
        with pytest.raises(ValidationError):
            parse_vat_number("GB123456789")

    def test_invalid_suffix_raises(self):
        with pytest.raises(ValidationError):
            parse_vat_number(f"SE{VALID_ORGNR}02")


class TestIsValidVatFormat:
    def test_valid(self):
        assert is_valid_vat_format(f"SE{VALID_ORGNR}01") is True

    def test_invalid_country(self):
        assert is_valid_vat_format("DE123456789") is False

    def test_invalid_suffix(self):
        assert is_valid_vat_format(f"SE{VALID_ORGNR}99") is False

    def test_too_short(self):
        assert is_valid_vat_format("SE12345601") is False


class TestFormatVatEu:
    def test_from_vat(self):
        result = format_vat_eu(f"SE{VALID_ORGNR}01")
        assert result.startswith("SE ")

    def test_from_orgnr(self):
        result = format_vat_eu(VALID_ORGNR)
        assert result.startswith("SE ")

    def test_groups_of_three(self):
        result = format_vat_eu(VALID_ORGNR)
        parts = result.split(" ")
        assert parts[0] == "SE"
        # остальные части по 3 символа (кроме возможно последней)
        for part in parts[1:]:
            assert len(part) <= 3


class TestCompanyVatProperties:
    def _company(self, is_vat=None) -> Company:
        return Company(
            org_number=VALID_ORGNR,
            name="Test AB",
            status="Aktiv",
            is_vat_registered=is_vat,
        )

    def test_vat_number_when_registered(self):
        c = self._company(is_vat=True)
        assert c.vat_number == f"SE{VALID_ORGNR}01"

    def test_vat_number_when_not_registered(self):
        c = self._company(is_vat=False)
        assert c.vat_number is None

    def test_vat_number_when_unknown(self):
        c = self._company(is_vat=None)
        # Возвращает потенциальный номер даже если статус неизвестен
        assert c.vat_number == f"SE{VALID_ORGNR}01"

    def test_eu_format_not_none_when_registered(self):
        c = self._company(is_vat=True)
        assert c.vat_number_eu_format is not None
        assert c.vat_number_eu_format.startswith("SE ")

    def test_eu_format_none_when_not_registered(self):
        c = self._company(is_vat=False)
        assert c.vat_number_eu_format is None

    def test_to_dict_contains_moms(self):
        c = self._company(is_vat=True)
        d = c.to_dict(include_raw=False)
        assert "moms" in d
        assert d["moms"]["moms_registrerad"] is True
        assert d["moms"]["vat_nummer"] == f"SE{VALID_ORGNR}01"
        assert d["moms"]["notering"] == "Registrerad"

    def test_to_dict_moms_ej_registrerad(self):
        c = self._company(is_vat=False)
        d = c.to_dict(include_raw=False)
        assert d["moms"]["notering"] == "Ej registrerad"
        assert d["moms"]["vat_nummer"] is None


# ─────────────────────────────────────────────
#  Тесты MackAnClient
# ─────────────────────────────────────────────

from unittest.mock import patch as mock_patch
from bolagsverket.mackan import MackAnClient
from bolagsverket.factory import get_client

# Пример ответа mackan.eu (поля в стиле mackan)
MACKAN_RESPONSE = {
    "company_name": "Bygg Stockholm AB",
    "org_number": VALID_ORGNR,
    "status": "Aktiv",
    "legal_form": "Aktiebolag",
    "registration_date": "2012-03-10",
    "business_description": "Byggnadsverksamhet i Stockholm",
    "address": {
        "street": "Byggatan 5",
        "postal_code": "123 45",
        "city": "Stockholm",
        "country": "Sverige",
    },
    "sni_codes": ["41200", "43120"],
    "vat_registered": True,
    "annual_reports": [
        {"document_id": "m001", "type": "Arsredovisning", "period": "2023", "date": "2024-03-01"},
    ],
}

# Пример ответа mackan.eu в стиле bolagsverket (альтернативные ключи)
MACKAN_BV_STYLE = {
    "namn": "IKEA AB",
    "organisationsnummer": VALID_ORGNR2,
    "status": "Aktiv",
    "organisationsform": "Aktiebolag",
    "registreringsdatum": "1999-01-01",
    "verksamhetsbeskrivning": "Möbelhandel",
    "adress": {
        "gatuadress": "IKEA-vägen 1",
        "postnummer": "343 81",
        "postort": "Älmhult",
        "land": "Sverige",
    },
    "sniKoder": ["47590"],
}


def make_mackan_mock(data: dict, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.ok = status < 400
    resp.json.return_value = data
    resp.text = json.dumps(data)
    return resp


class TestMackAnClient:
    @pytest.fixture
    def client(self):
        return MackAnClient()

    def test_source_name(self, client):
        assert "mackan" in client.source_name.lower()

    def test_get_company_mackan_fields(self, client):
        with mock_patch.object(client._session, "get") as m:
            m.return_value = make_mackan_mock(MACKAN_RESPONSE)
            company = client.get_company(VALID_ORGNR)

        assert company.name == "Bygg Stockholm AB"
        assert company.status == "Aktiv"
        assert company.legal_form == "Aktiebolag"
        assert company.address.city == "Stockholm"
        assert company.address.street == "Byggatan 5"

    def test_get_company_bv_style_fields(self, client):
        """mackan.eu может вернуть поля и в стиле bolagsverket."""
        with mock_patch.object(client._session, "get") as m:
            m.return_value = make_mackan_mock(MACKAN_BV_STYLE)
            company = client.get_company(VALID_ORGNR2)

        assert company.name == "IKEA AB"
        assert company.address.city == "Älmhult"

    def test_sni_codes_parsed(self, client):
        with mock_patch.object(client._session, "get") as m:
            m.return_value = make_mackan_mock(MACKAN_RESPONSE)
            company = client.get_company(VALID_ORGNR)

        assert len(company.sni_codes) == 2
        codes = [s.code for s in company.sni_codes]
        assert "41200" in codes
        assert "43120" in codes

    def test_is_construction_true(self, client):
        with mock_patch.object(client._session, "get") as m:
            m.return_value = make_mackan_mock(MACKAN_RESPONSE)
            company = client.get_company(VALID_ORGNR)

        assert company.is_construction is True

    def test_vat_registered(self, client):
        with mock_patch.object(client._session, "get") as m:
            m.return_value = make_mackan_mock(MACKAN_RESPONSE)
            company = client.get_company(VALID_ORGNR)

        assert company.is_vat_registered is True
        assert company.vat_number == f"SE{VALID_ORGNR}01"

    def test_include_docs(self, client):
        with mock_patch.object(client._session, "get") as m:
            m.return_value = make_mackan_mock(MACKAN_RESPONSE)
            company = client.get_company(VALID_ORGNR, include_docs=True)

        assert len(company.annual_reports) == 1
        assert company.annual_reports[0].document_id == "m001"

    def test_get_documents(self, client):
        with mock_patch.object(client._session, "get") as m:
            m.return_value = make_mackan_mock(MACKAN_RESPONSE)
            docs = client.get_documents(VALID_ORGNR)

        assert len(docs) == 1

    def test_not_found_raises(self, client):
        with mock_patch.object(client._session, "get") as m:
            m.return_value = make_mackan_mock({"error": "Not found"})
            with pytest.raises(NotFoundError):
                client.get_company(VALID_ORGNR)

    def test_http_404_raises(self, client):
        with mock_patch.object(client._session, "get") as m:
            m.return_value = make_mackan_mock({}, status=404)
            with pytest.raises(NotFoundError):
                client.get_company(VALID_ORGNR)

    def test_source_stored_in_raw(self, client):
        with mock_patch.object(client._session, "get") as m:
            m.return_value = make_mackan_mock(MACKAN_RESPONSE)
            company = client.get_company(VALID_ORGNR)

        assert "_source" in company.raw
        assert "mackan" in company.raw["_source"].lower()


# ─────────────────────────────────────────────
#  Тесты factory / get_client()
# ─────────────────────────────────────────────

class TestGetClient:
    def test_mackan_explicit(self):
        client = get_client(source="mackan")
        assert isinstance(client, MackAnClient)

    def test_bolagsverket_with_keys(self):
        from bolagsverket import BolagsverketClient
        client = get_client(
            source="bolagsverket",
            client_id="test_id",
            client_secret="test_secret",
        )
        assert isinstance(client, BolagsverketClient)

    def test_bolagsverket_missing_keys_raises(self):
        with pytest.raises(ValueError, match="client_id"):
            get_client(source="bolagsverket")

    def test_auto_no_env_returns_mackan(self):
        """Без ключей auto → MackAnClient."""
        with mock_patch.dict("os.environ", {}, clear=True):
            # Убираем env-переменные если они есть
            import os
            env = {k: v for k, v in os.environ.items()
                   if k not in ("BV_CLIENT_ID", "BV_CLIENT_SECRET")}
            with mock_patch.dict("os.environ", env, clear=True):
                client = get_client(source="auto")
        assert isinstance(client, MackAnClient)

    def test_auto_with_keys_returns_bolagsverket(self):
        """С ключами auto → BolagsverketClient."""
        from bolagsverket import BolagsverketClient
        client = get_client(
            source="auto",
            client_id="abc",
            client_secret="xyz",
        )
        assert isinstance(client, BolagsverketClient)

    def test_timeout_passed(self):
        client = get_client(source="mackan", timeout=30)
        assert client._timeout == 30

    def test_validate_orgnr_passed(self):
        client = get_client(source="mackan", validate_orgnr=False)
        assert client._validate is False
