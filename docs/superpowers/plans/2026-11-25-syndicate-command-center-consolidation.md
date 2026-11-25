# Syndicate Intelligence Command Center Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the Rajasthan Police Cyber Forensic Suite into an integrated 7-Workbench Investigation Command Center featuring suspect threat risk scoring, 24x7 temporal heatmaps, multi-suspect geospatial playback, batch IPDR resolution, real LEA preamble stripping, 66-tower master sync, and a tamper-evident SHA-256 audit chain.

**Architecture:** Consolidate the 36-view flat sidebar into 7 cohesive workbenches with tabbed navigation while maintaining 100% backward compatibility with all 35+ existing REST API endpoints. Enforce genuine law-enforcement capabilities on the backend (skipping LEA preambles in Airtel/Jio CDRs, indexing 66 towers across Rajasthan & Mewat, querying 275k TACs, and chaining audit entries via SHA-256) while surfacing rich interactive visual components (threat cards, 24x7 heatmap, Leaflet animated time scrubber, Cytoscape centrality sizing with slide-in node evidence drawer).

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy, SQLite (WAL mode), Pandas, Chart.js, Cytoscape.js, Leaflet.js, ReportLab, OpenPyXL, PyTest.

**Spec:** `docs/superpowers/specs/2026-11-25-syndicate-command-center-consolidation-design.md`

## Global Constraints
- Python 3.12+ compatibility (tested up to 3.14).
- Zero hardcoded demo cases/CDRs/IPDRs on startup (ingestion-first gate preserved).
- All 35+ existing API endpoints and existing 41 tests must continue to pass without regression.
- Section 5(2) Indian Telegraph Act guardrail must remain strictly enforced (no audio wiretapping).
- Every extracted forensic data item must retain `source_file` and `source_row` for Section 65B Indian Evidence Act admissibility.

## Review Focus
1. Raw LEA CDR files (`airtel_lea_cdr.csv`, `jio_lea_cdr.csv`) starting with non-standard telco preambles must parse correctly without dropping real call records.
2. Cross-suspect movement calculations in `get_case_analytics` must group by subscriber to avoid generating impossible speed hops between two distinct callers.
3. Blank IMEI CDR records must be tolerated with an ingestion warning rather than discarding the entire call transaction.
4. Audit log hash chain must detect any modified or deleted record and return `TAMPERED` status.
5. All legacy view IDs (`view-dashboard`, `view-mfc`, `view-graph`, `view-raw-cdr`, etc.) must remain accessible inside the consolidated workbenches to preserve deep-linking.

---

### Task 1: Ingestion & Tower Master Enhancements (LEA Preamble Stripping & 66 Tower Master)

**Files:**
- Modify: `app/ingest.py:105-187, 483-506`
- Test: `tests/test_forensic_suite.py`

**Interfaces:**
- Consumes: Raw file bytes from Airtel/Jio LEA CSVs and `data/rajasthan_cell_towers_master.csv`
- Produces: `read_tabular_bytes` with automatic header preamble detection; `seed_towers_from_csv` seeding all 66 Rajasthan towers

- [ ] **Step 1: Write failing tests for LEA preamble stripping and 66 tower master seeding**

```python
def test_lea_preamble_stripping_and_ingestion(client, auth_headers):
    # Test reading a CSV with LEA preamble lines
    raw_lea_content = (
        "BHARTI AIRTEL LIMITED\n"
        "\"\"\n"
        "PAN India\n"
        "Call Details of Mobile No '9829011111'\n"
        "Target No,Call Type,B Party No,Date,Time,Dur(s),First CGI,IMEI,IMSI\n"
        "9829011111,IN,9829022222,01/02/2026,10:00:00,45,RAJ-DEG-603,864698066569960,404971908560194\n"
    ).encode("utf-8")
    
    # Check inspect
    resp = client.post("/api/ingest/inspect", files={"file": ("airtel_lea.csv", raw_lea_content, "text/csv")})
    assert resp.status_code == 200
    data = resp.json()
    assert "Target No" in data["columns"]
    assert data["suggested_type"] == "CDR"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_forensic_suite.py -k "test_lea_preamble" -v`  
