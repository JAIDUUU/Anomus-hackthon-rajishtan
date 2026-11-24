import os
import re
import json
from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_

from langgraph.graph import StateGraph, END
from app.db import CDRRecord, IPDRRecord, Case, AIObservation
from app.analysis import (
    analyze_communication_patterns,
    find_common_numbers,
    get_location_timeline,
    detect_meetings,
    detect_imei_sim_changes,
    get_suspect_numbers_for_case,
    get_ordered_suspects_for_case
)
from app.ipdr import match_ipdr_session


class AgentState(TypedDict):
    query: str
    case_id: str
    user_role: str
    intent: str
    tool_name: str
    tool_args: Dict[str, Any]
    tool_result: Dict[str, Any]
    is_supported: bool
    unsupported_reason: str
    answer: str
    evidence: List[Dict[str, Any]]
    confidence_note: str
    status: str
    follow_up_questions: List[str]
    suggested_filters: Dict[str, Any]


def extract_phone_numbers(text: str) -> List[str]:
    # Match 10-digit Indian numbers or numbers starting with +91
    raw_matches = re.findall(r"(?:\+91|0)?[6-9]\d{9}", text)
    cleaned = []
    for m in raw_matches:
        c = m.replace("+91", "").lstrip("0")
        if len(c) == 10 and c not in cleaned:
            cleaned.append(c)
    return cleaned


def extract_ip_and_port(text: str) -> tuple[Optional[str], Optional[int]]:
    ip_match = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text)
    port_match = re.search(r":(\d{2,5})\b|\bport\s*(\d{2,5})\b", text, re.IGNORECASE)

    ip = ip_match.group(0) if ip_match else None
    port = None
    if port_match:
        port = int(port_match.group(1) or port_match.group(2))
    return ip, port


def detect_intent_rule_based(query: str, suspect_numbers: list[str]) -> tuple[str, str, dict]:
    q = query.lower()

    # 1. Guardrail checks for unsupported capabilities
    unsupported_keywords = [
        "recording", "sunao", "kya bola", "kya baat hui", "call content",
        "audio", "transcript", "intercept live", "real-time location",
        "live location", "call sunna", "voice message", "whatsapp message content"
    ]
    for uk in unsupported_keywords:
        if uk in q:
            return "unsupported", "guardrail_unsupported", {
                "reason": "Telecommunications metadata (CDR / IPDR) records only transactional session parameters (timestamp, cell ID, caller/callee, IP address, duration). It does not capture voice audio, message payloads, or live interception per Section 5(2) Indian Telegraph Act."
            }

    extracted_nums = extract_phone_numbers(query)
    ip, port = extract_ip_and_port(query)

    # 2. IPDR Lookup
    if ip or "ipdr" in q or "ip address" in q or "public ip" in q:
        return "ipdr_lookup", "match_ipdr_session", {
            "ip": ip or "",
            "port": port or 0,
            "timestamp": ""
        }

    # 3. Meeting detection / same tower same time
    if any(k in q for k in ["meeting", "mili thi", "mile the", "kahan mile", "same tower", "same time", "ikathhe", "together", "encounter", "rendezvous"]):
        target_nums = extracted_nums if len(extracted_nums) >= 2 else suspect_numbers[:2]
        return "meeting_detection", "detect_meetings", {
            "num1": target_nums[0] if len(target_nums) > 0 else "",
            "num2": target_nums[1] if len(target_nums) > 1 else ""
        }

    # 4. SIM swap / IMEI change detection
    if any(k in q for k in ["sim swap", "sim change", "imei change", "imei reuse", "handset change", "device change", "sim badla", "handset badla"]):
        return "imei_sim_changes", "detect_imei_sim_changes", {}

    # 5. Common numbers
    if any(k in q for k in ["common", "mutual", "common number", "shared contact", "dono se baat", "dono ke number", "dono number"]):
        target_nums = extracted_nums if len(extracted_nums) >= 2 else suspect_numbers[:2]
        return "common_numbers", "find_common_numbers", {"numbers": target_nums}

    # 6. Night activity
    if any(k in q for k in ["night", "raat", "late night", "22:00", "der raat", "odd hours", "night time"]):
        target = extracted_nums[0] if extracted_nums else (suspect_numbers[-1] if suspect_numbers else "")
        return "night_activity", "analyze_communication_patterns", {"number": target}

    # 7. Tower locations / movement
    if any(k in q for k in ["tower", "location", "movement", "kahan tha", "kahan gaya", "route", "timeline", "path", "map"]):
        target = extracted_nums[0] if extracted_nums else (suspect_numbers[0] if suspect_numbers else "")
        return "location_timeline", "get_location_timeline", {"number": target}

    # 8. Frequent / Top contacts
    if any(k in q for k in ["frequent", "top contact", "sabse jyada", "sabse zyada", "adhik call", "most called", "who did he call"]):
        target = extracted_nums[0] if extracted_nums else (suspect_numbers[0] if suspect_numbers else "")
        return "frequent_contacts", "analyze_communication_patterns", {"number": target}

    # 9. Explain chart / graph
    if any(k in q for k in ["explain", "chart", "graph", "overview", "samjhao"]):
        return "explain_view", "case_overview", {}

    # Default: if any number found, run communication pattern analysis
    if extracted_nums:
        return "frequent_contacts", "analyze_communication_patterns", {"number": extracted_nums[0]}

    # General suspect overview
    return "frequent_contacts", "analyze_communication_patterns", {
        "number": suspect_numbers[0] if suspect_numbers else ""
    }


