# Zero-Demo, 2-Format Dynamic Ingestion & Config Externalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or superpowers:subagent-driven-development) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate all pre-loaded demo data and hardcoded dictionaries/defaults across backend & frontend, enforcing a clean ingestion-first workflow supporting 2 file formats (`.csv` and `.xlsx/.xls`) and dual-file dynamic column mapping.

**Architecture:** Move lookup tables (`TAC_DATABASE`, `SERVICE_DIRECTORY`) into external JSON configs under `data/config/`, upgrade `app/ingest.py` to parse both CSV and Excel files and dynamically inspect/suggest column mappings via `POST /api/ingest/inspect`, remove `/api/cases/demo` and UI demo elements, enforce an ingestion-first gate in `app/static/`, isolate integration tests onto a temporary SQLite DB via FastAPI `TestClient`, and reset live `prototype.db` to zero cases/CDRs/IPDRs.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy, Pandas, OpenPyXL, Vanilla JS + HTML/CSS, Pytest, Playwright MCP.

**Spec:** `docs/superpowers/specs/2026-11-25-dynamic-dual-format-ingestion-design.md`

## Global Constraints
- Zero demo data in live `prototype.db` (only 3 RBAC users + `towers.csv` coordinates on startup).
- Remove `⚡ Load Demo Case` button from UI and `/api/cases/demo` from backend.
- Support both `.csv` and `.xlsx`/`.xls` files in CDR and IPDR ingestion.
- Support Dual-Format upload (Slot 1 + Slot 2) with dynamic header inspection & column mapping before analytics unlock.
- No hardcoded IPs (`103.211.54.12`), sample IMEI buttons, `<option>` mapping tags, or TAC/Service dictionaries in Python/HTML/JS.
- Every task follows TDD (`Red -> Green -> Verify`) and preserves all existing 37 forensic capabilities.

## Review Focus
1. Uploading an `.xlsx` file with completely unseen column names (e.g. `Caller`, `Callee`, `Time`, `Dur`) via `/api/ingest/inspect` + `/api/cases/{id}/upload` with custom mapping JSON must succeed without relying on hardcoded column fallbacks.
2. Uploading a malformed or empty file / unsupported extension to `/api/ingest/inspect` must return HTTP `400` cleanly without 500 tracebacks.
3. Calling `GET /api/cases/{id}/ipdr/sample` on a case with 0 IPDR records must return `{"available": false}` cleanly (no hardcoded IP).
4. Opening the live app on an empty `prototype.db` (0 cases or 0 CDR/IPDR records) must direct the user to the Ingestion-First Wizard and block/empty analytics views until data is ingested.
5. Running the full `pytest` suite must leave live `prototype.db` completely untouched (0 cases, 0 CDRs, 0 IPDRs).

---

### Task 1: Externalize TAC & Service Directory Configs (`data/config/`)

**Files:**
- Create: `data/config/tac_database.json`
- Create: `data/config/service_directory.json`
- Modify: `app/analysis.py:11-85`
- Modify: `app/main.py:733-818`
- Test: `tests/test_forensic_suite.py`

**Interfaces:**
- Produces: `load_tac_database() -> dict`, `load_service_directory() -> dict` in `app/analysis.py`; unified `lookup_tac_device(imei: str) -> dict` returning `brand`, `model`, `generation`, `device_type`, `manufacturer`, `mfr`, `origin`, `tac`, `imei`, `luhn_valid`, `valid_length`.

- [ ] **Step 1: Write failing test for external JSON config loading & unified Luhn TAC metadata**
  Test that `lookup_tac_device("354890123456781")` returns `luhn_valid`, `mfr`, `origin`, `brand`, `model` and loads dynamically from `data/config/tac_database.json`.
- [ ] **Step 2: Run test to verify failure**
  Run: `PYTHONPATH=. .venv/bin/pytest tests/test_forensic_suite.py -k "test_external_config_loading" -v`
- [ ] **Step 3: Create `data/config/tac_database.json` and `data/config/service_directory.json` and refactor `app/analysis.py` & `app/main.py`**
  Merge `TAC_DATABASE` and `KNOWN_TACS` into `data/config/tac_database.json`, merge `SERVICE_DIRECTORY` into `data/config/service_directory.json`, remove `KNOWN_TACS`/`decode_tac_info` duplication from `app/main.py` and delegate `/api/tac/{imei}` and `get_case_analytics` to `lookup_tac_device()`.
- [ ] **Step 4: Run test to verify pass**
  Run: `PYTHONPATH=. .venv/bin/pytest tests/test_forensic_suite.py -k "tac or external_config" -v`
- [ ] **Step 5: Commit**

---

### Task 2: Support `.csv` + `.xlsx/.xls` & Dynamic Header Inspector (`/api/ingest/inspect`)

**Files:**
- Modify: `app/ingest.py:105-385`
- Modify: `app/main.py:345-395`
- Test: `tests/test_core.py`

**Interfaces:**
- Produces: `read_tabular_bytes(file_bytes: bytes, filename: str) -> pd.DataFrame`, `inspect_uploaded_file(file_bytes: bytes, filename: str) -> dict` in `app/ingest.py`; `POST /api/ingest/inspect` and `GET /api/cases/{case_id}/ipdr/sample` in `app/main.py`.

