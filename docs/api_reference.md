# REST API Reference Specification

## API Architecture Overview

The **Rajasthan Police CDR/IPDR Analysis Tool** provides a RESTful API built on **FastAPI**. All analytical operations, ingestions, graph generations, and AI assistant dialogues are accessible through documented JSON endpoints.

- **Base URL**: `http://127.0.0.1:8000`
- **Interactive Documentation**: Swagger UI is available at `/docs` and ReDoc at `/redoc`.
- **Default Authentication**: Bearer JWT tokens or role header (`X-Demo-Role`).

---

## 1. Authentication & User Profile

### `POST /api/auth/login`
Authenticates an officer and initializes an audit session.
- **Request Body**:
  ```json
  { "username": "io_sharma", "password": "IO@RajPolice2026" }
  ```
- **Response `200 OK`**:
  ```json
  {
    "access_token": "jwt_token_string",
    "token_type": "bearer",
    "user": {
      "username": "io_sharma",
      "full_name": "Inspector Rajesh Sharma",
      "role": "investigating_officer",
      "badge_number": "RJ-IO-4122"
    }
  }
  ```

### `GET /api/auth/me`
Retrieves the currently authenticated user identity and effective permissions.

---

## 2. Case Management & Demo Loader

### `GET /api/cases`
Lists all active and archived cases in the system.

### `POST /api/cases`
Creates a new police case file.
- **Request Body**:
  ```json
  { "id": "CASE-RAJ-2026-0042", "title": "Operation Maru-Drishti", "description": "Cyber crime syndicate analysis" }
  ```

### `GET /api/cases/{case_id}`
Returns case details, suspect phone numbers, summary counts of CDR/IPDR records, and batch ingestions.

### `POST /api/cases/demo`
One-click loader for Hackathon evaluation. Initializes case `CASE-RAJ-2026-0042`, seeds cell towers, and ingests 1,998 CDR records across two operator formats and 312 IPDR sessions.

---

## 3. Ingestion & Column Mappings

### `GET /api/mappings`
Returns all registered operator JSON mapping configurations (`operator_a`, `operator_b`, `ipdr_operator_a`).

### `POST /api/mappings`
Registers or updates a custom operator column mapping schema.

### `POST /api/cases/{case_id}/upload`
Uploads raw CSV files for processing.
- **Form Data**:
  - `file`: Multipart binary CSV file.
  - `file_type`: `"CDR"` or `"IPDR"`.
  - `mapping_name`: Mapping identifier (e.g., `"operator_a"`).
- **Response**: Ingestion status, total rows, valid rows, and rejected rows count.

### `GET /api/cases/{case_id}/batches`
Returns history of all uploaded batches for the case with validation summaries.

---

## 4. Forensic Telecommunications Analytics

### `GET /api/cases/{case_id}/patterns`
Computes communication patterns for a specific suspect.
- **Query Parameters**: `suspect_number` (string)
- **Response**: Total calls, total duration, in/out ratio, first/last call, and top contacts.

### `GET /api/cases/{case_id}/common`
Computes common contacts between two or more targets.
- **Query Parameters**: `suspects` (comma-separated string, e.g., `9829022222,9829033333`)
- **Response**: Array of shared numbers, call count per suspect, and direct call indicators.

### `GET /api/cases/{case_id}/towers/timeline`
Retrieves timestamped cell tower registrations and GPS coordinates.
- **Query Parameters**: `suspect_number` (string)

### `GET /api/cases/{case_id}/meetings`
Runs the spatiotemporal co-location algorithm.
- **Query Parameters**: `window_minutes` (integer, default `30`)
- **Response**: Confirmed meetings, location addresses, timestamps, participants, and evidence row IDs.

### `GET /api/cases/{case_id}/device-changes`
Detects hardware and subscriber anomalies.
- **Response**: Multi-SIM per IMEI and multi-IMEI per SIM tracking arrays.