def intent_node(state: AgentState, db: Session) -> AgentState:
    query = state["query"]
    case_id = state["case_id"]

    ordered = get_ordered_suspects_for_case(case_id, db)
    suspect_set = [s["phone"] for s in ordered if s.get("phone")]

    llm_key = os.getenv("LLM_API_KEY")
    # If no LLM key or swappable fallback requested:
    intent, tool_name, tool_args = detect_intent_rule_based(query, suspect_set)

    # Dynamically resolve missing IPDR args from active case's uploaded IPDR records
    if intent == "ipdr_lookup" and not tool_args.get("ip"):
        sample = db.query(IPDRRecord).filter(IPDRRecord.case_id == case_id).first()
        if sample:
            tool_args["ip"] = sample.source_ip
            tool_args["port"] = sample.source_port
            tool_args["timestamp"] = sample.session_start
    elif intent == "ipdr_lookup" and not tool_args.get("timestamp"):
        sample = db.query(IPDRRecord).filter(
            IPDRRecord.case_id == case_id,
            IPDRRecord.source_ip == tool_args["ip"]
        ).first()
        if sample:
            tool_args["timestamp"] = sample.session_start
            if not tool_args.get("port"):
                tool_args["port"] = sample.source_port

    state["intent"] = intent
    state["tool_name"] = tool_name
    state["tool_args"] = tool_args
    return state


def guardrail_node(state: AgentState) -> AgentState:
    if state["intent"] == "unsupported":
        state["is_supported"] = False
        state["unsupported_reason"] = state["tool_args"].get("reason", "Query exceeds telecom metadata boundaries.")
        state["answer"] = (
            f"**Information Not Available in Uploaded Data**\n\n"
            f"{state['unsupported_reason']}\n\n"
            f"> *Note for Investigating Officer:* CDR and IPDR data strictly contain communication metadata, cell tower identifiers, and IP connection logs. Contents of spoken conversations or messaging text cannot be retrieved from CDR records."
        )
        state["evidence"] = []
        state["confidence_note"] = "Guardrail check triggered: request exceeds legal telecom metadata capability."
        state["status"] = "pending_verification"
        state["follow_up_questions"] = [
            "What were the top contacts for this number instead?",
            "What tower locations was the suspect active on?",
            "Were there common numbers between the suspects?"
        ]
        state["suggested_filters"] = {"data_type": "CDR_METADATA_ONLY"}
    else:
        state["is_supported"] = True
    return state