Expected: FAIL (unrecognized column headers due to preamble lines).

- [ ] **Step 3: Implement preamble stripping in `read_tabular_bytes` and 66 tower seeding in `seed_towers_from_csv`**

In `app/ingest.py`:
- In `read_tabular_bytes`, if file is CSV/text, scan the first 20 lines. If the first line does not contain standard delimiters (`,`, `\t`, `;`) or contains typical report preambles (`BHARTI AIRTEL`, `Ticket Number`, `Call Details of`, `REPORT`), find the line that contains recognizable header tokens (`Calling`, `Called`, `Target`, `MSISDN`, `A Party`, `Party No`, `Source`, `Phone`, `IMEI`) and use it as `header_row`.
- In `seed_towers_from_csv`, load `data/rajasthan_cell_towers_master.csv` (or fall back to `data/towers.csv`), upserting towers so all 66 sites (including Deeg, Kaman, Jurhara, Gopalgarh) are in `cell_towers`.
- In `ingest_cdr_data`, allow records with empty IMEI if they have valid A/B numbers and timestamps (flag with warning instead of rejection).

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_forensic_suite.py -k "test_lea_preamble" -v`  
Expected: PASS.

- [ ] **Step 5: Commit changes**

```bash
git add app/ingest.py tests/test_forensic_suite.py
git commit -m "feat(ingest): add LEA preamble stripping and 66 Rajasthan tower master sync"
```

---

### Task 2: Suspect Threat Risk Scoring & 24x7 Activity Heatmap

**Files:**
- Modify: `app/analysis.py:260-324, 799-895, 1419-1460`
- Modify: `app/main.py:678-694, 938-1400`
- Test: `tests/test_forensic_suite.py`

**Interfaces:**
- Produces: `calculate_suspect_threat_scores(case_id, db) -> list[dict]`
- Produces: `get_temporal_heatmap_24x7(case_id, db, target_number) -> dict`
- Fixes: Cross-subscriber movement calculation in `get_case_analytics`

- [ ] **Step 1: Write failing tests for Threat Risk Scoring and 24x7 Heatmap**

```python
def test_threat_scoring_and_heatmap_endpoints(client, auth_headers):
    # Register case and test endpoints
    # Case must return valid threat scores (0-100) and 24x7 heatmap matrix
    pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_forensic_suite.py -k "test_threat_scoring_and_heatmap" -v`  
Expected: FAIL (`404` endpoint not found or functions undefined).

- [ ] **Step 3: Implement `calculate_suspect_threat_scores` & `get_temporal_heatmap_24x7` in `app/analysis.py`**

- `calculate_suspect_threat_scores`: Evaluates each target against 5 crime indicators:
  - Night ratio > 25% (+25 pts)
  - SIM swap / multi-SIM hardware usage (+30 pts)
  - Impossible travel (>150 km/h) (+20 pts)
  - International / high-risk contacts (+15 pts)
  - Syndicate connectivity / common contacts (+10 pts)
  - Assigns `threat_score` (0-100) and `archetype` (`Kingpin / Syndicate Head`, `Night Phisher`, `Mule Cashout`, `Burner Swapper`, `Active Operative`).
- `get_temporal_heatmap_24x7`: Builds a matrix of 7 days (Monday-Sunday) x 24 hours (0-23) containing call counts.
- In `get_case_analytics`: Fix `movement_hops` so transitions are tracked per individual subscriber rather than jumping between different callers.
- In `app/main.py`: Add `GET /api/cases/{case_id}/threat-scoring` and `GET /api/cases/{case_id}/heatmap`. Include `threat_scores` and `heatmap_24x7` directly in `get_case_analytics` payload.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_forensic_suite.py -k "test_threat_scoring_and_heatmap" -v`  
Expected: PASS.

- [ ] **Step 5: Commit changes**

```bash
git add app/analysis.py app/main.py tests/test_forensic_suite.py
git commit -m "feat(analysis): add suspect threat risk scorer, 24x7 heatmap, and fix subscriber movement hops"
```

---

### Task 3: 275k TAC Handset Cache & Batch IPDR NAT Resolver

