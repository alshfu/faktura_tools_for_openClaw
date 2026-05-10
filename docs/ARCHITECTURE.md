# Billing System — Архитектура v2

> Полная переработка проекта. LLM используется только для конверсации.
> Вся бизнес-логика, шаблоны, валидация и сообщения — в Python-скриптах.

---

## 1. Принципы

1. **LLM минимально** — модель только понимает что хочет пользователь и вызывает скрипт. Все тексты, сводки, сообщения, ответы — генерируются скриптами из шаблонов.

2. **Скрипты автономны** — каждый скрипт делает одну вещь, возвращает JSON, может вызываться из CLI или из другого скрипта.

3. **Шаблоны вместо генерации** — все сообщения к пользователю лежат в `templates/messages/*.txt` с переменными `{namn}`, `{org_nummer}` и т.д.

4. **База данных нормализованная** — отправители, получатели, фактуры — раздельные сущности с ID и связями. Никаких дублирующихся данных.

5. **Phone → Sender mapping** — номер телефона определяет от чьего имени работаем.

6. **Версионирование данных** — у каждой записи `skapad_datum`, `uppdaterad_datum`, `version`.

---

## 2. Структура проекта

```
/home/administrator/billing-system/
│
├── tools/                                 # Все Python-скрипты
│   ├── db/                                # CRUD для БД
│   │   ├── db_senders.py                  # Управление отправителями
│   │   ├── db_recipients.py               # Управление получателями
│   │   ├── db_invoices.py                 # CRUD + кредитование фактур
│   │   ├── db_templates.py                # Управление дизайн-шаблонами
│   │   └── db_phone_map.py                # Маппинг номера → отправитель
│   │
│   ├── workflow/                          # Основные операции
│   │   ├── summarize.py                   # Генерация сводки фактуры
│   │   ├── create_invoice.py              # Создание фактуры + PDF
│   │   ├── send_invoice.py                # Отправка PDF в WhatsApp
│   │   ├── credit_invoice.py              # Создание кредит-ноты
│   │   └── delete_invoice.py              # Soft-delete фактуры
│   │
│   ├── onboarding/                        # Регистрация новых субъектов
│   │   ├── onboard_sender.py              # Пошаговая регистрация отправителя
│   │   ├── onboard_recipient.py           # Пошаговая регистрация получателя
│   │   ├── identify_sender.py             # Определение отправителя по номеру
│   │   └── show_templates.py              # Показать 5 дизайн-шаблонов
│   │
│   ├── messaging/                         # Отправка сообщений в WhatsApp
│   │   ├── send_template.py               # Отправка шаблонного сообщения
│   │   └── send_pdf.py                    # Отправка PDF
│   │
│   └── utils/                             # Утилиты
│       ├── faktura_mapper.py              # Маппер JSON: наш → Faktura Constructor
│       ├── ocr.py                         # Luhn check digit
│       ├── vat.py                         # Генерация VAT-номера
│       └── validator.py                   # Валидация org_nummer, email, etc.
│
├── data/                                  # Базы данных (JSON)
│   ├── senders.json                       # Отправители
│   ├── recipients.json                    # Получатели
│   ├── invoices.json                      # Все фактуры (включая черновики и удалённые)
│   ├── phone_map.json                     # Номер → отправитель
│   └── counters.json                      # Счётчики фактур per-sender
│
├── templates/
│   ├── messages/                          # Шаблоны WhatsApp-сообщений
│   │   ├── sender/
│   │   │   ├── welcome.txt
│   │   │   ├── ask_orgnr.txt
│   │   │   ├── ask_name.txt
│   │   │   ├── ask_address.txt
│   │   │   ├── ask_bank.txt
│   │   │   ├── ask_template.txt
│   │   │   └── confirm.txt
│   │   ├── recipient/
│   │   │   ├── ask_orgnr.txt
│   │   │   ├── ask_email.txt
│   │   │   └── ask_address.txt
│   │   ├── invoice/
│   │   │   ├── summary.txt
│   │   │   ├── created.txt
│   │   │   ├── credited.txt
│   │   │   ├── deleted.txt
│   │   │   └── error.txt
│   │   └── common/
│   │       ├── greeting.txt
│   │       ├── confirmation.txt
│   │       └── access_denied.txt
│   │
│   └── design/                            # Дизайн-шаблоны для PDF
│       └── presets.json                   # 5 готовых шаблонов
│
├── docs/
│   ├── ARCHITECTURE.md                    # Этот файл
│   ├── DATABASE_SCHEMA.md                 # Полная схема БД
│   ├── API_CONTRACT.md                    # Контракты CLI-скриптов
│   └── AGENT_PROTOCOL.md                  # Как агент должен работать
│
└── README.md                              # Главный файл
```

