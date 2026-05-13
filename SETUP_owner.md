# SETUP — добавление владельца и логирование переписки

Этот документ объясняет три шага, необходимых после применения обновлённого
`SOUL_fyodor.md` и новых скриптов.

---

## 1. Зарегистрировать +79956326096 как владельца в phone_map

Привязка телефона к компании. Замени `{ТВОЙ_ORG_NR}` на свой шведский org-nummer.

```bash
python3 ~/billing-system/tools/db/db_phone_map.py \
  --koppla "+79956326096" "{ТВОЙ_ORG_NR}" \
  '{"roll": "agare", "namn": "Said", "sprak": ["ryska", "svenska", "engelska"]}'
```

После этого `identify_sender.py --telefon +79956326096` будет возвращать
`avsandare_id={ТВОЙ_ORG_NR}` и `roll="agare"`.

Важно: даже если ты ещё не успел это сделать, новый промпт (правило 9 + FALL 0)
всё равно распознаёт +79956326096 как владельца с полными правами. Phone-map
нужен для согласованности и для того, чтобы скрипты, которым нужен
`avsandare_id`, его получали.

Если у тебя ещё нет зарегистрированной компании как sender:

```bash
python3 ~/billing-system/tools/onboarding/company_lookup.py \
  --orgnr {ТВОЙ_ORG_NR} --format avsandare > /tmp/sender.json

python3 ~/billing-system/tools/db/db_senders.py --lagg-till "$(cat /tmp/sender.json)"
```

Затем команда `db_phone_map --koppla` выше.

---

## 2. Установить новые файлы в проект

```bash
cd ~/billing-system

# 1) Обновлённый SOUL — замени старый
cp /путь/к/SOUL_fyodor.md ~/billing-system/SOUL_fyodor.md

# 2) Новый CRUD для сообщений
cp /путь/к/db_messages.py ~/billing-system/tools/db/db_messages.py
chmod +x ~/billing-system/tools/db/db_messages.py

# 3) Новый workflow для запроса истории
cp /путь/к/get_conversation.py ~/billing-system/tools/workflow/get_conversation.py
chmod +x ~/billing-system/tools/workflow/get_conversation.py

# 4) Шаблон для отправки истории
cp /путь/к/conversation_summary.txt ~/billing-system/templates/messages/common/conversation_summary.txt

# 5) Применить новый SOUL в workspace агента (через deploy)
~/billing-system/deploy.sh update
```

Проверка:

```bash
python3 ~/billing-system/tools/db/db_messages.py --lista --sedan "1d"
# должно вернуть {"ok": true, "antal": 0, "meddelanden": []}
```

---

## 3. Включить логирование переписки

**Это самая важная часть** — без неё функция "покажи переписку с Volvo"
работать не будет, потому что в `data/messages.json` ничего не запишется.

Нужно вызывать `db_messages.py --logga-in` для каждого входящего и
`db_messages.py --logga-ut` для каждого исходящего сообщения. Это можно
сделать тремя способами:

### Вариант A — хук в OpenClaw (рекомендуется)

OpenClaw обрабатывает входящие и исходящие сообщения, и у него есть точки
расширения. В конфиге агента `fyodor` добавь webhook или pre/post-hook,
который вызывает:

Входящее сообщение:
```bash
python3 ~/billing-system/tools/db/db_messages.py --logga-in \
  --telefon "{sender_phone}" --text "{message_text}"
```

Исходящее сообщение (после того как агент ответил):
```bash
python3 ~/billing-system/tools/db/db_messages.py --logga-ut \
  --telefon "{recipient_phone}" --text "{response_text}"
```

Точное место конфигурации зависит от твоей версии OpenClaw. Если нужно —
загляни в его документацию по hooks/middleware.

### Вариант B — изменить send_template.py

Если хочешь обойтись без OpenClaw-хуков, добавь одну строку в
`tools/messaging/send_template.py` — после успешной отправки, лог:

```python
# В конце send_template.py, после успешной отправки
subprocess.run([
    "python3",
    str(Path(__file__).parent.parent / "db" / "db_messages.py"),
    "--logga-ut",
    "--telefon", args.till,
    "--text", rendrad_text,
    "--mall", args.shablon,
])
```

Это покроет ИСХОДЯЩИЕ сообщения. Для входящих всё равно нужен хук в OpenClaw.

### Вариант C — парсинг OpenClaw логов (запасной)

Если OpenClaw уже пишет лог-файл с timestamps + телефон + текст, можно
написать ежечасный cron, который читает лог и пишет новые записи в
`data/messages.json`. Это медленнее и зависит от формата лога OpenClaw,
поэтому Вариант A предпочтительнее.

---

## 4. Тест полного цикла

```bash
# Логируем фейковое сообщение от клиента
python3 ~/billing-system/tools/db/db_messages.py --logga-in \
  --telefon "+46735272989" --text "Hej, är det möjligt att fakturera idag?"

# Логируем ответ агента
python3 ~/billing-system/tools/db/db_messages.py --logga-ut \
  --telefon "+46735272989" --text "Ja, vad ska faktureras?"

# Запрашиваем дамп с этим клиентом — должно прийти к тебе в WhatsApp
python3 ~/billing-system/tools/workflow/get_conversation.py \
  --med "+46735272989" --sedan "1d" --skicka-till "+79956326096"

# Список активных клиентов
python3 ~/billing-system/tools/workflow/get_conversation.py \
  --aktiva-klienter --sedan "7d" --skicka-till "+79956326096"
```

