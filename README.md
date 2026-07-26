# PackIn.ai

Agentic carton box inventory tracker. Deducts stock automatically when an invoice is processed, replenishes it when a PO is uploaded, and flags anything ambiguous — misread handwriting, out-of-catalog sizes, brand substitutions, unmapped customers — into a review queue instead of guessing.

Full architecture write-up, DB schema, and edge-case list: see [`docs/carton-inventory-architecture.md`](./docs/carton-inventory-architecture.md).

## Design principle

**LLMs extract and suggest. Deterministic Python computes and writes.** No model call ever performs arithmetic or touches the ledger directly — extraction agents only turn messy invoice/PO input into structured JSON; everything from there (size rounding, brand lookup, stock deduction, guardrails) is plain, testable Python.

## Extraction provider fallback chain

Every extraction call (invoice or PO slip) tries providers in order until one succeeds, so a single provider outage or rate limit doesn't stop processing:

1. **Gemini** (`gemini-3.6-flash`) — Google's current fastest/cheapest tier tuned for high-volume document extraction
2. **Groq** (`qwen/qwen3.6-27b`) — 27B multimodal model on Groq's LPU hardware, fastest raw inference
3. **Hugging Face** (`Qwen/Qwen2.5-VL-7B-Instruct`) — open-weight fallback, tuned for documents/layouts/structured output

Order is configurable via `EXTRACTION_PROVIDER_ORDER` in `.env` — set only the keys you have and drop the rest from the list. Which provider actually served a given extraction is recorded on the response (`_extraction_provider`) and surfaces in the `/activity` feed, so you can see over time whether Claude is handling everything or backups are firing often (a signal worth investigating either way).

## Quick start

```bash
git clone <repo-url>
cd packin-ai

cp .env

docker-compose up --build
```

- Backend + docs: http://localhost:8000/docs
- Frontend (PWA): http://localhost:3000

On first boot the backend seeds the box-size catalog (`15/17/19/21` × `16/18/20` × `4/6/8`) and the four starter brands (Metro Steel, Modular Kitchen, Danfe, Dream Kitchen). Edit `backend/app/db/seed.py` to match real brand list.

## Running locally without Docker

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env   
uvicorn app.main:app --reload
```

```bash
cd frontend
npx serve -l 3000 
```

## Running tests

```bash
cd backend
python -m pytest tests/ -v
```

Covers the safety-critical deterministic logic: box-size rounding (regular vs outsize vs exceeds-catalog), ledger guardrails (negative-stock prevention, large-deduction sanity check), and invoice idempotency.

## Key endpoints

| Endpoint | Purpose |
|---|---|
| `POST /invoices/upload` | Upload a Busy-exported invoice PDF (or photo) — auto-extracts, resolves, deducts |
| `POST /po/upload-excel` | Upload a filled `PO_Upload_Template.xlsx` — the primary PO ingestion path |
| `POST /po/upload-slip` | Upload a photo of a handwritten PO slip — extracts + validates, doesn't write until confirmed |
| `POST /po/confirm` | Apply a human-confirmed set of slip items to the ledger |
| `GET /inventory` | Current stock by size × brand |
| `GET /inventory/export?format=xlsx\|pdf` | Download a formatted stock report |
| `GET /review` | Everything currently flagged for human review |
| `POST /review/resolve-substitution` | Confirm which brand's box was actually used on a shortage |
| `POST /review/correct-brand` | Retroactively fix a misattributed brand (audit-trail preserving) |
| `POST /combinations/log-batch` | Weekend batch entry for oversize items packed from taped-together boxes |
| `GET /brands`, `POST /brands`, `POST /brands/map-customer` | Brand and customer-mapping admin |

## Repository layout

```
packin-ai/
├── backend/         FastAPI app, agents, resolver/ledger logic, tests
├── frontend/         PWA (vanilla JS, installable on phone, camera capture)
├── docs/              architecture spec and PO upload template
└── docker-compose.yml
```

## License

MIT