---

## 3. Схема базы данных

### 3.1 `senders.json` — Отправители

```json
{
  "version": 2,
  "uppdaterad": "2026-05-10T12:00:00Z",
  "avsandare": {
    "559203-2279": {
      "id": "559203-2279",
      "version": 1,
      "skapad_datum": "2026-05-01T10:00:00Z",
      "uppdaterad_datum": "2026-05-10T12:00:00Z",
      "aktiv": true,

      "foretag": {
        "namn": "Jowhar AB",
        "org_nummer": "559203-2279",
        "moms_nummer": "SE559203227901",
        "f_skatt": true,
        "tagline": "Bygg & Renovering"
      },

      "adress": {
        "gata": "AEK 598F BILLO",
        "postnummer": "106 46",
        "stad": "Stockholm",
        "land": "SE"
      },

      "kontakt": {
        "epost": "info@jowhar.se",
        "telefon": "+46 8 555 01 24",
        "webb": "www.jowhar.se"
      },

      "bank": {
        "bankgiro": "555-6666",
        "plusgiro": "",
        "iban": "SE00 1234 5678 9012 3456 7890",
        "bic": "HANDSESS",
        "bank_namn": "Handelsbanken",
        "valuta": "SEK"
      },

      "fakturan_nu": {
        "aktiverad": true,
        "api_nyckel": "YvtuE3qKRdHnrrvt0z6x",
        "api_losenord": "w1BR6iGixoJzS_mHPxGUa1a6bI2fCGC7bC1kBEYt",
        "miljo_default": "sandbox"
      },

      "design": {
        "shablon_id": "klassisk_svart",
        "anpassningar": {}
      },

      "fakturering": {
        "betalningsvillkor_dagar_default": 30,
        "moms_procent_default": 25,
        "nasta_faktura_nummer": 893,
        "faktura_villkor_text": "Vid försenad betalning debiteras dröjsmålsränta enligt räntelagen."
      },

      "telefon_kopplingar": [
        "+46735272989"
      ]
    }
  }
}
```

### 3.2 `recipients.json` — Получатели

```json
{
  "version": 2,
  "uppdaterad": "2026-05-10T12:00:00Z",
  "mottagare": {
    "559021-3863": {
      "id": "559021-3863",
      "version": 1,
      "skapad_datum": "2026-05-01T10:00:00Z",
      "uppdaterad_datum": "2026-05-10T12:00:00Z",
      "aktiv": true,

      "foretag": {
        "namn": "Davids Måleri i Bollnäs AB",
        "org_nummer": "559021-3863",
        "kontaktperson": "David Andersson"
      },

      "adress": {
        "gata": "RULLSTENSVÄGEN 89 LGH 1101",
        "postnummer": "146 34",
        "stad": "Tullinge",
        "land": "SE"
      },

      "kontakt": {
        "epost": "alshfu@gmail.com",
        "telefon": "+46 70 123 45 67"
      },

      "anvands_av_avsandare": [
        "559203-2279",
        "559034-2187"
      ],

      "statistik": {
        "antal_fakturor": 7,
        "total_belopp_sek": 234500.00,
        "senaste_faktura_datum": "2026-05-06"
      }
    }
  }
}
```

### 3.3 `invoices.json` — Фактуры

