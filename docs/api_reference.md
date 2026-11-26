# Complete REST API Reference (50 API Endpoints)

The Rajasthan Police Cyber Forensic Command Center exposes **50 `/api/` RESTful endpoints** (plus `/` SPA entrypoint and `/favicon.ico`) built with **FastAPI**, secured via **JWT Bearer Tokens**, and logged to the SHA-256 hash-chained **AuditLog**.

- **Interactive Swagger UI:** `http://127.0.0.1:8000/docs`
- **Authorization Header:** `Authorization: Bearer <access_token>`

> **Note on Dynamic Ingestion-First Workflow:** Legacy static demo seeders (e.g., `POST /api/cases/demo`) have been removed. All analytics endpoints compute strictly against case data ingested via `POST /api/cases` and `POST /api/cases/{case_id}/upload`.

---

## 1. Authentication & Officer Session (`2 Endpoints`)

| Method | Endpoint | Access Roles | Payload / Parameters | Description |
| :--- | :--- | :--- | :--- | :--- |
| **`POST`** | `/api/auth/login` | Public | JSON `LoginRequest`: `{ username, password }` | Authenticates credentials (`bcrypt`), logs `LOGIN` or `LOGIN_FAILED`, and returns `{ access_token, token_type, user: { username, role, full_name, badge_number } }` |
| **`GET`** | `/api/auth/me` | Any Authenticated | Bearer Token | Returns active authenticated officer profile |

---

## 2. FIR Case Management (`4 Endpoints`)

| Method | Endpoint | Access Roles | Payload / Parameters | Description |
| :--- | :--- | :--- | :--- | :--- |
| **`GET`** | `/api/cases` | `investigating_officer`, `senior_officer`, `admin` | — | Lists all registered FIR cases sorted newest-first with CDR/IPDR/observation counts |
| **`POST`** | `/api/cases` | `investigating_officer`, `senior_officer`, `admin` | JSON `CreateCaseRequest`: `{ id, title, description, case_type, police_station, investigator_name, status }` | Registers a new FIR case, embeds brief metadata JSON, and logs `CASE_CREATED` |
| **`GET`** | `/api/cases/{case_id}` | `investigating_officer`, `senior_officer`, `admin` | Path: `case_id` | Returns complete FIR dossier, dynamic suspect list, record metrics, and upload batch history |
| **`PATCH`** | `/api/cases/{case_id}/status` | `investigating_officer`, `senior_officer`, `admin` | JSON `UpdateCaseStatusRequest`: `{ status }` | Updates operational status (e.g. `ACTIVE`, `UNDER REVIEW`, `CLOSED`) and logs `CASE_STATUS_UPDATED` |

---

## 3. Data Ingestion & Header Mappings (`5 Endpoints`)

| Method | Endpoint | Access Roles | Payload / Parameters | Description |
| :--- | :--- | :--- | :--- | :--- |
| **`GET`** | `/api/mappings` | Public | — | Lists all preset telecom operator schemas in `data/mappings/*.json` |
| **`POST`** | `/api/mappings` | `investigating_officer`, `senior_officer`, `admin` | Form: `mapping_id`, `config_json` | Saves or updates a reusable operator column mapping JSON |
| **`POST`** | `/api/ingest/inspect` | `investigating_officer`, `senior_officer`, `admin` | Multipart: `file` | Parses headers of `.csv`, `.tsv`, `.txt`, `.xlsx`, or `.xls`, strips LEA preambles, and proposes auto-detected field mappings + sample preview rows |
| **`POST`** | `/api/cases/{case_id}/upload` | `investigating_officer`, `senior_officer` | Multipart: `file`, `file_type` (`CDR` \| `IPDR`), `mapping_name` (`auto` or preset), `custom_mapping_json` | Normalizes & persists records with `source_file:source_row`, auto-upserts BTS coordinates when present, and saves an `ImportBatch` summary |
| **`GET`** | `/api/cases/{case_id}/batches` | `investigating_officer`, `senior_officer`, `admin` | Path: `case_id` | Retrieves upload validation receipts and row-level rejection logs |

---

## 4. Dashboard, Suspect Workspace & Forensic Analytics (`18 Endpoints`)