### `GET /api/cases/{case_id}/network`
Generates Cytoscape-formatted graph elements.
- **Query Parameters**: `min_calls` (integer, default `1`)
- **Response**: `{ "nodes": [...], "edges": [...] }`

---

## 5. Advanced Forensic Suite

### `GET /api/dashboard/metrics`
Returns executive KPI statistics across the case (total calls, unique callers, active towers, total duration).

### `GET /api/tac/{imei}`
Returns handset intelligence (brand, commercial model, generation) for an 8-digit TAC.

### `GET /api/cases/{case_id}/raw-cdr`
Paginated raw CDR viewer supporting dynamic filters (`search`, `start_date`, `end_date`, `call_type`, `limit`, `offset`).

### `GET /api/cases/{case_id}/mfc`
Most Frequent Callers breakdown with cumulative talk time.

### `GET /api/cases/{case_id}/day-night`
Daytime (06:00-22:00) vs. Nocturnal (22:00-06:00) calling volume and percentage breakdown.

### `GET /api/cases/{case_id}/first-last`
Earliest and latest recorded call events for onboarding and cutoff profiling.

### `GET /api/cases/{case_id}/missing-dates`
Detects communication blackouts and dormancy gaps in target activity.

### `GET /api/cases/{case_id}/movement`
Analyzes inter-district tower transitions and physical movement velocity across Rajasthan.

### `GET /api/cases/{case_id}/service-numbers`
Filters calls to bank OTP lines, helpline 1930, 112 ERSS, and customer care.

### `GET /api/cases/{case_id}/international`
Isolates cross-border communications with international dialing prefixes.

### `GET /api/cases/{case_id}/imei-summary`
Lists all physical handset IMEIs registered by a given subscriber number.

### `GET /api/cases/{case_id}/imsi-summary`
Lists all SIM card IMSIs utilized by a given subscriber number.

### `GET /api/search`
Global forensic search engine scanning callers, receivers, IMEIs, IMSIs, and towers.

### `GET /api/cases/{case_id}/record/{record_type}/{source_row}`
Retrieves raw data for a specific source row to fulfill Section 65B judicial verification modals.

---

## 6. Carrier-Grade NAT (CGNAT) IPDR Resolver

### `GET /api/cases/{case_id}/ipdr/match`
De-anonymizes public IP sessions.
- **Query Parameters**:
  - `ip`: Public IPv4 address (e.g., `103.211.54.12`)
  - `port`: Public TCP/UDP port (e.g., `44321`)
  - `timestamp`: Timestamp string (e.g., `2026-11-20 18:25:10`)
  - `tolerance_seconds`: Time window tolerance (default `300`)
- **Response**: Matched subscriber MSISDN, private IP, session duration, and application hint.

### `GET /api/cases/{case_id}/ipdr/subscriber`
Summarizes all Internet data activity for a target subscriber.

---

## 7. AI Investigation Assistant & Endorsements

### `POST /api/cases/{case_id}/assistant`
Submits a natural language query in English, Hindi, or Hinglish.
- **Request Body**: `{ "query": "S3 ne kab SIM badla?" }`
- **Response**: Synthesized answer, evidence row citations, suggested follow-ups, and observation ID.

### `GET /api/cases/{case_id}/observations`
Lists all AI-generated observations with current verification statuses.

### `POST /api/cases/{case_id}/observations/{obs_id}/verify`
Supervisory officer endpoint to endorse or reject an AI observation.
- **Request Body**: `{ "action": "verify", "notes": "Verified against raw CDR rows." }`

---

## 8. Judicial Reports & Audit Logs

### `GET /api/cases/{case_id}/report`
Generates and downloads formal case reports.
- **Query Parameters**: `format` (`"pdf"` or `"excel"`)
- **Response**: Streaming binary attachment (`application/pdf` or `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`).

### `GET /api/audit`
Retrieves the immutable, tamper-evident audit trail records.