- [ ] **Step 1: Write failing tests for Excel ingestion, dynamic inspection, and IPDR sample endpoint**
  Write tests in `tests/test_core.py` covering:
  - `test_read_and_ingest_excel_cdr`: builds an in-memory `.xlsx` workbook with custom unseen column headers (`SrcNum`, `DstNum`, `CallDir`, `CallDT`, `Secs`, `HandsetIMEI`, `SimIMSI`, `TowerCode`), calls `inspect_uploaded_file()` and `ingest_cdr_data()`, asserts valid ingestion.
  - `test_inspect_invalid_file_raises_value_error`: verifies malformed/empty upload fails cleanly.
- [ ] **Step 2: Run test to verify failure**
  Run: `PYTHONPATH=. .venv/bin/pytest tests/test_core.py -k "excel or inspect_invalid" -v`
- [ ] **Step 3: Implement `read_tabular_bytes`, `inspect_uploaded_file`, Excel support in `ingest_cdr_data`/`ingest_ipdr_data`, plus `POST /api/ingest/inspect` & `GET /api/cases/{case_id}/ipdr/sample` in `app/main.py`**
  Also include `batch_id` and `rejected_details` consistently in ingestion summaries so frontend validation reports render cleanly.
- [ ] **Step 4: Run test to verify pass**
  Run: `PYTHONPATH=. .venv/bin/pytest tests/test_core.py -v`
- [ ] **Step 5: Commit**

---

### Task 3: Remove `/api/cases/demo`, Eliminate `app/assistant.py` Hardcoded IP Fallback, & Isolate Tests from Live DB

**Files:**
- Modify: `app/main.py:221-323` (remove `/api/cases/demo`)
- Modify: `app/assistant.py:78-90` (query latest `IPDRRecord` from DB instead of `"103.211.54.12"`)
- Create: `tests/conftest.py` (isolated temporary SQLite DB + `TestClient(app)` fixture with seeded synthetic upload)
- Modify: `tests/test_demo_flow.py`, `tests/test_forensic_suite.py` (migrate from live `requests` on `prototype.db` to isolated `TestClient`)
- Reset: `prototype.db` (empty cases/CDRs/IPDRs/batches/observations/audit, only 3 RBAC users + Rajasthan towers)

**Interfaces:**
- Produces: Isolated `client` & `auth_headers` fixtures in `tests/conftest.py`; `/api/cases/demo` returns `404`; clean live `prototype.db` with 0 cases.

- [ ] **Step 1: Write failing tests verifying `/api/cases/demo` is removed (`404`) and assistant IPDR lookup handles empty DB without hardcoded IP**
- [ ] **Step 2: Run test to verify failure**
- [ ] **Step 3: Remove `/api/cases/demo` in `app/main.py`, update `app/assistant.py` to query `IPDRRecord` from DB, create `tests/conftest.py`, update `tests/test_demo_flow.py` & `tests/test_forensic_suite.py` to use isolated `TestClient`, and reset live `prototype.db`**
- [ ] **Step 4: Run full `pytest tests/ -v` and confirm 100% pass AND confirm live `prototype.db` still has 0 cases/CDRs/IPDRs**
- [ ] **Step 5: Commit**

---

### Task 4: Frontend Ingestion-First Gate, Dual-Format Upload + Dynamic Column Mapper, & Zero Demo UI

**Files:**
- Modify: `app/static/index.html`
- Modify: `app/static/app.js`
- Modify: `app/static/style.css`

- [ ] **Step 1: Remove `⚡ Load Demo Case` button from header, remove hardcoded `<option>` tags in `#upload-mapping-select`, remove hardcoded `103.211.54.12` IPDR input value, and remove hardcoded TAC sample buttons in `#modal-tac`**
- [ ] **Step 2: Build Dual-Format Upload Wizard (`#view-import`) supporting Slot 1 + Slot 2 (`.csv`, `.xlsx`, `.xls`), auto-calling `POST /api/ingest/inspect` on file selection, rendering dynamic column-mapping selectors from detected headers, and fixing `displayValidationReport()` to show `batch_id` & `rejected_details`**
- [ ] **Step 3: Implement Ingestion-First Gate in `app/static/app.js` (`onCaseSelected` / `switchView`)**:
  - When 0 cases exist OR active case has 0 CDR and 0 IPDR records, auto-route to `#view-import` (or Case Creation Banner) and display an ingestion gate banner when trying to view analytics modules before uploading data.
  - Dynamically populate IPDR Quick Pre-fill via `GET /api/cases/{case_id}/ipdr/sample` and TAC sample chips via `cachedAnalytics.imei_summary`.
  - Refresh `cachedAnalytics`, `loadExecutiveMetrics()`, and `loadCaseDetails()` immediately upon successful upload and unlock dashboard.
- [ ] **Step 4: Restart live `uvicorn` server on clean empty `prototype.db` and verify via Playwright MCP**:
  - Check clean start (0 cases/CDRs/IPDRs, no demo button, ingestion-first view active).
  - Register a case -> inspect & upload 2 formats (`.xlsx` CDR + `.csv` IPDR) -> verify dynamic header mapper -> ingest -> verify analytics unlock & populate dynamically with 0 console errors!
- [ ] **Step 5: Run full `pytest tests/ -v`, update screenshots/docs if needed, and commit + push**