def tool_execution_node(state: AgentState, db: Session) -> AgentState:
    if not state.get("is_supported", True):
        return state

    tool_name = state["tool_name"]
    args = state["tool_args"]
    case_id = state["case_id"]

    try:
        if tool_name == "analyze_communication_patterns":
            res = analyze_communication_patterns(args["number"], case_id, db)
            state["tool_result"] = res
        elif tool_name == "find_common_numbers":
            res = find_common_numbers(args.get("numbers", []), case_id, db)
            state["tool_result"] = res
        elif tool_name == "get_location_timeline":
            res = get_location_timeline(args["number"], case_id, db)
            state["tool_result"] = res
        elif tool_name == "detect_meetings":
            res = detect_meetings(args["num1"], args["num2"], case_id, db)
            state["tool_result"] = {"meetings": res}
        elif tool_name == "detect_imei_sim_changes":
            res = detect_imei_sim_changes(case_id, db)
            state["tool_result"] = res
        elif tool_name == "match_ipdr_session":
            res = match_ipdr_session(case_id, args["ip"], args["port"], args["timestamp"], db)
            state["tool_result"] = res
        elif tool_name == "case_overview":
            c = db.query(Case).filter(Case.id == case_id).first()
            state["tool_result"] = {"overview": c.title if c else "Active Case"}
        else:
            state["tool_result"] = {}
    except Exception as e:
        state["tool_result"] = {"error": str(e)}

    return state