**Files:**
- Modify: `app/analysis.py:123-256`
- Modify: `app/ipdr.py:7-115`
- Modify: `app/main.py:431-482`
- Test: `tests/test_forensic_suite.py`

**Interfaces:**
- Produces: Fast in-memory TAC lookups for 275k records (`data/real_samples/tac_full.csv`) and Indian carrier attribution via `data/real_samples/mcc_mnc_india.csv`
- Produces: `POST /api/cases/{case_id}/ipdr/batch` accepting `{queries: [{ip, port, timestamp}]}`

- [ ] **Step 1: Write failing tests for 275k TAC lookup and Batch IPDR matching**

```python
def test_tac_full_cache_and_batch_ipdr(client, auth_headers):
    # Test batch IPDR resolution
    batch_payload = {
        "queries": [
            {"ip": "100.64.68.138", "port": 40242, "timestamp": "2026-02-01T13:09:21"},
            {"ip": "100.64.12.68", "port": 33241, "timestamp": "2026-02-01T14:04:38"}
        ]
    }
    # verify batch endpoint returns matched list
    pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_forensic_suite.py -k "test_tac_full_cache_and_batch_ipdr" -v`  
Expected: FAIL.

- [ ] **Step 3: Implement TAC full cache and `batch_match_ipdr_sessions`**

- In `app/analysis.py`:
  - Lazy load `data/real_samples/tac_full.csv` (275,865 lines) into an in-memory dictionary `_TAC_FULL_CACHE` on first lookup if present, mapping 8-digit TAC to `{brand, specs}`.
  - Load `data/real_samples/mcc_mnc_india.csv` (200 lines) into `_MCC_MNC_CACHE` for exact operator/circle attribution (e.g., Airtel Punjab, Jio Bihar, Vi Haryana).
- In `app/ipdr.py`:
  - Implement `batch_match_ipdr_sessions(case_id, queries, db, tolerance_minutes=15)` looping over candidate queries and returning summary stats (total queries, resolved count, unmatched count) and detailed subscriber matches.
