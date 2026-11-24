# Design Spec: Zero-Demo, 2-Format Dynamic Ingestion & Full Config Externalization

**Date:** 2026-11-25  
**Status:** Pending Approval  
**Scope:** Backend (`app/ingest.py`, `app/analysis.py`, `app/main.py`, `app/assistant.py`), Config (`data/config/`), Frontend (`app/static/`), Live Database (`prototype.db`), Tests (`tests/`)

---

## 1. Intent & Why

Currently, the live application opens with pre-loaded demo data in `prototype.db`, displays a `⚡ Load Demo Case` button, restricts uploads to single CSV files, and contains hardcoded dictionaries, column fallbacks, sample IPDR IPs, and TAC IMEIs inside Python, HTML, and JavaScript.

The user wants a genuine, production-style forensic workflow:
- **Zero Demo Data:** When launched, the live app starts completely clean with **0 cases, 0 CDRs, and 0 IPDRs**. No `Load Demo Case` button or baked-in demo values anywhere.
- **2-Format Ingestion First:** Before analytics unlock, the officer registers a case (or selects an empty case) and uploads data in **2 formats** — supporting both **CSV (`.csv`) and Excel (`.xlsx`, `.xls`)** file formats, AND allowing **dual-format ingestion in one flow** (e.g., CDR Format 1 + CDR Format 2 or CDR + IPDR) with **dynamic header inspection & column mapping** on any unknown file.
- **100% Dynamic Code:** Move all hardcoded lookup dictionaries (`TAC_DATABASE`/`KNOWN_TACS`, `SERVICE_DIRECTORY`) into JSON config files (`data/config/`), remove hardcoded IPDR/TAC/phone literals from HTML/JS/Python, and derive all UI defaults/chips/prefills exclusively from the active case's uploaded database records.

---

## 2. Goals, Non-Goals & Anti-Goals

- **Goals:**
  1. Empty live `prototype.db` on startup (seeded only with RBAC users and Rajasthan tower coordinates).
  2. Ingestion-first UI flow: when active case has 0 records (or 0 cases exist), route directly to Case Creation + Dual-Format Ingestion Wizard; display a clear lock notice on analytics tabs until data is uploaded.
  3. Support `.csv`, `.xlsx`, and `.xls` across both CDR and IPDR ingestion in `app/ingest.py`.
  4. Add `/api/ingest/inspect` endpoint that reads headers + 3 sample rows from any uploaded CSV/Excel file and auto-suggests schema column mappings dynamically.
  5. Support Dual-File / Dual-Format Upload UI (Slot 1 + Slot 2) so investigators can ingest two operator formats (or CDR + IPDR) together before unlocking the dashboard.
  6. Externalize `tac_database.json` and `service_directory.json` into `data/config/` and eliminate duplicate `KNOWN_TACS` in `app/main.py`.
  7. Remove `/api/cases/demo`, `⚡ Load Demo Case` button, hardcoded IPDR IPs (`103.211.54.12`), hardcoded TAC sample buttons, and hardcoded fallback phone strings.
  8. Isolate tests using temporary SQLite DB overrides so running `pytest` never pollutes the live `prototype.db`.

- **Non-Goals:**
  - Changing existing forensic algorithms (MFC, common contacts, co-location meetings, IMEI swaps, CGNAT resolution, Section 5(2) guardrails, PDF/Excel reports).
  - Deleting `data/` sample CSVs from disk (they remain outside the live app for test fixtures and manual testing if desired, though never auto-loaded).

- **Anti-Goals:**
  - Any pre-populated case/CDR/IPDR rows showing up automatically without user upload.
  - Hardcoded fallback numbers/IPs appearing in UI inputs when a case has no data.

---

## 3. Approaches Considered

- **Approach 1 (Selected): Clean Ingestion-First Gate + 2-Format Dynamic Mapper + Zero Hardcoding**
  - Clean `prototype.db`, remove demo route & button, build CSV+Excel dual-slot dynamic column mapper, lock analytics views until upload completes, externalize JSON configs, isolate tests.
  - *Trade-off:* Existing tests that relied on `/api/cases/demo` and live `prototype.db` are refactored to use an isolated temp test DB and upload via `/api/cases/{id}/upload`.
- **Approach 2 (Rejected): Empty DB + Mapper Only, No View Gate**
  - Keeps analytics tabs accessible while empty without guiding the user through 2-format ingestion first. Rejected because it does not enforce the ingestion-first workflow.

---

## 4. Architecture & Component Design

### A. External Dynamic Configs (`data/config/`)
- `data/config/tac_database.json`: Unified TAC lookup table (replaces both `TAC_DATABASE` in `app/analysis.py` and `KNOWN_TACS` in `app/main.py`).
- `data/config/service_directory.json`: Unified toll-free, banking OTP, and helpline directory (replaces `SERVICE_DIRECTORY` in `app/analysis.py`).
- Loaded via helper functions in `app/analysis.py` with graceful fallback if keys aren't found (using GSMA prefix heuristics for unlisted TACs).

