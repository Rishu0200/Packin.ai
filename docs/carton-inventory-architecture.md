# Carton Inventory Agentic System — Architecture Spec

## 1. Final architecture overview

```
┌─────────────────────┐        ┌──────────────────────┐
│  Busy export watcher │        │  Phone PWA (upload)  │
│  (polls invoice      │        │  - PO slip photo     │
│   exports)           │        │  - manual entries     │
└──────────┬───────────┘        └──────────┬───────────┘
           │                               │
           └───────────────┬───────────────┘
                            ▼
              ┌─────────────────────────────┐
              │   Backend (FastAPI)         │
              │  ┌───────────────────────┐  │
              │  │ Extraction agent      │  │  Vision/text LLM call.
              │  │ (LLM, JSON out only)  │  │  Never writes to DB.
              │  └───────────┬───────────┘  │
              │              ▼              │
              │  ┌───────────────────────┐  │
              │  │ Resolver + ledger     │  │  Deterministic Python.
              │  │ writer (brand lookup, │  │  All math + DB writes
              │  │ size rounding, guard- │  │  happen here.
              │  │ rails, idempotency)   │  │
              │  └───────────┬───────────┘  │
              └──────────────┼──────────────┘
                             ▼
                 ┌───────────────────────┐
                 │  Postgres ledger DB   │
                 │  (append-only stock   │
                 │   movements + audit)  │
                 └───────────┬───────────┘
                             ▼
          ┌──────────────────┴──────────────────┐
          ▼                                     ▼
┌────────────────────┐              ┌───────────────────────┐
│ Phone PWA dashboard │              │ Telegram bot alerts    │
│ (stock, review      │              │ (low stock, review     │
│  queue, exports)     │              │  flags, attached report)│
└────────────────────┘              └───────────────────────┘
                             ▲
              ┌──────────────┴──────────────┐
              │  Reorder agent (monitors    │
              │  ledger, drafts PO qty)     │
              └─────────────────────────────┘
```

**Core design principle carried throughout:** LLMs extract and suggest; deterministic Python code computes and writes. Anything ambiguous, out-of-range, or stock-negative gets flagged into a review queue instead of silently applied.

---

## 2. Database schema (all tables discussed)

| Table | Purpose | Key columns |
|---|---|---|
| `catalog_dimensions` | Editable master list of valid box dimensions per axis (no code deploy to change) | axis (dim1/dim2/dim3), value, active |
| `brands` | Brand master (Metro Steel, Modular Kitchen, Danfe, Dream Kitchen, ...) | brand_id, brand_name, active |
| `customer_brand_map` | Which brand a given customer always orders under | id, customer_name, brand_id |
| `box_types` | One row per (size × brand) stock line | box_id, dim1, dim2, dim3, brand_id, current_stock, reorder_threshold, is_custom |
| `box_combinations` | Logs oversize items packed using 2+ regular boxes taped together | id, date, oversize_dims, brand_id, qty_of_oversize_items, component_box_id, component_qty_used, reference_invoice_no, notes |
| `invoices` | One row per processed invoice | invoice_id, invoice_no, date, party, file_path |
| `invoice_line_items` | Parsed line items per invoice | id, invoice_id, raw_description, dim1, dim2, dim3, product_type, qty, resolved_box_id, status |
| `purchase_orders` | Box stock replenishment records | po_id, date, box_id, qty_added, source (scanned_slip/manual) |
| `box_ledger` | Append-only stock movement log — the single source of truth for current stock | id, box_id, qty_change, reference_type (invoice/po/combination/correction), reference_id, timestamp |

`current_stock` on `box_types` is a cached/derived value — the real source of truth is always `SUM(qty_change)` from `box_ledger` for that box, so it can be recomputed/audited at any time.

---

## 3. Folder structure