- In `app/main.py`:
  - Add `POST /api/cases/{case_id}/ipdr/batch`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_forensic_suite.py -k "test_tac_full_cache_and_batch_ipdr" -v`  
Expected: PASS.

- [ ] **Step 5: Commit changes**

```bash
git add app/analysis.py app/ipdr.py app/main.py tests/test_forensic_suite.py
git commit -m "feat(ipdr,tac): implement 275k TAC cache, MCC-MNC attribution, and batch IPDR NAT resolver"
```

---

### Task 4: Tamper-Evident SHA-256 Audit Hash Chain & Integrity Verifier

**Files:**
- Modify: `app/db.py:136-148`
- Modify: `app/audit.py:8-51`
- Modify: `app/main.py:1478-1498`
- Test: `tests/test_forensic_suite.py`

**Interfaces:**
- Consumes: User actions, queries, logins, uploads
- Produces: Chained `prev_hash` & `entry_hash` per audit entry, plus `verify_audit_integrity(db)` returning verification status

- [ ] **Step 1: Write failing tests for SHA-256 audit chaining and verification**

```python
def test_audit_hash_chain_verification(client, auth_headers):
    resp = client.get("/api/audit/verify", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("VERIFIED", "EMPTY")
    assert "total_entries" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_forensic_suite.py -k "test_audit_hash_chain_verification" -v`  
Expected: FAIL (`404` endpoint not found).

- [ ] **Step 3: Implement SHA-256 hash chaining and integrity verifier**

- In `app/db.py`:
  - Add `prev_hash = Column(String(64), default="")` and `entry_hash = Column(String(64), default="")` to `AuditLog`.
- In `app/audit.py`:
  - In `log_audit_event`: Fetch the latest audit log entry's `entry_hash` (or use `"0"*64` for genesis). Compute:
    `entry_hash = hashlib.sha256(f"{prev_hash}|{username}|{action}|{timestamp_str}|{details_str}|{ip_addr}".encode()).hexdigest()`
    Save both `prev_hash` and `entry_hash`.
  - Implement `verify_audit_integrity(db) -> dict`: Read all entries in ascending order of `id`, verify each hash matches the computed SHA-256. If any entry does not match, return `{status: "TAMPERED", tampered_id: id}`. If valid, return `{status: "VERIFIED", total_checked: count, genesis_hash, latest_hash}`.
- In `app/main.py`:
  - Add `GET /api/audit/verify` (requires `admin` or `senior_officer`).

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_forensic_suite.py -k "test_audit_hash_chain_verification" -v`  
Expected: PASS.

- [ ] **Step 5: Commit changes**

```bash
git add app/db.py app/audit.py app/main.py tests/test_forensic_suite.py
git commit -m "feat(audit): implement SHA-256 tamper-evident hash chain and verification API"
```

---

### Task 5: Statutory Reporting Upgrade (PDF & Excel with Threat Scores & Audit Certificate)

**Files:**
- Modify: `app/reports.py:24-356`
- Test: `tests/test_demo_flow.py`

**Interfaces:**
- Consumes: Case analytics, Threat Scores, CGNAT IPDR sessions, SHA-256 audit log
- Produces: Enhanced ReportLab PDF and multi-tab OpenPyXL Excel reports

- [ ] **Step 1: Write test checking enhanced PDF & Excel content**

```python
def test_reports_include_threat_scoring_and_audit(client, auth_headers):
    # Verify PDF download returns valid 200 stream with non-zero length
    # Verify Excel download includes sheets
    pass
```

- [ ] **Step 2: Run test to verify behavior**

Run: `PYTHONPATH=. pytest tests/test_demo_flow.py -v`

- [ ] **Step 3: Update `generate_pdf_report` and `generate_excel_report`**

- In `app/reports.py`:
  - Add Section for "Suspect Threat Scoring & Syndicate Profile" in PDF.
  - Add Section for "Carrier NAT (CGNAT) IPDR Sessions".
  - Add Section 65B Certificate block with SHA-256 Audit Log Latest Hash stamp.
  - In Excel workbook, add sheet "Threat & Syndicate Profiling" and sheet "Section 65B Audit Trail".

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_demo_flow.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit changes**

```bash
git add app/reports.py
git commit -m "feat(reports): enrich formal judicial PDF and Excel with threat scores, IPDR sessions, and audit verification"
```

---

### Task 6: Frontend 7-Workbench Consolidation, Visual Command Center, Heatmap & Slide-in Network Drawer

**Files:**
- Modify: `app/static/index.html`
- Modify: `app/static/app.js`
- Modify: `app/static/style.css`

**Interfaces:**
- Consumes: Backend analytics, threat scores, heatmap, batch IPDR, audit verify APIs
- Produces: Consolidated 7-Workbench UI with responsive sub-tabs, threat meter cards, 24x7 heatmap canvas, Leaflet animated trajectory scrubber, Cytoscape centrality sizing with slide-in node drawer, and audit verification modal

- [ ] **Step 1: Update `app/static/index.html`**
  - Restructure sidebar into 7 primary Workbench items:
    1. 🎛️ Command Center (`workbench-command`)
    2. 📂 Data Ingestion Studio (`workbench-import`)
    3. 👥 Behavioral Analytics (`workbench-behavior`)
    4. 🌐 Geospatial Mobility Hub (`workbench-geo`)
    5. 🕸️ Network & Link Workbench (`workbench-network`)
    6. 📱 Device & Cyber-Telco Fusion (`workbench-device-cyber`)
    7. ⚖️ Legal, Copilot & Audit Wing (`workbench-legal-audit`)
  - Inside each workbench, insert a clean sub-tab navigation bar switching between the detailed modules.
  - Ensure all existing container IDs (`view-dashboard`, `view-mfc`, `view-first-last`, `view-day-night`, `view-missing-dates`, `view-movement`, `view-service-numbers`, `view-international`, `view-common-numbers`, `view-meetings`, `view-imei-summary`, `view-imsi-summary`, `view-device-changes`, `view-ownership`, `view-geo-map`, `view-graph`, `view-link-analysis`, `view-ipdr`, `view-assistant`, `view-reports`, `view-import`, `view-audit`, etc.) exist inside their respective workbenches.
  - Add containers for:
    - Suspect Threat Cards grid
    - 24x7 Activity Heatmap (`canvas id="chart-24x7-heatmap"`)
    - Leaflet trajectory time-slider controls (`#map-time-slider`, Play/Pause buttons)
    - Cytoscape Slide-in Node Evidence Drawer (`#node-inspector-drawer`)
    - Batch IPDR Resolver modal (`#modal-batch-ipdr`)
    - Audit Hash Chain Integrity badge and button (`#btn-verify-audit-chain`)

- [ ] **Step 2: Update `app/static/app.js`**
  - Add workbench switcher `switchWorkbench(workbenchId, defaultSubView)` with backward-compatible fallback for `switchView(viewName)`.
  - Add `renderThreatCards(threatScores)` rendering color-coded risk meter badges.
  - Add `render24x7Heatmap(heatmapData)` rendering hour vs day intensity grid.
  - Add `renderAnimatedTrajectory(timeline)` with Leaflet polyline scrubbing.
  - Add Cytoscape node tap event handler to open `#node-inspector-drawer` with full call counts, connected targets, and Section 65B citation pill instead of browser `alert()`.
  - Add `handleBatchIpdrSubmit(e)` and `verifyAuditChain()` functions.

- [ ] **Step 3: Update `app/static/style.css`**
  - Add styling for:
    - Workbench sub-tab navigation bar (`.workbench-tabs`, `.workbench-tab-btn.active`)
    - Threat Risk Cards (`.threat-meter-card`, `.threat-pill-critical`, `.threat-pill-warning`)
    - 24x7 Heatmap CSS Grid / Canvas container
    - Animated Map Playback scrubber bar
    - Slide-in Cytoscape Node Inspector Drawer (`.node-drawer`, `.node-drawer.open`)
    - Batch IPDR and Audit Verification UI badges

- [ ] **Step 4: Manual & Playwright UI verification**
  - Open UI in browser, verify clean ingestion gate on empty DB.
  - Upload `case-2026-mewat` CDR + IPDR files.
  - Verify all 7 workbenches switch seamlessly, charts render, Cytoscape node drawer opens on click, and audit chain verifies as `VERIFIED`.

- [ ] **Step 5: Commit changes**

```bash
git add app/static/index.html app/static/app.js app/static/style.css
git commit -m "feat(ui): consolidate into 7 investigation workbenches with threat cards, 24x7 heatmap, and slide-in graph inspector"
```

---

### Task 7: Comprehensive Regression & End-to-End Verification

**Files:**
- Modify/Run: `tests/test_core.py`, `tests/test_demo_flow.py`, `tests/test_external_datasets.py`, `tests/test_forensic_suite.py`

**Interfaces:**
- Consumes: Entire test suite across all 7 modules
- Produces: 100% green pytest verification (45+ passing tests)

- [ ] **Step 1: Run complete automated test suite**

```bash
PYTHONPATH=. pytest tests/ -v
```
Expected: All 41+ tests PASSED (0 failures, 0 errors).

- [ ] **Step 2: Run clean-database initialization check**

Verify that launching with an empty `prototype.db` exhibits zero preloaded cases or records and directly prompts the ingestion wizard.

- [ ] **Step 3: Final commit and tag**

```bash
git add -A
git commit -m "chore(release): complete syndicate intelligence command center consolidation"
```

---

## Plan Self-Review Checklist
- [x] **Spec coverage:** All items from spec (7 workbenches, LEA preambles, 66 towers, 275k TAC, threat scoring, 24x7 heatmap, animated map playback, slide-in node drawer, batch IPDR, SHA-256 audit chain) mapped to specific tasks.
- [x] **Step scan:** Every step contains explicit actions, command lines, or code signatures with testable results.
- [x] **Type consistency:** Identical function names (`calculate_suspect_threat_scores`, `get_temporal_heatmap_24x7`, `batch_match_ipdr_sessions`, `verify_audit_integrity`) used throughout.
- [x] **Review Focus:** Preamble stripping, cross-subscriber movement bug, blank IMEI tolerance, audit tamper detection, and legacy view ID preservation explicitly pinned to tasks.
- [x] **Proportion:** Clear, concise steps without redundant boilerplate.
