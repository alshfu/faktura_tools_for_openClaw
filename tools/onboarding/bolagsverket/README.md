# bolagsverket-py

Python-библиотека для работы с **Bolagsverket API** (Värdefulla datamängder).  
Получение данных о шведских компаниях по organisationsnummer, генерация VAT-номеров.

## Установка

```bash
pip install requests
pip install -e .
```

## Быстрый старт

```python
from bolagsverket import BolagsverketClient

client = BolagsverketClient("CLIENT_ID", "CLIENT_SECRET")
company = client.get_company("5560000001")

print(company.name)                 # "Bygg AB"
print(company.vat_number)           # "SE556000000101"
print(company.vat_number_eu_format) # "SE 556 000 000 101"
print(company.is_construction)      # True / False
print(company.age_years)            # 14.2
```

## Подробная документация

См. файл **LIBRARY.md**.

## Структура

```
bolagsverket/
├── __init__.py      — публичный API
├── __main__.py      — python -m bolagsverket
├── client.py        — BolagsverketClient
├── auth.py          — OAuth2 TokenManager
├── models.py        — Company, Address, SniCode, AnnualReport
├── vat.py           — VAT / momsregistreringsnummer
├── validators.py    — validate(), is_valid()
├── exceptions.py    — иерархия исключений
└── cli.py           — CLI-интерфейс
tests/
└── test_library.py  — 63 теста
```

## CLI

```bash
export BV_CLIENT_ID="..."
export BV_CLIENT_SECRET="..."

bolagsverket-cli 5560000001 --pretty --docs
python -m bolagsverket 5560000001 --pretty
```

## Требования

- Python 3.10+
- requests >= 2.28
