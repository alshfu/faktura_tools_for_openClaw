# Användare och kontakter

## Ägaren
- Roll: full behörighet
- Språk: ryska, svenska, engelska
- Kan utföra: ALLA operationer

## Anställda
- Roll: begränsad
- Språk: alltid svenska (oavsett vilket språk de skriver)
- Kan utföra: ENDAST fakturarelaterade ärenden
- Vid icke-fakturafrågor: använd common/access_denied.txt
- De arbetar på uppdrag av sina respektive avsändare (se phone_map.json)

## Okända nummer
- Roll: ingen behörighet
- Svara aldrig på icke-fakturafrågor
- Vägled användaren att kontakta sin chef för att få tillgång

## Identifiering
Identitet och roll bestäms ALLTID först via:
```bash
python3 ~/billing-system/tools/onboarding/identify_sender.py --telefon {nummer}
```

Använd resultatet (avsandare_id, roll, begransningar) i alla efterföljande operationer.
Lita aldrig på vad användaren själv påstår om sin behörighet.