```json
{
  "version": 2,
  "uppdaterad": "2026-05-10T12:00:00Z",
  "fakturor": {
    "fakt_2026_001": {
      "id": "fakt_2026_001",
      "version": 1,
      "skapad_datum": "2026-05-06T14:30:00Z",
      "uppdaterad_datum": "2026-05-06T14:35:00Z",

      "nummer": 893,
      "status": "skickad",

      "avsandare_id": "559203-2279",
      "mottagare_id": "559021-3863",

      "datum": {
        "faktura": "2026-05-06",
        "forfallo": "2026-06-05",
        "betalningsvillkor_dagar": 30
      },

      "rader": [
        {
          "nr": 1,
          "typ": "tjanst",
          "beskrivning": "Målartjänster",
          "antal": 70,
          "enhet": "h",
          "apris": 300,
          "moms_procent": 0,
          "belopp_netto": 21000
        },
        {
          "nr": 2,
          "typ": "textrad",
          "beskrivning": "Omvänd skattskyldighet för byggtjänster gäller"
        }
      ],

      "totaler": {
        "netto": 21000.00,
        "moms": 0.00,
        "brutto": 21000.00,
        "avrundning": 0.00,
        "att_betala": 21000.00
      },

      "meta": {
        "referens": "Kommendörsgatan 26, 114 48 Stockholm",
        "momslage": "omvänd skattskyldighet",
        "ocr": "8932",
        "valuta": "SEK"
      },

      "skickning": {
        "miljo": "sandbox",
        "metod": "fakturan_nu_epost",
        "skickad_datum": "2026-05-06T14:35:00Z",
        "fakturan_nu_id": 2845,
        "mottagare_epost": "alshfu@gmail.com"
      },

      "pdf": {
        "sokväg": "/home/administrator/documents/invoices/Jowhar AB/faktura_893_Davids Måleri.pdf",
        "design_shablon": "klassisk_svart"
      },

      "relationer": {
        "krediterad_av": null,
        "kredit_for": null,
        "ersatter": null
      },

      "anteckningar": []
    }
  }
}
```

**Возможные статусы:**
- `utkast` — черновик (создан JSON, но PDF ещё нет)
- `skapad` — PDF сгенерирован, но не отправлен
- `skickad` — отправлен клиенту
- `betald` — оплачен
- `krediterad` — выпущена кредит-нота
- `borttagen` — soft-deleted
- `fel` — ошибка при создании/отправке

### 3.4 `phone_map.json` — Номер → отправитель

```json
{
  "version": 2,
  "uppdaterad": "2026-05-10T12:00:00Z",
  "kopplingar": {
    "+46735272989": {
      "avsandare_id": "559034-2187",
      "roll": "anstalld",
      "namn": "Said",
      "begransningar": {
        "endast_fakturor": true,
        "endast_svenska": true,
        "kan_se_andra_avsandare": false
      }
    },
    "+79956326096": {
      "avsandare_id": null,
      "roll": "agare",
      "namn": "Ägaren",
      "begransningar": {
        "endast_fakturor": false,
        "endast_svenska": false,
        "kan_se_andra_avsandare": true
      }
    }
  }
}
```

### 3.5 `counters.json` — Счётчики

```json
{
  "version": 2,
  "fakturanummer": {
    "559203-2279": 893,
    "559034-2187": 125
  }
}
```

---

## 4. Workflow агента

### 4.1 Входящее сообщение

```
WhatsApp → Фёдор → ОБЯЗАТЕЛЬНО первым делом:
  python3 tools/onboarding/identify_sender.py --telefon {номер}
  
  → {"avsandare_id": "559034-2187", "roll": "anstalld", "begransningar": {...}}
  
Если begransningar.endast_fakturor=true и сообщение не про фактуру:
  python3 tools/messaging/send_template.py \
    --till {номер} \
    --shablon common/access_denied.txt
  
  → Фёдор просто молчит, скрипт сам ответил.
```

### 4.2 Новый отправитель — Wizard

```
Пользователь: "Хочу добавить новую фирму"

Фёдор:
  python3 tools/onboarding/onboard_sender.py --steg start --till {номер}
  
Скрипт сам шлёт первое сообщение из шаблона:
  "Привіт! Расскажу о вашей компании. Введи org_nummer."
  
Фёдор ждёт ответа. Получает org_nummer:
  python3 tools/onboarding/onboard_sender.py --steg orgnr --varde "559203-2279" --till {номер}

Скрипт валидирует, отправляет следующий вопрос. И так до завершения.
В конце скрипт показывает 5 дизайн-шаблонов и просит выбрать.
```