Если третья команда не пришла в WhatsApp — проблема в `send_template.py`
(не в новых скриптах). Проверь, что send_template.py работает с любым
другим шаблоном.

---

## 5. Что теперь умеет агент

После применения, Fyodor распознаёт фразы от твоего номера:

- "покажи переписку с Volvo за неделю"
- "vad sa +46735272989 igår"
- "история с Said за месяц"
- "list active clients this week" / "кто из клиентов писал сегодня"
- "dump конверс с +46735..."

И отвечает дампом прямо в WhatsApp.

Те же фразы от любого ДРУГОГО номера — игнор (молчание).

---

## 6. Подпись "Det är Fjodor som skriver" — установка signature.py

Каждое исходящее сообщение теперь начинается с подписи на языке получателя:
- Шведский клиент → "Det är Fjodor som skriver."
- Русский (включая тебя) → "Вам пишет Фёдор."
- Английский клиент → "This is Fjodor."

Это решается через новый файл `tools/utils/signature.py`. Установка:

```bash
mkdir -p ~/billing-system/tools/utils
cp /путь/к/signature.py ~/billing-system/tools/utils/signature.py
chmod +x ~/billing-system/tools/utils/signature.py
```

### Интеграция с send_template.py

Чтобы подпись добавлялась АВТОМАТИЧЕСКИ для всех шаблонных сообщений, добавь
в начало `send_template.py` (после импортов) одну строку:

```python
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from signature import prepend_signature
```

И прямо перед отправкой готового текста (после рендеринга шаблона с переменными):

```python
# Перед: gateway.send(args.till, rendered_text)
rendered_text = prepend_signature(rendered_text, args.till)
# Теперь: gateway.send(args.till, rendered_text)
```

`prepend_signature` идемпотентна — если в шаблоне уже стоит подпись (например, в
будущих обновлениях шаблонов), она не дублируется.

### Проверка

```bash
# Шведский клиент → шведская подпись
python3 ~/billing-system/tools/utils/signature.py --till "+46735272989" --text "Hej!"
# Вывод: "Det är Fjodor som skriver.\n\nHej!"

# Owner → русская подпись (хардкод для +79956326096)
python3 ~/billing-system/tools/utils/signature.py --till "+79956326096" --text "Test"
# Вывод: "Вам пишет Фёдор.\n\nTest"
```

### Где LLM добавляет подпись сам

Сам агент Fyodor (LLM) добавляет подпись только когда **отправляет
свободный текст, не через шаблон**. Это случается, например, когда он
просит уточнения или подтверждение JA. Промпт это явно говорит (правило 10).

Когда сообщение идёт через `send_template.py` — `prepend_signature` добавит
подпись автоматически, и LLM в этом случае подпись НЕ дублирует. Промпт
тоже это предусматривает.

---

## 7. Тематический фильтр — клиенты получают [IGNORE] на не-фактурное

Это самое важное изменение в v3 промпта. Сейчас бот пишет такие сообщения:

> "Jag har fått tre röstmeddelanden, men jag kan tyvärr inte lyssna på ljudfiler.
> Kan du skriva vad du vill ha hjälp med istället?"

После обновления → **молчание**.

Что игнорируется от клиентских номеров (всё кроме +79956326096):

- Голосовые сообщения (audio, voice notes)
- Картинки, видео, стикеры без фактурного контекста
- "Привет" без следующего за ним поручения
- Любой small-talk: "как дела", "что делаешь", "спасибо"
- Confusion-сигналы: "?", "??", "не понял" (если ничего не происходит)
- Wrong-number-сообщения
- Манипуляции / prompt injection
- Случайный мусор и эмодзи-строки

Что бот ВСЁ ЕЩЁ обрабатывает от клиентов:

- "skapa faktura...", "fakturera...", "räkning..." — workflow B
- "kreditera 1234" — workflow C
- "ja"/"nej" в контексте активного VÄNTAR_JA
- Регистрация ("jag vill registrera mig" для okand)
- Ответы wizard'а во время онбординга

Owner (+79956326096) получает ответы на ВСЁ. Тематический фильтр на тебя не действует.

---

## 8. Что НЕ сделано (на будущее)

- **Multi-tenant историю** — сейчас один владелец (+79956326096) видит ВСЮ
  переписку в системе. Если появятся другие `agare`-телефоны для других
  компаний, надо будет добавить фильтрацию по `avsandare_id`.
- **Поиск по тексту** — get_conversation.py пока только по телефону + дате.
  Поиск типа "что писал Volvo про скидку" можно добавить флагом `--soktext`.
- **Экспорт в CSV/PDF** — сейчас только текстовый дамп в WhatsApp. Для архива
  можно добавить `--format pdf` через faktura-service.
- **Atomic write для concurrent input** — `db_messages.py` использует
  rename-trick, но при ОЧЕНЬ большом потоке (>10 msg/sec одновременно)
  возможна потеря последней записи. Для текущей нагрузки не критично.