def evidence_and_answer_node(state: AgentState) -> AgentState:
    if not state.get("is_supported", True):
        return state

    tool_name = state["tool_name"]
    res = state.get("tool_result", {})
    intent = state.get("intent")

    evidence = []
    follow_ups = []
    filters = {}
    answer_text = ""

    if intent == "frequent_contacts":
        num = res.get("target_number", "Unknown")
        top = res.get("top_contacts", [])
        total = res.get("total_calls", 0)
        answer_text = f"**Communication Analysis for {num}**\n\n"
        answer_text += f"- **Total Transactions:** {total} calls/SMS\n"
        answer_text += f"- **In/Out Ratio:** {res.get('in_out_ratio')} (Incoming: {res.get('incoming_calls')}, Outgoing: {res.get('outgoing_calls')})\n"
        answer_text += f"- **First Seen:** {res.get('first_communication')}\n"
        answer_text += f"- **Last Seen:** {res.get('last_communication')}\n\n"
        answer_text += "**Top Frequent Contacts:**\n"

        for idx, c in enumerate(top[:5], 1):
            answer_text += f"{idx}. **{c['number']}** - {c['call_count']} calls ({c['total_duration_sec']} sec total)\n"
            for ev in c.get("sample_evidence", [])[:2]:
                evidence.append(ev)

        follow_ups = [
            f"Show tower locations for {num}",
            f"Check night activity for {num}",
            f"Are any of these contacts shared with other suspects?"
        ]
        filters = {"target_number": num, "sort_by": "call_count"}

    elif intent == "night_activity":
        num = res.get("target_number", "Unknown")
        night = res.get("night_activity", {})
        cnt = night.get("count", 0)
        pct = night.get("percentage", 0.0)
        answer_text = f"**Night-Time Activity Analysis (22:00 - 05:00 hrs) for {num}**\n\n"
        answer_text += f"- **Total Night Calls:** {cnt} calls ({pct}% of total traffic)\n"
        if pct > 25:
            answer_text += f"- ⚠️ **High Night-Activity Flag:** Over {pct}% of communications occurred during late night hours.\n"
        else:
            answer_text += f"- Normal night activity proportion ({pct}%).\n"

        for ev in night.get("records", [])[:5]:
            evidence.append(ev)

        follow_ups = [
            f"Show top contacts for {num}",
            f"Check SIM swap history for {num}",
            "Check physical meetings around night time"
        ]
        filters = {"target_number": num, "hour_filter": "22:00-05:00"}

    elif intent == "common_numbers":
        targets = res.get("targets", [])
        common = res.get("common_contacts", [])
        mutual = res.get("direct_mutual_links", [])

        answer_text = f"**Cross-Suspect Correlation between {', '.join(targets)}**\n\n"
        answer_text += f"- **Shared / Common Contacts Found:** {len(common)}\n"
        for c in common:
            answer_text += f"  - Contact **{c['common_number']}** is linked to {c['target_count']} targets ({', '.join(c['connected_to_targets'])})\n"
            for ev in c.get("evidence", [])[:2]:
                evidence.append(ev)

        if mutual:
            answer_text += "\n- **Direct Mutual Communications:**\n"
            for m in mutual:
                answer_text += f"  - Direct link between {m['party_a']} and {m['party_b']}: {m['call_count']} direct calls\n"
                for ev in m.get("evidence", [])[:2]:
                    evidence.append(ev)
        else:
            answer_text += "\n- No direct calls detected between the selected numbers (they communicate primarily through shared nodes).\n"

        follow_ups = [
            f"Did {targets[0]} and {targets[1]} meet at the same tower?",
            f"Show IPDR logs for {targets[0]}",
            "View common nodes in the interactive Network Graph"
        ]
        filters = {"targets": targets, "common_only": True}

    elif intent == "meeting_detection":
        meetings = res.get("meetings", [])
        num1 = state["tool_args"].get("num1")
        num2 = state["tool_args"].get("num2")

        if meetings:
            answer_text = f"🚨 **Physical Meeting / Co-Location Detected!**\n\n"
            answer_text += f"Suspects **{num1}** and **{num2}** were co-located at the same cell tower within a narrow time window:\n\n"
            for m in meetings:
                diff_min = round(m["time_diff_sec"] / 60, 1)
                answer_text += f"- **Location:** {m['area_name']} (Cell ID: `{m['cell_id']}`)\n"
                answer_text += f"- **Time Interval:** {m['event_target_1']['timestamp']} vs {m['event_target_2']['timestamp']} (delta: ~{diff_min} mins)\n"
                answer_text += f"- **Coordinates:** Lat {m['lat']}, Lon {m['lon']}\n\n"
                evidence.append(m["event_target_1"])
                evidence.append(m["event_target_2"])
        else:
            answer_text = f"No concurrent cell tower co-location found between {num1} and {num2} within the standard 30-minute window."

        follow_ups = [
            f"Check IPDR data for {num1} during this meeting window",
            f"View {num1} path on Location Map",
            "Generate Case Report"
        ]
        filters = {"meeting_detected": True, "towers": [m["cell_id"] for m in meetings]}

    elif intent == "imei_sim_changes":
        multi_nums = res.get("multi_number_imeis", [])
        multi_imsis = res.get("multi_imsi_imeis", [])
        multi_imeis = res.get("multi_imei_numbers", [])

        answer_text = "**Device & SIM Swap Analysis (IMEI / IMSI Correlation)**\n\n"
        if multi_nums or multi_imsis:
            answer_text += "⚠️ **Handset Sharing / SIM Swap Detected:**\n"
            for item in multi_nums:
                answer_text += f"- **IMEI `{item['imei']}`** was used with **{item['distinct_numbers_count']} different numbers**: {', '.join(item['numbers'])}\n"
                for h in item.get("history", []):
                    answer_text += f"  - Number `{h['number']}` active from {h['first_seen']} to {h['last_seen']} ({h['count']} calls)\n"
                    for ev in h.get("sample_evidence", []):
                        evidence.append(ev)
        if multi_imeis:
            answer_text += "\n📱 **Multiple Handsets Used by Same Number:**\n"
            for item in multi_imeis:
                answer_text += f"- Number `{item['number']}` was detected using multiple devices: {', '.join(item['imeis'])}\n"
                for h in item.get("history", []):
                    for ev in h.get("sample_evidence", []):
                        evidence.append(ev)

        follow_ups = [
            "Show common contacts for swapped SIM numbers",
            "Trace tower timeline for the new number",
            "Check IPDR sessions for this IMEI"
        ]
        filters = {"anomaly": "SIM_SWAP"}

    elif intent == "location_timeline":
        num = res.get("number")
        timeline = res.get("timeline", [])
        repeated = res.get("repeated_towers", [])

        answer_text = f"**Cell Tower Movement Timeline for {num}**\n\n"
        answer_text += f"- Total Tower Connections: {len(timeline)}\n"
        answer_text += "- **Top Repeated Cell Sites:**\n"
        for r in repeated[:5]:
            answer_text += f"  - `{r['cell_id']}` ({r['area_name']}) - {r['count']} connections\n"

        for t in timeline[:6]:
            evidence.append(t)

        follow_ups = [
            f"Check meetings with other suspects near {repeated[0]['cell_id'] if repeated else 'Jaipur'}",
            f"Show top contacts for {num}",
            "Open Location Map tab to see animated path"
        ]
        filters = {"target_number": num, "view": "map"}

    elif intent == "ipdr_lookup":
        matched = res.get("match_found", False)
        if matched:
            sessions = res.get("sessions", [])
            primary = res.get("primary_subscriber")
            answer_text = f"🌐 **IPDR Session Resolution Match**\n\n"
            answer_text += f"- **Attributed Subscriber:** `{primary}`\n"
            answer_text += f"- **Match Precision:** {res.get('match_type')}\n"
            for s in sessions[:3]:
                answer_text += f"- **Session:** {s['session_start']} to {s['session_end']}\n"
                answer_text += f"  - Source: `{s['source_ip']}:{s['source_port']}` -> Dest: `{s['destination_ip']}:{s['destination_port']}`\n"
                answer_text += f"  - **Application Hint:** `{s['app_hint']}` ({s['app_attribution_note']})\n"
                answer_text += f"  - Data Volume: {round(s['bytes_transferred'] / 1024, 1)} KB\n\n"
                evidence.append({
                    "source_file": s["source_file"],
                    "source_row": s["source_row"],
                    "timestamp": s["session_start"],
                    "subscriber": s["subscriber_number"],
                    "ip": s["source_ip"],
                    "port": s["source_port"],
                    "app": s["app_hint"]
                })
        else:
            answer_text = f"**No Matching IPDR Session Found**\n\n{res.get('explanation')}\n"

        follow_ups = [
            f"Check CDR tower activity for subscriber during that time",
            "List all IPDR sessions for this suspect",
            "Generate full investigation report"
        ]
        filters = {"ipdr_match": matched}

    else:
        answer_text = f"**Analysis Summary**\n\nProcessed case investigation query with available metadata tools."
        follow_ups = ["Show common numbers", "Check SIM swap detection", "Detect meetings"]

    state["answer"] = answer_text
    state["evidence"] = evidence
    state["confidence_note"] = "AI observation - officer verification pending. Derived strictly from telecom metadata."
    state["status"] = "pending_verification"
    state["follow_up_questions"] = follow_ups
    state["suggested_filters"] = filters
    return state