| Method | Endpoint | Access Roles | Parameters | Description |
| :--- | :--- | :--- | :--- | :--- |
| **`GET`** | `/api/dashboard/metrics` | `IO`, `SP`, `Admin` | Query: `case_id` (optional) | Computes global or case-scoped Executive KPI cards, call/SMS distributions, and activity summaries |
| **`GET`** | `/api/cases/{case_id}/analytics` | `IO`, `SP`, `Admin` | Path: `case_id` | Master 28-module aggregator returning `suspects`, `threat_scores`, `heatmap_24x7`, `mfc`, `first_last`, `day_night`, `day_calls`, `night_calls`, `day_locations`, `night_locations`, `location_summary`, `location_intelligence`, `missing_dates`, `movement`, `cell_id_changes`, `location_changes`, `interactive_timeline`, `network_stats`, `service_numbers`, `international_numbers`, `imei_summary`, `imsi_summary`, `imei_patterns`, `imsi_patterns`, `notifications`, and `ownership` |
| **`GET`** | `/api/cases/{case_id}/suspect/{phone}/summary` | `IO`, `SP`, `Admin` | Path: `case_id`, `phone` | Returns 10 Suspect Workspace KPI cards, real ownership matches, operator percentages, and 100 recent CDR rows |
| **`GET`** | `/api/cases/{case_id}/threat-scoring` | `IO`, `SP`, `Admin` | Path: `case_id` | Computes `0–100` multi-factor Threat Score, risk tier, archetype, and risk factors per suspect |
| **`GET`** | `/api/cases/{case_id}/heatmap` | `IO`, `SP`, `Admin` | Query: `target_number` (optional) | Generates 7×24 temporal call-intensity matrix |
| **`GET`** | `/api/cases/{case_id}/raw-cdr` | `IO`, `SP`, `Admin` | Query: `search`, `call_type`, `page` (≥1), `limit` (1–500) | Paginated Section 65B raw CDR explorer with filter support |
| **`GET`** | `/api/cases/{case_id}/patterns` | `IO`, `SP` | Query: `number` | Call asymmetry, hourly peaks, and top contacts for one number |
| **`GET`** | `/api/cases/{case_id}/common` | `IO`, `SP` | Query: `numbers` (comma-separated) | Intersects contact sets across 2+ suspect MSISDNs |
| **`GET`** | `/api/cases/{case_id}/link-analysis` | `IO`, `SP`, `Admin` | Query: `num1`, `num2` | Direct link stats, common contacts, shared cell towers, and chronological interactions between two targets |
| **`GET`** | `/api/cases/{case_id}/mfc` | `IO`, `SP`, `Admin` | Query: `target_number` (optional), `top` (1–200) | Most Frequent Callers ranking |
| **`GET`** | `/api/cases/{case_id}/day-night` | `IO`, `SP`, `Admin` | Query: `target_number` (optional) | Day (`06:00–21:59`) vs. Night (`22:00–05:59`) call ratio & high-nocturnal peers |
| **`GET`** | `/api/cases/{case_id}/first-last` | `IO`, `SP`, `Admin` | Query: `target_number` (optional) | First and last communication timestamps per contact |
| **`GET`** | `/api/cases/{case_id}/missing-dates` | `IO`, `SP`, `Admin` | Query: `target_number` (optional) | Detects zero-activity dormancy days between first & last CDR event |
| **`GET`** | `/api/cases/{case_id}/service-numbers` | `IO`, `SP`, `Admin` | Path: `case_id` | Screens interactions against banking IVRs, 1930, 112, and carrier codes |
| **`GET`** | `/api/cases/{case_id}/international` | `IO`, `SP`, `Admin` | Path: `case_id` | Identifies cross-border `+` / `00` / ISD calls and high-risk corridors |
| **`GET`** | `/api/cases/{case_id}/imei-summary` | `IO`, `SP`, `Admin` | Path: `case_id` | IMEI device usage counts, linked numbers, and TAC model intelligence |
| **`GET`** | `/api/cases/{case_id}/imsi-summary` | `IO`, `SP`, `Admin` | Path: `case_id` | IMSI SIM identity counts, carrier MCC/MNC decoding, and IMEI bindings |
| **`GET`** | `/api/cases/{case_id}/device-changes` | `IO`, `SP` | Path: `case_id` | Flags `1 IMEI -> N SIMs` and `1 SIM -> N IMEIs` swapping behavior |

---

## 5. Geospatial Intelligence & Mobility (`5 Endpoints`)

| Method | Endpoint | Access Roles | Parameters | Description |
| :--- | :--- | :--- | :--- | :--- |
| **`GET`** | `/api/cases/{case_id}/towers/timeline` | `IO`, `SP` | Query: `number` | Chronological BTS tower hops for a suspect with CGI-aware lat/lon resolution |
| **`GET`** | `/api/cases/{case_id}/towers/sectors` | `IO`, `SP`, `Admin` | Query: `suspect` (optional) | Generates 65° tri-sector azimuth RF coverage polygons (`1.2 km` radius) for GIS mode 5 |
| **`GET`** | `/api/cases/{case_id}/movement` | `IO`, `SP`, `Admin` | Query: `target_number` (optional) | Sequential inter-tower movement trail with Haversine distance & speed calculation |
| **`GET`** | `/api/cases/{case_id}/meetings` | `IO`, `SP` | Query: `num1`, `num2`, `window` (default `30` mins) | Identifies physical BTS co-location meetings between two targets within time delta |
| **`GET`** | `/api/cases/{case_id}/velocity-anomalies` | `IO`, `SP`, `Admin` | Query: `suspect` (optional), `max_speed` (default `120.0` km/h) | Flags impossible non-flight terrestrial velocities indicating cloned SIMs |