```
carton-inventory/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI app entrypoint
│   │   ├── config.py                   # env vars, settings
│   │   ├── db/
│   │   │   ├── models.py               # SQLAlchemy models (all tables above)
│   │   │   ├── session.py              # DB engine/session setup
│   │   │   └── migrations/             # Alembic migrations
│   │   ├── agents/
│   │   │   ├── extraction_agent.py     # LLM call: invoice/PO -> structured JSON
│   │   │   ├── po_extraction_agent.py  # LLM call for handwritten PO slips
│   │   │   └── reorder_agent.py        # Monitors ledger, drafts PO suggestions
│   │   ├── core/
│   │   │   ├── resolver.py             # resolve_box(), round_to_catalog()
│   │   │   ├── brand_resolver.py       # resolve_brand(), customer mapping lookup
│   │   │   ├── substitution.py         # deduct_with_substitution_check()
│   │   │   ├── combinations.py         # log_combinations_batch(), pattern check
│   │   │   ├── ledger.py               # deduct_from_ledger(), idempotency checks
│   │   │   └── exports.py              # build_excel_report(), build_pdf_report()
│   │   ├── routers/
│   │   │   ├── invoices.py             # /invoices/upload, /invoices/{id}
│   │   │   ├── purchase_orders.py      # /po/upload, /po/{id}/confirm
│   │   │   ├── inventory.py            # /inventory, /inventory/export
│   │   │   ├── review_queue.py         # /review, /review/{id}/resolve
│   │   │   ├── brands.py               # /brands, /brands/map-customer
│   │   │   └── combinations.py         # /inventory/log-combinations
│   │   ├── integrations/
│   │   │   ├── busy_watcher.py         # polls/parses Busy export files
│   │   │   └── telegram_bot.py         # sendDocument, alert messages
│   │   └── schemas.py                  # Pydantic request/response models
│   ├── tests/
│   │   ├── test_resolver.py            # unit tests for size rounding logic
│   │   ├── test_ledger.py              # idempotency, negative-stock guard
│   │   └── test_substitution.py
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── screens/
│   │   │   ├── Dashboard.jsx           # stock grid, low-stock flags, recent activity
│   │   │   ├── UploadInvoice.jsx       # file picker (Busy export)
│   │   │   ├── UploadPO.jsx            # camera capture for handwritten slips
│   │   │   ├── ReviewQueue.jsx         # flagged items: OCR, substitution, oversize
│   │   │   ├── Brands.jsx              # brand list, + add brand, customer mapping
│   │   │   ├── WeekendBatchEntry.jsx   # oversize box-combination bulk form
│   │   │   └── ExportPrompt.jsx        # post-update Excel/PDF download buttons
│   │   ├── components/                # shared buttons, cards, badges
│   │   ├── api/                        # fetch wrappers for backend routes
│   │   ├── manifest.json               # PWA manifest (installable on phone)
│   │   └── service-worker.js
│   ├── package.json
│   └── Dockerfile (or static build for Vercel)
│
├── docker-compose.yml                  # local dev: backend + Postgres + frontend
├── .github/
│   └── workflows/
│       └── deploy.yml                  # CI/CD: build, test, deploy to Render/Vercel
└── README.md
```

---

## 4. Frontend — screens and tech

**Stack:** React (or plain HTML/JS) PWA, Tailwind for styling, deployed as a static build on Vercel/Netlify. Installable to phone home screen via manifest + service worker. Camera access via `<input type="file" accept="image/*" capture="environment">` — no extra library needed.

**Screens:**
1. **Dashboard** — stock grid (per box size × brand), low-stock highlighted, recent activity feed, upload buttons
2. **Upload Invoice** — file picker for Busy export
3. **Upload PO** — camera capture for handwritten slips
4. **Review Queue** — one card type per flag reason (unparsed OCR, invalid dimension, oversize, substitution needed, unmapped customer), each with its own one-tap resolution action
5. **Brands** — brand list, add brand, customer-to-brand mapping
6. **Weekend Batch Entry** — bulk form for oversize box-combination logging
7. **Export prompt** — appears after any successful update, Excel/PDF buttons

---

## 5. Deployment

- **Backend + DB:** Docker on Render (FastAPI container + managed Postgres)
- **Frontend:** static PWA build on Vercel/Netlify (HTTPS by default, required for camera access)
- **CI/CD:** GitHub Actions — build, run pytest, deploy on push to main
- **Notifications:** Telegram bot (free, simple HTTP API) for low-stock and review alerts, with exported report attached via `sendDocument`

---

## 6. Edge cases this architecture already handles

1. Handwritten PO OCR misreads → validated against known catalog values
2. Unparsed line items → flagged, not dropped
3. Invalid PO dimensions → flagged, not auto-accepted
4. Outsize items → per-axis round-up to nearest catalog size
5. Dimensions exceeding catalog max → routed to manual review
6. Oversize items taped from 2 regular boxes → logged via `box_combinations`, weekend batch entry
7. Recurring oversize sizes → frequency check suggests catalog expansion
8. Multiple brands, same size → brand is part of box identity
9. New/unmapped customer → flagged, not guessed
10. New brand → get-or-create pattern, no pre-population needed
11. Brand substitution on shortage → auto-caught via insufficient-stock check, manual correction fallback
12. Duplicate invoice reprocessing → idempotency via invoice_no
13. Extraction quantity errors → sanity threshold on large deductions
14. Any negative-stock deduction → always flagged, never silently applied