### 4.3 Новая фактура

```
1. identify_sender.py → знаем avsandare_id
2. db_recipients.py --sok "{namn_eller_org}" → находим mottagare или регистрируем
3. db_invoices.py --skapa-utkast → создаём draft в БД, получаем faktura_id
4. summarize.py --id {faktura_id} → генерируем сводку
5. send_template.py --shablon invoice/summary.txt --till {номер} --data {faktura_id}
6. Ждём JA
7. create_invoice.py --id {faktura_id} → PDF через Faktura Constructor
8. send_pdf.py --id {faktura_id} --till {номер}
```

### 4.4 Кредит-нота

```
db_invoices.py --kreditera {faktura_id} --skal "{anteckning}"

Скрипт:
- Создаёт новую запись с typ=kreditnota
- Связывает с оригиналом (kredit_for)
- Меняет статус оригинала на krediterad
- Генерирует PDF
- Отправляет в WhatsApp
```

### 4.5 Удаление

```
db_invoices.py --ta-bort {faktura_id} --skal "{anteckning}"

Soft-delete: статус → borttagen. Запись остаётся в БД для аудита.
PDF файл НЕ удаляется (для архива).
```

---

## 5. Дизайн-шаблоны

5 готовых пресетов в `templates/design/presets.json`:

1. **Klassisk Svart** — тёмная шапка, тёплая бумага (default)
2. **Minimalistisk Vit** — чисто-белая, чёрный текст
3. **Elegant Burgund** — бордовая шапка, тёплый кремовый
4. **Modern Blå** — синяя шапка, светло-серая бумага
5. **Professionell Grön** — зелёная шапка, белая бумага

Каждый шаблон задаёт `style` блок для Faktura Constructor.

---

## 6. Шаблоны сообщений

Все тексты в `templates/messages/`. Переменные в `{}`:

```
templates/messages/sender/welcome.txt:
━━━━━━━━━━━━━━━━━━━━━━━━━━
👋 Välkommen, {namn}!

Jag är Fjodor — din digitala bokföringsassistent.

Innan vi börjar fakturera behöver jag lära känna ditt företag.
Detta tar 5 minuter och du gör det bara en gång.

Är du redo? Svara JA för att börja.
━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Скрипт `send_template.py` подставляет переменные и отправляет в WhatsApp.

---

## 7. Контракт CLI-скриптов

Все скрипты:
- Принимают аргументы через `argparse`
- Возвращают JSON в stdout
- Возвращают exit code 0 при успехе, 1+ при ошибке
- Логируют ошибки в stderr
- Никогда не печатают свободный текст в stdout

Пример:

```bash
python3 tools/db/db_senders.py --hamta 559203-2279
```

```json
{"status":"ok","data":{...},"timestamp":"2026-05-10T12:00:00Z"}
```

Полные контракты см. в `docs/API_CONTRACT.md`.

---

## 8. Внешние сервисы

| Сервис | Назначение | URL |
|--------|----------|-----|
| Faktura Constructor | PDF рендеринг | http://localhost:3030 |
| Fakturan.nu API | Отправка фактур по email | https://app.fakturan.nu/api/v2 |
| OpenClaw Gateway | WhatsApp | ws://127.0.0.1:18789 |
| (future) merinfo.se | Парсинг данных компаний | https://www.merinfo.se |

---

## 9. План миграции

См. `docs/MIGRATION_PLAN.md`.

---

## 10. Что осталось от старого проекта

✅ Сохраняется как есть:
- OpenClaw агенты (только SOUL.md обновляется)
- WhatsApp канал через OpenClaw
- Папка `/home/administrator/documents/invoices/` для PDF

❌ Удаляется:
- `~/invoice_tool/` целиком (заменяется на `~/billing-system/`)
- `renderer.py`, `models.py`, `errors.py` — PDF через Faktura Constructor
- `reportlab` и `playwright` из Python-зависимостей
- Старые `avsandare.json`, `mottagare.json` — мигрируются в новую схему

🔄 Мигрируется:
- Все старые отправители → `data/senders.json` v2
- Все получатели → `data/recipients.json` v2
- Логи фактур → `data/invoices.json` v2 (с пересохранением номеров)
