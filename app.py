
"""
MSC Monitor Ops - Streamlit Frontend
Works with lightweight backend.py.

Run:
  streamlit run app.py

Expected backend:
  uvicorn backend:app --reload --port 8000
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import json

import requests
import streamlit as st

st.set_page_config(page_title="MSC Monitor Ops", layout="wide")

DEFAULT_API_URL = "http://localhost:8000"

# -----------------------------------------------------------------------------
# API helpers
# -----------------------------------------------------------------------------

def get_api_url() -> str:
    return st.session_state.get("api_url", DEFAULT_API_URL).rstrip("/")


def api_get(path: str) -> Any:
    response = requests.get(f"{get_api_url()}{path}", timeout=15)
    response.raise_for_status()
    return response.json()


def api_post(path: str, payload: Dict[str, Any]) -> Any:
    response = requests.post(f"{get_api_url()}{path}", json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def safe_api_get(path: str) -> tuple[Optional[Any], Optional[str]]:
    try:
        return api_get(path), None
    except Exception as exc:
        return None, str(exc)


def safe_api_post(path: str, payload: Dict[str, Any]) -> tuple[Optional[Any], Optional[str]]:
    try:
        return api_post(path, payload), None
    except Exception as exc:
        return None, str(exc)

# -----------------------------------------------------------------------------
# UI helpers
# -----------------------------------------------------------------------------

def status_badge(label: str, mode: str = "neutral") -> None:
    colors = {
        "success": ("#DCFCE7", "#166534"),
        "warning": ("#FEF9C3", "#854D0E"),
        "danger": ("#FEE2E2", "#991B1B"),
        "info": ("#DBEAFE", "#1E40AF"),
        "neutral": ("#F3F4F6", "#374151"),
    }
    bg, fg = colors.get(mode, colors["neutral"])
    st.markdown(
        f"<span style='background:{bg}; color:{fg}; padding:4px 10px; "
        f"border-radius:999px; font-size:12px; font-weight:600'>{label}</span>",
        unsafe_allow_html=True,
    )


def guidance_mode_color(mode: str) -> str:
    if mode == "Recommend":
        return "success"
    if mode == "Suggest Investigation":
        return "warning"
    if mode == "Escalate":
        return "danger"
    return "neutral"


def queue_status_color(status: str) -> str:
    return {
        "Open": "info",
        "Assigned": "warning",
        "Escalated": "danger",
        "Auto Resolved": "success",
    }.get(status, "neutral")


def compact_json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def rerun() -> None:
    try:
        st.rerun()
    except Exception:
        st.experimental_rerun()

# -----------------------------------------------------------------------------
# Header / sidebar
# -----------------------------------------------------------------------------

st.title("MSC Monitor Ops - AI Assisted Operations Support")
st.caption(
    "Evidence-grounded support assistant for ticket classification, similar incident matching, "
    "resolution guidance, escalation packaging, and documentation gap detection."
)

with st.sidebar:
    st.header("Backend Connection")
    st.text_input("FastAPI backend URL", DEFAULT_API_URL, key="api_url")
    health, health_error = safe_api_get("/health")
    if health_error:
        st.error("Backend unavailable")
        st.code(
            "Start backend:\n"
            "pip install -r requirements.txt\n"
            "uvicorn backend:app --reload --port 8000",
            language="bash",
        )
        st.caption(health_error)
    else:
        st.success(f"Connected: {health.get('status')} | {health.get('version', 'n/a')}")

    if st.button("Refresh App", use_container_width=True):
        rerun()

    st.divider()
    st.header("Manual Ticket Analysis")
    with st.form("manual_ticket_form"):
        manual_source = st.selectbox("Source", ["Manual", "ServiceNow", "Jira", "E-Mail"])
        manual_title = st.text_input("Title", "Amazon PVC delivery failed")
        manual_description = st.text_area(
            "Description",
            "Delivery failed from Prism with manifest validation error and missing territory metadata.",
            height=110,
        )
        manual_logs = st.text_area(
            "Logs, one per line",
            "manifest_validation_failed\nmissing territoryCode\npartner=Amazon PVC",
            height=90,
        )
        analyze_manual = st.form_submit_button("Analyze Without Saving", use_container_width=True)

    if analyze_manual:
        payload = {
            "source": manual_source,
            "status": "Open",
            "title": manual_title,
            "description": manual_description,
            "requester": "Operator",
            "logs": [line.strip() for line in manual_logs.splitlines() if line.strip()],
            "monitor_context": {
                "workflow_status": "Unknown",
                "processing_status": "Manual analysis",
                "current_step": "Operator supplied",
                "active_incident": "Unknown",
                "recent_deployment": "Unknown",
                "known_outage": "Unknown",
                "partner": "Manual",
            },
        }
        data, err = safe_api_post("/tickets/analyze", payload)
        if err:
            st.error("Manual analysis failed")
            st.caption(err)
        else:
            st.session_state["manual_analysis"] = data
            st.session_state["selected_ticket_id"] = None
            rerun()

    if st.session_state.get("manual_analysis"):
        if st.button("Exit Manual Analysis", use_container_width=True):
            st.session_state.pop("manual_analysis", None)
            rerun()

if health_error:
    st.stop()

# -----------------------------------------------------------------------------
# Load data
# -----------------------------------------------------------------------------

tickets, tickets_error = safe_api_get("/tickets")
if tickets_error:
    st.error("Could not load tickets from backend.")
    st.caption(tickets_error)
    st.stop()

manual_analysis = st.session_state.get("manual_analysis")

# -----------------------------------------------------------------------------
# Three-panel layout
# -----------------------------------------------------------------------------

left_col, center_col, right_col = st.columns([0.90, 1.55, 1.35], gap="large")

# Left panel: Ticket Queue
with left_col:
    st.subheader("Ticket Queue")

    if manual_analysis:
        status_badge("Manual Analysis Mode", "info")
        st.info("Showing one-off manual ticket analysis. Use sidebar to return to the queue.")
        selected_analysis = manual_analysis
    else:
        status_filter = st.radio(
            "Status Filter",
            ["All", "Open", "Assigned", "Escalated", "Auto Resolved"],
            horizontal=False,
        )
        filtered_tickets = [
            ticket for ticket in tickets
            if status_filter == "All" or ticket.get("status") == status_filter
        ]
        if not filtered_tickets:
            st.warning("No tickets found for this filter.")
            st.stop()

        ticket_labels = [
            f"{ticket['id']} | {ticket.get('status', 'Open')} | {ticket['title']}"
            for ticket in filtered_tickets
        ]
        default_index = 0
        if st.session_state.get("selected_ticket_id"):
            for idx, ticket in enumerate(filtered_tickets):
                if ticket["id"] == st.session_state["selected_ticket_id"]:
                    default_index = idx
                    break

        selected_label = st.selectbox("Select Ticket", ticket_labels, index=default_index)
        selected_ticket_id = selected_label.split(" | ")[0]
        st.session_state["selected_ticket_id"] = selected_ticket_id

        selected_analysis, selected_error = safe_api_get(f"/tickets/{selected_ticket_id}")
        if selected_error:
            st.error("Could not analyze selected ticket.")
            st.caption(selected_error)
            st.stop()

        st.markdown("#### Queue Items")
        for ticket in filtered_tickets:
            with st.container(border=True):
                st.write(f"**{ticket['id']}**")
                st.write(ticket["title"])
                status_badge(ticket.get("status", "Open"), queue_status_color(ticket.get("status", "Open")))

analysis = selected_analysis
ticket = analysis["ticket"]
classification = analysis["classification"]
assistant = analysis["assistant"]

# Center panel: Investigation
with center_col:
    st.subheader("Ticket Investigation")

    with st.container(border=True):
        st.write(f"### {ticket.get('id', 'Manual')} - {ticket.get('title')}")
        st.write(ticket.get("description", ""))
        st.caption(
            f"Source: {ticket.get('source', 'n/a')} | "
            f"Requester: {ticket.get('requester', 'n/a')} | "
            f"Created: {ticket.get('created', 'n/a')}"
        )

    st.markdown("#### Classification")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Workflow", classification["workflow"])
    c2.metric("Product", classification["product"])
    c3.metric("Type", classification["incident_type"])
    c4.metric("Severity", classification["severity"])
    c5.metric("Classifier", f"{classification['confidence']}%")

    st.markdown("#### Similar Incidents")
    similar_summary = analysis.get("similar_summary", {})
    s1, s2, s3 = st.columns(3)
    s1.metric("Matches", similar_summary.get("count", 0))
    s2.metric("Recurrence", f"{similar_summary.get('resolution_recurrence', 0)}%")
    s3.metric("Outcome", similar_summary.get("outcome", "n/a"))

    similar_incidents = analysis.get("similar_incidents", [])
    if similar_incidents:
        for incident in similar_incidents:
            title = f"{incident.get('id')} - {incident.get('title')} | score={incident.get('score')}"
            with st.expander(title):
                st.write(f"Workflow: {incident.get('workflow')} | Product: {incident.get('product')}")
                st.write(f"Type: {incident.get('incident_type')} | Severity: {incident.get('severity')}")
                st.write(f"Resolution: {incident.get('resolution', 'n/a')}")
    else:
        st.info("No similar incidents found.")

    st.markdown("#### Monitor Context")
    st.json(analysis.get("monitor_context", {}))

    st.markdown("#### Documentation Gap Signals")
    gaps = analysis.get("documentation_gaps", [])
    if gaps:
        for gap in gaps:
            st.warning(f"{gap.get('type')}: {gap.get('message')} → {gap.get('action')}")
    else:
        st.success("No documentation gap detected for this evidence set.")

# Right panel: AI Assistant
with right_col:
    st.subheader("AI Resolution Assistant")

    status_badge(assistant.get("mode", "Unknown"), guidance_mode_color(assistant.get("mode", "")))
    st.metric("Guidance Confidence", f"{assistant.get('confidence', 0)}%")

    if assistant.get("unsupported_recommendation_blocked"):
        st.error("Unsupported recommendation blocked. Escalation required.")

    if assistant.get("human_approval_required"):
        st.caption("Human approval required for all operational actions.")

    st.markdown("#### Likely Cause")
    st.write(assistant.get("likely_cause", "n/a"))

    st.markdown("#### Recommended / Investigation Actions")
    for idx, action in enumerate(assistant.get("recommended_actions", []), 1):
        st.write(f"{idx}. {action}")

    st.markdown("#### Evidence")
    evidence = assistant.get("evidence", [])
    if evidence:
        for item in evidence:
            st.info(item)
    else:
        st.warning("No approved source evidence found.")

    st.markdown("#### Sources, Version, Lineage")
    sources = assistant.get("sources", [])
    if sources:
        st.dataframe(sources, use_container_width=True, hide_index=True)
        st.code("\n".join(assistant.get("source_lineage", [])), language="text")
    else:
        st.write("No eligible citations.")

    escalation_package = assistant.get("escalation_package")
    if escalation_package:
        st.markdown("#### Escalation Package")
        st.json(escalation_package)

    st.markdown("#### Conversational Support")
    question = st.text_input(
        "Ask about this ticket",
        "Why did this fail?",
        key=f"question_{ticket.get('id', 'manual')}",
    )
    if st.button("Ask Assistant", use_container_width=True):
        ticket_id = ticket.get("id")
        if not ticket_id or str(ticket_id).startswith("MANUAL"):
            st.info("Manual analysis already shows grounded guidance above. Save/ingest the ticket to use backend chat.")
        else:
            chat_result, chat_error = safe_api_post("/chat", {"ticket_id": ticket_id, "question": question})
            if chat_error:
                st.error("Chat failed")
                st.caption(chat_error)
            else:
                st.write(chat_result.get("answer"))
                st.caption(f"Mode: {chat_result.get('mode')} | Confidence: {chat_result.get('confidence')}%")

# -----------------------------------------------------------------------------
# Pilot Analytics
# -----------------------------------------------------------------------------

st.divider()
st.subheader("Pilot Analytics")
analytics, analytics_error = safe_api_get("/analytics")
if analytics_error:
    st.warning("Analytics unavailable.")
    st.caption(analytics_error)
else:
    a1, a2, a3, a4, a5, a6 = st.columns(6)
    a1.metric("Tickets", analytics.get("ticket_count", 0))
    a2.metric("Recommend", f"{analytics.get('recommendation_rate', 0)}%")
    a3.metric("Investigate", f"{analytics.get('investigation_rate', 0)}%")
    a4.metric("Escalate", f"{analytics.get('escalation_rate', 0)}%")
    a5.metric("Citation", f"{analytics.get('citation_coverage', 0)}%")
    a6.metric("Unsupported Recs", analytics.get("unsupported_recommendations", 0))

    with st.expander("Workflow Distribution"):
        st.json(analytics.get("workflow_distribution", {}))

    with st.expander("Documentation Gaps"):
        gaps = analytics.get("documentation_gaps", [])
        if gaps:
            st.json(gaps)
        else:
            st.success("No documentation gaps detected.")

    with st.expander("Pilot Targets"):
        st.json(analytics.get("pilot_targets", {}))
