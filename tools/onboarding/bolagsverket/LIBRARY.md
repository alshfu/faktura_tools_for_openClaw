# bolagsverket-py — Документация библиотеки

Python-библиотека для работы с **Bolagsverket API** (Värdefulla datamängder).  
Получение данных о шведских компаниях по organisationsnummer, генерация VAT-номеров.

---

## Содержание

- [Установка](#установка)
- [Быстрый старт](#быстрый-старт)
- [Архитектура](#архитектура)
- [Модуль client — BolagsverketClient](#модуль-client--bolagsverketclient)
- [Модуль models — датаклассы](#модуль-models--датаклассы)
- [Модуль vat — VAT-номера и момс](#модуль-vat--vat-номера-и-момс)
- [Модуль validators — валидация org.nr](#модуль-validators--валидация-orgnr)
- [Модуль auth — управление токенами](#модуль-auth--управление-токенами)
- [Модуль exceptions — исключения](#модуль-exceptions--исключения)
- [CLI-интерфейс](#cli-интерфейс)
- [JSON-структура ответа](#json-структура-ответа)
- [SNI-коды строительной отрасли](#sni-коды-строительной-отрасли)
- [Тестирование](#тестирование)
- [Лимиты API](#лимиты-api)

---

## Установка

```bash
pip install requests        # единственная зависимость

# Установка библиотеки (локально из папки)
pip install -e .
```

**Требования:** Python 3.10+

---

## Быстрый старт

```python
from bolagsverket import BolagsverketClient

client = BolagsverketClient("YOUR_CLIENT_ID", "YOUR_CLIENT_SECRET")

# Базовый запрос
company = client.get_company("5560000001")
print(company.name)               # → "Bygg AB"
print(company.status)             # → "Aktiv"
print(company.age_years)          # → 14.2
print(company.is_construction)    # → False
print(company.vat_number)         # → "SE556000000101"
print(company.vat_number_eu_format) # → "SE 556 000 000 101"

# Запрос с годовыми отчётами
company = client.get_company("5560000001", include_docs=True)
for doc in company.annual_reports:
    print(doc.period, doc.document_id)

# Полный JSON
import json
print(json.dumps(company.to_dict(), ensure_ascii=False, indent=2))
```

---

## Архитектура

```
bolagsverket/
├── __init__.py      — публичный API (все экспорты)
├── __main__.py      — точка входа: python -m bolagsverket
├── client.py        — BolagsverketClient
├── auth.py          — TokenManager (OAuth2 + кэш)
├── models.py        — Company, Address, SniCode, AnnualReport
├── vat.py           — VatInfo, generate_vat_number() и др.
├── validators.py    — validate(), is_valid(), legal_form_hint()
├── exceptions.py    — иерархия исключений
└── cli.py           — CLI-обёртка
```

---

## Модуль client — BolagsverketClient

Главный класс библиотеки. Управляет HTTP-сессией, OAuth2-токеном, парсингом и валидацией.

### Конструктор

```python
BolagsverketClient(
    client_id:      str,
    client_secret:  str,
    timeout:        int  = 15,
    validate_orgnr: bool = True,
)
```

| Параметр | Тип | По умолч. | Описание |
|---|---|---|---|
| `client_id` | str | — | OAuth2 client_id от Bolagsverket |
| `client_secret` | str | — | OAuth2 client_secret |
| `timeout` | int | 15 | Таймаут HTTP-запросов в секундах |
| `validate_orgnr` | bool | True | Проверять org.nr по алгоритму Luhn перед запросом |

```python
# Пример
client = BolagsverketClient(
    client_id="abc123",
    client_secret="xyz789",
    timeout=30,
    validate_orgnr=True,
)
```

---

### get_company()

```python
client.get_company(orgnr: str, include_docs: bool = False) -> Company
```

Возвращает полную информацию о компании.

| Параметр | Тип | Описание |
|---|---|---|
| `orgnr` | str | Organisationsnummer (10 цифр, дефисы допустимы) |
| `include_docs` | bool | Если True — дополнительно запрашивает список годовых отчётов |

**Возвращает:** объект `Company`

**Исключения:**

| Исключение | Когда |
|---|---|
| `ValidationError` | Некорректный org.nr (неверный формат или контрольная цифра) |
| `NotFoundError` | Компания не найдена (HTTP 404) |
| `AuthError` | Ошибка аутентификации (HTTP 401) |
| `RateLimitError` | Превышен лимит запросов (HTTP 429) |
| `ApiError` | Прочие ошибки API |

```python
# Без отчётов
company = client.get_company("5560000001")

# С отчётами
company = client.get_company("5560000001", include_docs=True)

# Дефисы в org.nr — допустимы
company = client.get_company("556-000-0001")

# Обработка ошибок
from bolagsverket import NotFoundError, RateLimitError
try:
    company = client.get_company("5560000001")
except NotFoundError:
    print("Компания не найдена")
except RateLimitError:
    import time
    time.sleep(60)
```

---

### get_documents()

```python
client.get_documents(orgnr: str) -> list[AnnualReport]
```

Возвращает только список годовых отчётов без основных данных компании.

```python
docs = client.get_documents("5560000001")
for doc in docs:
    print(f"{doc.period}  →  {doc.document_id}")
```

---

### download_document()

```python
client.download_document(document_id: str) -> bytes
```

Скачивает годовой отчёт как ZIP-архив (формат iXBRL).  
`document_id` берётся из `AnnualReport.document_id`.

```python
docs = client.get_documents("5560000001")
if docs:
    data = client.download_document(docs[0].document_id)
    with open("arsredovisning.zip", "wb") as f:
        f.write(data)
```

---

### is_construction_company()

```python
client.is_construction_company(orgnr: str) -> bool
```

Быстрая проверка: относится ли компания к строительной отрасли (SNI 41–43).

```python
if client.is_construction_company("5560000001"):
    print("Строительная компания")
```

---

## Модуль models — датаклассы

### Company

Главная модель. Возвращается методами `get_company()`.

#### Поля (из API)

| Поле | Тип | Описание |
|---|---|---|
| `org_number` | str | Organisationsnummer (10 цифр) |
| `name` | str \| None | Официальное название |
| `legal_form` | str \| None | Правовая форма (Aktiebolag, HB и т.д.) |
| `status` | str \| None | Статус (Aktiv, Avregistrerad, Konkurs...) |
| `registration_date` | str \| None | Дата регистрации YYYY-MM-DD |
| `business_description` | str \| None | Описание деятельности |
| `address` | Address | Зарегистрированный адрес |
| `sni_codes` | list[SniCode] | Отраслевые коды |
| `annual_reports` | list[AnnualReport] | Годовые отчёты (если запрошены) |
| `is_vat_registered` | bool \| None | Зарегистрирован ли плательщиком момс |
| `raw` | dict | Необработанный ответ API |

#### Вычисляемые свойства

| Свойство | Тип | Описание |
|---|---|---|
| `age_years` | float \| None | Возраст компании в годах |
| `is_active` | bool | True если status == "Aktiv" |
| `is_construction` | bool | True если есть SNI-код 41–43 |
| `construction_codes` | list[SniCode] | Только строительные SNI-коды |
| `vat_number` | str \| None | Momsregistreringsnummer SE{orgnr}01 |
| `vat_number_eu_format` | str \| None | VAT с пробелами: "SE 556 000 000 101" |

```python
company = client.get_company("5560000001")

print(company.age_years)             # → 12.5
print(company.is_active)             # → True
print(company.is_construction)       # → True / False
print(company.vat_number)            # → "SE556000000101"
print(company.vat_number_eu_format)  # → "SE 556 000 000 101"
```

#### Методы

**`to_dict(include_raw: bool = True) -> dict`**

Сериализация в словарь. Передайте `include_raw=False` чтобы исключить сырой ответ API.

```python
d = company.to_dict(include_raw=False)
import json
print(json.dumps(d, ensure_ascii=False, indent=2))
```

---

### Address

```python
@dataclass
class Address:
    street:      Optional[str]  # gatuadress
    postal_code: Optional[str]  # postnummer
    city:        Optional[str]  # postort
    country:     Optional[str]  # land
```

```python
addr = company.address
print(addr.street)       # → "Regeringsgatan 19"
print(addr.postal_code)  # → "111 53"
print(addr.city)         # → "Stockholm"
print(str(addr))         # → "Regeringsgatan 19, 111 53, Stockholm"
```

---

### SniCode

```python
@dataclass
class SniCode:
    code:   str   # пятизначный код, напр. "41200"
    sector: str   # расшифровка, напр. "Строительство зданий"
```

| Метод | Описание |
|---|---|
| `is_construction() -> bool` | True если код начинается с 41, 42 или 43 |
| `__str__()` | "41200 — Строительство зданий" |

```python
for sni in company.sni_codes:
    print(sni.code, sni.sector, sni.is_construction())
```

---

### AnnualReport

```python
@dataclass
class AnnualReport:
    document_id:    str           # ID для скачивания
    doc_type:       Optional[str] # "Arsredovisning"
    period:         Optional[str] # "2023-01-01/2023-12-31"
    submitted_date: Optional[str] # "2024-04-10"
```

```python
company = client.get_company("5560000001", include_docs=True)
for r in company.annual_reports:
    print(r.period, "→", r.document_id)
    data = client.download_document(r.document_id)
```

---

## Модуль vat — VAT-номера и момс

Шведский momsregistreringsnummer строится по правилу:

```
SE  +  {10-значный organisationsnummer}  +  01
SE      5560000001                         01
─────────────────────────────────────────────
        SE556000000101
```

Суффикс `01` — стандартный для всех юридических лиц Швеции.

---

### generate_vat_number()

```python
generate_vat_number(orgnr: str) -> str
```

Генерирует VAT-номер из organisationsnummer.

```python
from bolagsverket import generate_vat_number

vat = generate_vat_number("5560000001")
print(vat)  # → "SE556000000101"

# С дефисами — тоже работает
vat = generate_vat_number("556-000-0001")
print(vat)  # → "SE556000000101"
```

**Raises:** `ValidationError` если org.nr некорректен.

---

### generate_vat_info()

```python
generate_vat_info(
    orgnr: str,
    is_registered: Optional[bool] = None,
) -> VatInfo
```

Создаёт полный объект `VatInfo` с метаданными.

| Параметр | Описание |
|---|---|
| `orgnr` | Organisationsnummer |
| `is_registered` | True = зарег. / False = не зарег. / None = неизвестно |

```python
from bolagsverket import generate_vat_info

info = generate_vat_info("5560000001", is_registered=True)
print(info.vat_number)      # → "SE556000000101"
print(info.eu_format)       # → "SE 556 000 000 101"
print(info.is_registered)   # → True
print(info.to_dict())
# {
#   "organisationsnummer": "5560000001",
#   "vat_nummer":          "SE556000000101",
#   "eu_format":           "SE 556 000 000 101",
#   "moms_registrerad":    True,
#   "suffix":              "01",
#   "skatteverket_url":    "https://..."
# }
```

---

### parse_vat_number()

```python
parse_vat_number(vat: str) -> str
```

Извлекает organisationsnummer из VAT-номера. Принимает форматы с пробелами и нижний регистр.

```python
from bolagsverket import parse_vat_number

orgnr = parse_vat_number("SE556000000101")
print(orgnr)  # → "5560000001"

orgnr = parse_vat_number("se 556 000 000 101")
print(orgnr)  # → "5560000001"
```

**Raises:** `ValidationError` если формат неверен.

---

### is_valid_vat_format()

```python
is_valid_vat_format(vat: str) -> bool
```

Проверяет формат VAT-номера (без исключений).

```python
from bolagsverket import is_valid_vat_format

is_valid_vat_format("SE556000000101")  # → True
is_valid_vat_format("GB123456789")     # → False
is_valid_vat_format("SE12345601")      # → False (слишком короткий)
```

---

### format_vat_eu()

```python
format_vat_eu(vat_or_orgnr: str) -> str
```

Форматирует VAT-номер или org.nr в читаемый EU-формат с пробелами.

```python
from bolagsverket import format_vat_eu

# Из VAT-номера
print(format_vat_eu("SE556000000101"))  # → "SE 556 000 000 101"

# Из org.nr
print(format_vat_eu("5560000001"))      # → "SE 556 000 000 101"
```

---

### VatInfo (датакласс)

```python
@dataclass
class VatInfo:
    org_number:       str            # organisationsnummer
    vat_number:       str            # SE{orgnr}01
    is_registered:    Optional[bool] # статус момс
    suffix:           str            # "01"
    eu_format:        str            # "SE 556 000 000 101"
    skatteverket_url: str            # ссылка на Skatteverket
```

**Методы:**

| Метод | Описание |
|---|---|
| `to_dict() -> dict` | Сериализация в словарь |

---

### Важное замечание о статусе момс

Bolagsverket **бесплатный API** не всегда возвращает явный признак регистрации в качестве плательщика момс. Библиотека пытается определить статус из следующих полей ответа:

| Поле в API | Тип | Приоритет |
|---|---|---|
| `registreradForMoms` | bool | Высший |
| `momsRegistrerad` | bool | Высший |
| `vatRegistered` | bool | Высший |
| `momsStatus` | string | Средний |

Если ни одно поле не найдено — `is_vat_registered = None`, и VAT-номер возвращается как **потенциальный** (не подтверждённый). Для гарантированной проверки используйте:

- **Skatteverket:** `https://www.skatteverket.se/`
- **EU VIES:** `https://ec.europa.eu/taxation_customs/vies/`

---

## Модуль validators — валидация org.nr

### validate()

```python
validate(orgnr: str) -> str
```

Нормализует и проверяет organisationsnummer. Выполняет три проверки:
1. Нормализацию (убирает дефисы/пробелы)
2. Формат (ровно 10 цифр)
3. Контрольную цифру по алгоритму Luhn

**Возвращает:** нормализованный номер (10 цифр)  
**Raises:** `ValidationError`

```python
from bolagsverket import validate

clean = validate("556-000-0001")   # → "5560000001"
clean = validate("5560000001")     # → "5560000001"
validate("123456789")              # → ValidationError (9 цифр)
validate("5560000000")             # → ValidationError (неверная контрольная цифра)
```

---

### normalize()

```python
normalize(orgnr: str) -> str
```

Только убирает дефисы и пробелы, без валидации.

```python
from bolagsverket import normalize

normalize("556-000-0001")  # → "5560000001"
normalize("556 000 0001")  # → "5560000001"
```

---

### is_valid()

```python
is_valid(orgnr: str) -> bool
```

Проверяет org.nr без выброса исключения.

```python
from bolagsverket import is_valid

is_valid("5560000001")  # → True
is_valid("1234567890")  # → False
```

---

### legal_form_hint()

```python
legal_form_hint(orgnr: str) -> str
```

Возвращает вероятную правовую форму по первой цифре organisationsnummer.

```python
from bolagsverket import legal_form_hint

legal_form_hint("5560000001")   # → "Aktiebolag (AB)"
legal_form_hint("9123456789")   # → "Handelsbolag / Kommanditbolag"
```

| Первая цифра | Правовая форма |
|---|---|
| 1 | Dödsbo |
| 2 | Государство / муниципалитет |
| 3 | Иностранная компания |
| 5 | Aktiebolag (AB) |
| 6 | Enskild firma (ИП) |
| 7 | Ekonomisk förening / Brf |
| 8 | Ideell förening / Stiftelse |
| 9 | Handelsbolag / Kommanditbolag |

---

## Модуль auth — управление токенами

### TokenManager

Управляет OAuth2-токеном. Используется внутри `BolagsverketClient`, но доступен напрямую.

```python
from bolagsverket.auth import TokenManager

manager = TokenManager("client_id", "client_secret")
token = manager.get_token()     # автоматически кэшируется
manager.invalidate()            # сброс кэша
```

**Логика кэширования:**
- Токен живёт 3 600 секунд (1 час)
- Обновляется автоматически за 60 секунд до истечения
- `get_token()` всегда возвращает действующий токен

---

## Модуль exceptions — исключения

Иерархия исключений библиотеки:

```
BolagsverketError          ← базовое исключение
├── AuthError              ← HTTP 401, неверные ключи
├── NotFoundError          ← HTTP 404, компания не найдена
│     .orgnr               ← org.nr из запроса
├── RateLimitError         ← HTTP 429, лимит запросов
├── ApiError               ← прочие HTTP-ошибки
│     .status_code         ← HTTP-код
│     .body                ← тело ответа
└── ValidationError        ← неверный формат org.nr или VAT
```

```python
from bolagsverket import (
    BolagsverketError,
    AuthError,
    NotFoundError,
    RateLimitError,
    ApiError,
    ValidationError,
)

try:
    company = client.get_company("5560000001")
except NotFoundError as e:
    print(f"Не найдено: {e.orgnr}")
except RateLimitError:
    time.sleep(60)
except AuthError:
    print("Проверьте client_id и client_secret")
except ApiError as e:
    print(f"HTTP {e.status_code}: {e.body}")
except BolagsverketError as e:
    print(f"Общая ошибка: {e}")
```

---

## CLI-интерфейс

После `pip install -e .` доступна команда `bolagsverket-cli`:

```bash
# Базовый запрос
bolagsverket-cli 5560000001

# С форматированием и годовыми отчётами
bolagsverket-cli 5560000001 --pretty --docs

# Без сырого ответа API
bolagsverket-cli 5560000001 --pretty --no-raw

# Сохранить в файл
bolagsverket-cli 5560000001 --out company.json

# Только валидация org.nr (без API-запроса)
bolagsverket-cli --validate 5560000001

# Передать ключи напрямую
bolagsverket-cli 5560000001 --client-id abc --client-secret xyz
```

Через переменные окружения:

```bash
export BV_CLIENT_ID="your_client_id"
export BV_CLIENT_SECRET="your_client_secret"
bolagsverket-cli 5560000001 --pretty
```

Или как Python-модуль:

```bash
python -m bolagsverket 5560000001 --pretty
```

---

## JSON-структура ответа

Метод `company.to_dict()` возвращает:

```json
{
  "meta": {
    "fetched_at": "2026-05-11T14:32:01",
    "source": "Bolagsverket Värdefulla datamängder API v1"
  },
  "grunduppgifter": {
    "organisationsnummer": "5560000001",
    "namn": "Bygg AB",
    "organisationsform": "Aktiebolag",
    "status": "Aktiv",
    "registreringsdatum": "2010-03-15",
    "alder_ar": 16.1,
    "verksamhetsbeskrivning": "Byggnadsverksamhet"
  },
  "adress": {
    "gatuadress": "Storgatan 1",
    "postnummer": "111 22",
    "postort": "Stockholm",
    "land": "Sverige"
  },
  "sni": {
    "koder": [
      { "kod": "41200", "sektor": "Строительство зданий" }
    ],
    "ar_byggforetag": true,
    "byggkoder": ["41200"]
  },
  "moms": {
    "moms_registrerad": true,
    "vat_nummer": "SE556000000101",
    "eu_format": "SE 556 000 000 101",
    "notering": "Registrerad"
  },
  "arsredovisningar": {
    "antal": 3,
    "dokument": [
      {
        "dokumentid": "abc123",
        "typ": "Arsredovisning",
        "period": "2023-01-01/2023-12-31",
        "datum": "2024-04-10"
      }
    ]
  },
  "raw_api_response": { "...": "..." }
}
```

---

## SNI-коды строительной отрасли

Библиотека автоматически определяет строительные компании по группам 41–43:

| Группа | Коды | Деятельность |
|---|---|---|
| **41** | 41100, 41200 | Девелопмент, строительство зданий |
| **42** | 42110–42990 | Дороги, мосты, коммуникации |
| **43** | 43110–43999 | Снос, электрика, сантехника, кровля, отделка |

```python
company = client.get_company("5560000001")

# Является ли строительной?
print(company.is_construction)        # True / False

# Какие именно строительные коды?
for code in company.construction_codes:
    print(code.code, code.sector)
```

---

## Тестирование

```bash
# Установить pytest
pip install pytest

# Запустить все тесты
pytest tests/ -v

# Запустить конкретный класс тестов
pytest tests/ -v -k "TestVat"

# С покрытием кода
pip install pytest-cov
pytest tests/ --cov=bolagsverket --cov-report=term-missing
```

Тесты покрывают:
- `TestNormalize` — нормализация org.nr
- `TestValidate` — проверка формата и алгоритма Luhn
- `TestIsValid`, `TestLegalFormHint`
- `TestSniCode`, `TestCompany` — модели и вычисляемые свойства
- `TestBolagsverketClient` — HTTP-клиент через моки
- `TestGenerateVatNumber`, `TestGenerateVatInfo` — генерация VAT
- `TestParseVatNumber` — парсинг VAT
- `TestIsValidVatFormat`, `TestFormatVatEu` — форматирование
- `TestCompanyVatProperties` — VAT-свойства в модели Company

---

## Лимиты API

| Параметр | Значение |
|---|---|
| Запросов в минуту | **60** |
| Один запрос = | 1 org.nr |
| Пакетных запросов | ❌ нет |
| Время жизни токена | 3 600 сек (1 час) |
| Кэширование токена | ✅ автоматически |
| Документы (iXBRL) | с 2020 года |

При превышении лимита выбрасывается `RateLimitError`. Для массовой обработки:

```python
import time
from bolagsverket import RateLimitError

orgnr_list = ["5560000001", "5560000002", "5560000003"]

for orgnr in orgnr_list:
    try:
        company = client.get_company(orgnr)
        print(company.name, company.vat_number)
    except RateLimitError:
        time.sleep(60)
        company = client.get_company(orgnr)  # повтор
    time.sleep(1)  # пауза между запросами
```