### B. Multi-Format & Dynamic Header Ingestion (`app/ingest.py` + `app/main.py`)
- Helper `read_tabular_bytes(file_bytes: bytes, filename: str) -> pd.DataFrame`:
  - Detects `.xlsx` / `.xls` vs `.csv` by extension (falling back cleanly) and parses using `pd.read_excel(..., dtype=str)` or `pd.read_csv(..., dtype=str)`.
- Function `inspect_uploaded_file(file_bytes: bytes, filename: str) -> dict`:
  - Extracts exact column headers, row count, first 3 preview rows, auto-detected file type (`CDR` vs `IPDR`), and auto-suggested column mapping dictionary matched against normalized synonyms (no hardcoded single operator fallback).
- New Endpoint `POST /api/ingest/inspect`:
  - Accepts an uploaded `.csv`/`.xlsx` file, returns `{filename, format, columns, preview_rows, suggested_type, suggested_mapping}`.
- Updated `POST /api/cases/{case_id}/upload`:
  - Accepts `.csv`, `.xlsx`, `.xls` and custom dynamic mapping JSON generated by the UI mapper (or saved operator preset).
  - Fixes validation report response keys so `batch_id`, `rejected_details`, and `missing_counts` render properly in UI.
- New Endpoint `GET /api/cases/{case_id}/ipdr/sample`:
  - Returns one actual IPDR `(source_ip, source_port, session_start)` tuple from the active case's uploaded DB records (or `null` if none), replacing the hardcoded `103.211.54.12` pre-fill.
- Remove `POST /api/cases/demo`.

### C. Clean Ingestion-First Frontend (`app/static/index.html`, `app/static/app.js`)
- **Header Cleanup**: Remove `⚡ Load Demo Case` button completely.
- **Ingestion-First Gate**:
  - On app load, if 0 cases exist OR active case has `cdr_count == 0 && ipdr_count == 0`:
    - Auto-switch to the **2-Format Data Ingestion Workspace** (`view-import`) with a clear step banner (*"Step 1: Register/Select Case → Step 2: Upload 2 Format Files (CSV / Excel, CDR & IPDR) → Step 3: Analytics Unlock"*).
    - Trying to switch to an analytics module while `total_records == 0` prompts/routes cleanly to upload data first.
- **Dual-Format Upload Wizard (`view-import`)**:
  - **Slot 1 (Primary File — CDR / Excel or CSV)** + **Slot 2 (Secondary Format File — Operator 2 CDR or IPDR, Excel or CSV)**.
  - Selecting a file in either slot automatically calls `POST /api/ingest/inspect`, displays detected headers, lets the officer interactively adjust any field mapping dropdowns (A-Number, B-Number, Start Time, Duration, Call Type, IMEI, IMSI, Cell ID / IPDR fields) dynamically, and ingests both formats together (`Ingest Both Files & Unlock Analysis`).
  - Once ingested, invalidates `cachedAnalytics`, reloads metrics/details, and switches automatically to `Executive Dashboard`!
- **Dynamic UI Zero-Hardcoding**:
  - Remove hardcoded `<option value="operator_a">` HTML tags (populated dynamically from `/api/mappings` filtered by `CDR`/`IPDR`).
  - Remove hardcoded `#ipdr-query-ip` value (`103.211.54.12`) and `prefillIpdrTest()` constants; fetch dynamically from `/api/cases/{case_id}/ipdr/sample`.
  - Remove hardcoded TAC sample IMEI buttons in `#modal-tac`; dynamically populate buttons from actual IMEIs present in `cachedAnalytics.imei_summary`.
  - Remove hardcoded fallback IP in `app/assistant.py` (`intent_node`) — query latest `IPDRRecord` from DB for the active case if no IP is provided in the question.

### D. Live DB Cleanup & Test Isolation
- Reset `prototype.db` cleanly so it contains only the 3 RBAC users (`io_sharma`, `sp_verma`, `admin`) and Rajasthan tower master records — **0 cases, 0 CDRs, 0 IPDRs, 0 batches, 0 observations**.
- Update `tests/conftest.py` (or test fixtures in `tests/test_demo_flow.py` and `tests/test_forensic_suite.py`) to use `TestClient` + an isolated temporary SQLite DB (created per test session and cleaned up) uploading real CSV & Excel test files via `/api/cases/{id}/upload` instead of touching live `prototype.db` or `/api/cases/demo`.

---

## 5. Verification Plan

1. **Unit & Integration Tests (`pytest`)**:
   - Test CSV and Excel (`.xlsx`) ingestion & normalization.
   - Test `/api/ingest/inspect` dynamic header detection on arbitrary unseen column names.
   - Test Dual-Format ingestion unlocking analytics from empty state.
   - Test externalized `tac_database.json` and `service_directory.json` loading.
   - Test that `/api/cases/demo` is gone (`404`) and fresh app startup has 0 cases/CDRs/IPDRs.
2. **Playwright E2E Verification**:
   - Open live app with clean `prototype.db` -> verify empty ingestion-first gate, 0 demo numbers, 0 demo alerts.
   - Create a new case -> inspect & upload 2 files (e.g. an `.xlsx` CDR + a `.csv` IPDR/CDR) via the UI -> verify dynamic column mapper -> ingest -> verify dashboard unlocks and populates dynamically with zero console errors.
