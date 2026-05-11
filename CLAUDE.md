# CLAUDE.md — Rules for working with this project

## Project overview

WhatsApp-based multi-tenant invoice management system for OpenClaw + Faktura Constructor.
Stack: Python 3.10+ (business logic), Node.js + Puppeteer (PDF rendering), JSON files (data layer), OpenClaw (WhatsApp gateway).

---

## Core rules

### 1. Surgical edits only — never rewrite whole files
- Edit only the function, block, or line that needs changing.
- Never rewrite an entire file or module unless explicitly asked.
- Never reorganize imports, rename variables, or reformat code in files you are not actively fixing.
- If a file has 200 lines and you need to fix 5 lines — touch only those 5 lines.

### 2. Don't touch what isn't broken
- If a module or function is not related to the task at hand, leave it untouched.
- Do not refactor, "clean up", or "improve" surrounding code while fixing a bug.
- Do not add docstrings, type hints, or comments to code you didn't change.

### 3. No speculative additions
- Don't add error handling for situations that can't happen in this architecture.
- Don't add config flags, environment variable toggles, or feature switches unless asked.
- Don't create helpers or abstractions for one-off operations.

### 4. Data files are sacred
- **Never modify** files in `data/` (`senders.json`, `recipients.json`, `invoices.json`, `phone_map.json`, `counters.json`).
- These are live databases. All mutations go through the `tools/db/` scripts.

### 5. Templates are read-only text
- Files in `templates/messages/` are WhatsApp message templates. Do not rename, restructure, or alter their variable syntax (`{variable_name}`).
- `templates/design/presets.json` contains the 5 design presets. Do not add or remove presets without being explicitly asked.

### 6. Agent instruction files — hands off
- `SOUL_fyodor.md` and `USER_fyodor.md` are agent behavioral specifications consumed by the OpenClaw agent. Do not edit these unless explicitly asked.

### 7. Faktura Constructor service is a separate subsystem
- The `faktura-service/` directory is a standalone Node.js service with its own lifecycle.
- Do not modify `server.js`, `renderer.js`, `render-pdf.js` unless the task is explicitly about the PDF rendering service.
- The HTTP API (`POST /pdf`, `POST /html`) on port 3030 is stable — don't change it.

### 8. CLI interface is a contract
- All scripts in `tools/` expose a stable CLI interface used by the OpenClaw agent.
- Never rename flags, remove flags, or change the output format (JSON) of any script without updating every caller.
- Adding a new optional flag is safe; changing existing flags is not.

### 9. Database schema versioning
- All JSON databases use `"version": 2` schema. Do not change the schema structure without updating **all** db scripts that read/write it.
- New optional fields can be added. Existing fields must not be renamed or removed.

### 10. Swedish language is the default
- Business logic, message templates, variable names in JSON schemas, and comments in `tools/` are in Swedish or follow Swedish conventions (e.g., `avsandare`, `mottagare`, `faktura`). Keep it that way.
- Internal code (Python function names, variables) can be in English — that's already mixed and consistent.

---

## Directory responsibilities

| Directory | What it does | Touch when |
|-----------|-------------|------------|
| `tools/db/` | JSON CRUD for all entities | Adding/fixing data operations |
| `tools/workflow/` | High-level invoice lifecycle | Adding/fixing workflow steps |
| `tools/onboarding/` | Registration wizards (state machines in `/tmp/billing_wizard/`) | Adding/fixing onboarding steps |
| `tools/messaging/` | WhatsApp template dispatch | Fixing message delivery |
| `tools/utils/` | Validators, OCR, VAT, mapper | Fixing calculation/validation bugs |
| `faktura-service/` | PDF rendering service | PDF layout or rendering bugs |
| `templates/messages/` | WhatsApp text templates | Adding/editing message text only |
| `templates/design/` | PDF design presets | Adding/editing design options |
| `data/` | Live JSON databases | **Never directly** |

---

## Before making any change

1. Read the specific file and function you are about to edit.
2. Understand what calls it and what it calls.
3. Make the minimal change that solves the problem.
4. If a CLI flag is involved, check all callers in `tools/workflow/` and `tools/onboarding/`.
5. If a JSON field is involved, check all db scripts that read/write it.