def build_investigation_graph(db: Session):
    workflow = StateGraph(AgentState)

    workflow.add_node("intent", lambda state: intent_node(state, db))
    workflow.add_node("guardrail", guardrail_node)
    workflow.add_node("tool_runner", lambda state: tool_execution_node(state, db))
    workflow.add_node("answer_builder", evidence_and_answer_node)

    workflow.set_entry_point("intent")
    workflow.add_edge("intent", "guardrail")
    workflow.add_edge("guardrail", "tool_runner")
    workflow.add_edge("tool_runner", "answer_builder")
    workflow.add_edge("answer_builder", END)

    return workflow.compile()


def run_ai_assistant(query: str, case_id: str, user_role: str, db: Session) -> dict:
    initial_state: AgentState = {
        "query": query,
        "case_id": case_id,
        "user_role": user_role,
        "intent": "",
        "tool_name": "",
        "tool_args": {},
        "tool_result": {},
        "is_supported": True,
        "unsupported_reason": "",
        "answer": "",
        "evidence": [],
        "confidence_note": "AI observation - officer verification pending",
        "status": "pending_verification",
        "follow_up_questions": [],
        "suggested_filters": {}
    }

    graph = build_investigation_graph(db)
    final_state = graph.invoke(initial_state)

    # Save observation to database
    obs = AIObservation(
        case_id=case_id,
        query_text=query,
        answer_text=final_state["answer"],
        evidence_json=json.dumps(final_state["evidence"]),
        confidence_note=final_state["confidence_note"],
        status="pending_verification",
        suggested_followups=json.dumps(final_state["follow_up_questions"]),
        suggested_filters=json.dumps(final_state["suggested_filters"])
    )
    db.add(obs)
    db.commit()

    return {
        "observation_id": obs.id,
        "answer": final_state["answer"],
        "evidence": final_state["evidence"],
        "confidence_note": final_state["confidence_note"],
        "status": final_state["status"],
        "follow_up_questions": final_state["follow_up_questions"],
        "suggested_filters": final_state["suggested_filters"]
    }