---

## 6. Global Intelligence, TAC & Entity Lookup (`4 Endpoints`)

| Method | Endpoint | Access Roles | Parameters | Description |
| :--- | :--- | :--- | :--- | :--- |
| **`GET`** | `/api/tac/{imei}` | `IO`, `SP`, `Admin` | Path: `imei` | Resolves 8-digit IMEI TAC prefix to OEM, commercial model, and cellular band |
| **`GET`** | `/api/search` | `IO`, `SP`, `Admin` | Query: `q` (min len 1), `case_id` (optional) | Cross-case or scoped full-text search via `global_search` |
| **`GET`** | `/api/cases/{case_id}/search` | `IO`, `SP`, `Admin` | Query: `q` (min len 1) | Case-local rapid search returning up to 20 CDRs, 20 IPDRs, and 10 matching BTS towers |
| **`GET`** | `/api/lookup` | `IO`, `SP`, `Admin` | Query: `q` (min len 2), `case_id` (optional) | Detailed entity dossier lookup via `lookup_entity_profile` |

---

## 7. Carrier-Grade NAT (CGNAT) IPDR Resolution (`4 Endpoints`)

| Method | Endpoint | Access Roles | Payload / Parameters | Description |
| :--- | :--- | :--- | :--- | :--- |
| **`GET`** | `/api/cases/{case_id}/ipdr/match` | `IO`, `SP` | Query: `ip`, `port`, `timestamp` | Triple-key subscriber attribution with ±15 min window tolerance and fallback IP matches |
| **`GET`** | `/api/cases/{case_id}/ipdr/subscriber` | `IO`, `SP` | Query: `subscriber` | Summarizes IPDR session volume, bytes transferred, and app hint breakdown |
| **`GET`** | `/api/cases/{case_id}/ipdr/sample` | `IO`, `SP`, `Admin` | Path: `case_id` | Returns first real uploaded IPDR session tuple in DB for one-click verification |
| **`POST`** | `/api/cases/{case_id}/ipdr/batch` | `IO`, `SP` | JSON `{ queries: [{ ip, port, timestamp, query_id }], tolerance_minutes }` | Bulk CGNAT resolution for 1930 Cyber Helpline & bank fraud complaint batches |

---

## 8. Network Graph, AI Copilot, Evidence, Reports & Audit (`8 Endpoints`)

| Method | Endpoint | Access Roles | Payload / Parameters | Description |
| :--- | :--- | :--- | :--- | :--- |
| **`GET`** | `/api/cases/{case_id}/network` | `IO`, `SP` | Query: `min_calls` (default `1`) | Generates Cytoscape.js node/edge elements for 4-Quad syndicate topology |
| **`POST`** | `/api/cases/{case_id}/assistant` | `IO`, `SP` | JSON `AIQueryRequest`: `{ query }` | Invokes LangGraph bilingual AI copilot & saves `AIObservation` (`pending_verification`) |
| **`GET`** | `/api/cases/{case_id}/observations` | `IO`, `SP`, `Admin` | Path: `case_id` | Lists persisted AI observations alongside SP verification metadata |
| **`POST`** | `/api/cases/{case_id}/observations/{obs_id}/verify` | **`senior_officer` only** | JSON `ObservationVerifyRequest`: `{ action: "verify" \| "reject", notes }` | Certifies or rejects an AI finding prior to statutory court inclusion |
| **`GET`** | `/api/cases/{case_id}/record/{record_type}/{source_row}` | `IO`, `SP` | Path: `record_type` (`CDR` \| `IPDR`), `source_row`; Query: `source_file` | Retrieves exact normalized & raw CSV row for Section 65B drawer verification |
| **`GET`** | `/api/cases/{case_id}/report` | `IO`, `SP` | Query: `format` (`pdf` \| `xlsx` \| `kml` \| `kmz`), `suspect` (optional) | Generates court PDF, 6-sheet Excel workbook, or Google Earth KML/KMZ stream |
| **`GET`** | `/api/audit` | `senior_officer`, `admin` | Query: `limit` (default `100`), `action` (optional) | Reads hash-chained audit logs (note: Investigating Officers receive `403`) |
| **`GET`** | `/api/audit/verify` | `IO`, `SP`, `Admin` | — | Re-computes SHA-256 chain from genesis record to verify ledger tamper resistance |

*Additionally, `GET /` serves the Command Center SPA and `GET /favicon.ico` returns HTTP `204`.*
