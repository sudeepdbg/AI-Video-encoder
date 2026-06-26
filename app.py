
import json
from typing import Any, Dict, List
import requests
import streamlit as st

API_URL = st.sidebar.text_input("Backend API URL", "http://localhost:8000")

st.set_page_config(page_title="MSC Monitor Ops", layout="wide")
st.title("MSC Monitor Ops - AI Assisted Operations Support")
st.caption("Recommendation-mode prototype with evidence-backed guidance, citations, confidence, source lineage, escalation packaging, and documentation gap signals.")


def api_get(path: str):
    r = requests.get(f"{API_URL}{path}", timeout=10)
    r.raise_for_status()
    return r.json()


def api_post(path: str, payload: Dict[str, Any]):
    r = requests.post(f"{API_URL}{path}", json=payload, timeout=20)
    r.raise_for_status()
    return r.json()


def pill(text: str, color: str = "gray"):
    colors = {
        "green": "#DCFCE7", "yellow": "#FEF9C3", "red": "#FEE2E2", "blue": "#DBEAFE", "gray": "#F3F4F6"
    }
    st.markdown(f"<span style='background:{colors.get(color, colors['gray'])}; padding:4px 10px; border-radius:999px; font-size:12px;'>{text}</span>", unsafe_allow_html=True)


def status_color(status: str) -> str:
    return {"Open": "blue", "Assigned": "yellow", "Escalated": "red", "Auto Resolved": "green"}.get(status, "gray")

try:
    health = api_get("/health")
except Exception as e:
    st.error(f"Backend unavailable. Start with: uvicorn backend:app --reload --port 8000\n\nError: {e}")
    st.stop()

with st.sidebar:
    st.header("Prototype Controls")
    st.success(f"Backend: {health['status']}")
    st.divider()
    if st.button("Refresh"):
        st.rerun()
    st.subheader("Ingest Manual Ticket")
    with st.form("manual_ticket"):
        title = st.text_input("Title", "Amazon PVC delivery failed")
        description = st.text_area("Description", "Delivery failed from Prism with manifest validation error and missing territory metadata.")
        source = st.selectbox("Source", ["ServiceNow", "Jira", "E-Mail", "Manual"])
        logs = st.text_area("Logs, one per line", "manifest_validation_failed\nmissing territoryCode")
        submitted = st.form_submit_button("Analyze without saving")
        if submitted:
            payload = {"source": source, "title": title, "description": description, "logs": [x.strip() for x in logs.splitlines() if x.strip()], "monitor_context": {"workflow_status": "Failed", "processing_status": "Blocked", "current_step": "Unknown", "partner": "Manual"}}
            st.session_state["manual_analysis"] = api_post("/tickets/analyze", payload)

if "manual_analysis" in st.session_state:
    analysis = st.session_state["manual_analysis"]
    selected_ticket_id = None
else:
    tickets = api_get("/tickets")
    left, center, right = st.columns([0.9, 1.5, 1.3], gap="large")
    with left:
        st.subheader("Ticket Queue")
        statuses = ["All", "Open", "Assigned", "Escalated", "Auto Resolved"]
        status_filter = st.radio("Status", statuses, horizontal=False)
        filtered = [t for t in tickets if status_filter == "All" or t.get("status") == status_filter]
        if not filtered:
            st.info("No tickets in this status.")
            st.stop()
        labels = [f"{t['id']} | {t.get('status')} | {t['title']}" for t in filtered]
        selected_label = st.selectbox("Select ticket", labels)
        selected_ticket_id = selected_label.split(" | ")[0]
        for t in filtered:
            with st.container(border=True):
                st.write(f"**{t['id']}**")
                st.write(t["title"])
                pill(t.get("status", "Open"), status_color(t.get("status", "Open")))
    analysis = api_get(f"/tickets/{selected_ticket_id}")
    
    with center:
        render_center = True
    with right:
        render_right = True

if "manual_analysis" in st.session_state:
    if st.button("Back to queued tickets"):
        del st.session_state["manual_analysis"]
        st.rerun()
    center, right = st.columns([1.4, 1.2], gap="large")

with center:
    ticket = analysis["ticket"]
    cls = analysis["classification"]
    st.subheader("Ticket Investigation")
    with st.container(border=True):
        st.write(f"### {ticket.get('id', 'Manual')} - {ticket['title']}")
        st.write(ticket.get("description", ""))
        st.caption(f"Source: {ticket.get('source')} | Requester: {ticket.get('requester')} | Created: {ticket.get('created', 'n/a')}")
    st.markdown("#### Classification")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Workflow", cls["workflow"])
    c2.metric("Product", cls["product"])
    c3.metric("Type", cls["incident_type"])
    c4.metric("Severity", cls["severity"])
    c5.metric("Classifier", f"{cls['confidence']}%")

    st.markdown("#### Similar Incidents")
    sim = analysis["similar_summary"]
    s1, s2, s3 = st.columns(3)
    s1.metric("Matches", sim.get("count", 0))
    s2.metric("Recurrence", f"{sim.get('resolution_recurrence', 0)}%")
    s3.metric("Outcome", sim.get("outcome", "n/a"))
    for inc in analysis["similar_incidents"]:
        with st.expander(f"{inc['id']} - {inc['title']} ({inc['score']})"):
            st.write(f"Workflow: {inc['workflow']} | Product: {inc['product']} | Type: {inc['incident_type']} | Severity: {inc['severity']}")
            st.write(f"Resolution: {inc.get('resolution')}")

    st.markdown("#### Monitor Context")
    st.json(analysis.get("monitor_context", {}))

    st.markdown("#### Documentation Gap Signals")
    gaps = analysis["documentation_gaps"]
    if gaps:
        for g in gaps:
            st.warning(f"{g['type']}: {g['message']} → {g['action']}")
    else:
        st.success("No documentation gap detected for current evidence set.")

with right:
    st.subheader("AI Resolution Assistant")
    assistant = analysis["assistant"]
    mode = assistant["mode"]
    color = "green" if mode == "Recommend" else "yellow" if mode == "Suggest Investigation" else "red"
    pill(mode, color)
    st.metric("Guidance Confidence", f"{assistant['confidence']}%")
    if assistant.get("unsupported_recommendation_blocked"):
        st.error("Unsupported recommendation blocked. Escalation required.")

    st.markdown("#### Likely Cause")
    st.write(assistant["likely_cause"])

    st.markdown("#### Recommended / Investigation Actions")
    for i, action in enumerate(assistant["recommended_actions"], 1):
        st.write(f"{i}. {action}")
    st.caption("Human approval required for all operational actions.")

    st.markdown("#### Evidence")
    if assistant["evidence"]:
        for e in assistant["evidence"]:
            st.info(e)
    else:
        st.warning("No approved operational evidence found.")

    st.markdown("#### Sources, Version, Lineage")
    if assistant["sources"]:
        st.dataframe(assistant["sources"], use_container_width=True, hide_index=True)
        st.code("\n".join(assistant["source_lineage"]), language="text")
    else:
        st.write("No eligible citations.")

    if assistant.get("escalation_package"):
        st.markdown("#### Escalation Package")
        st.json(assistant["escalation_package"])

    st.markdown("#### Conversational Support")
    default_q = "Why did this fail?"
    q = st.text_input("Ask", default_q)
    if st.button("Ask Assistant"):
        tid = ticket.get("id")
        if tid and not tid.startswith("MANUAL"):
            answer = api_post("/chat", {"ticket_id": tid, "question": q})
            st.write(answer["answer"])
            st.caption(f"Mode: {answer['mode']} | Confidence: {answer['confidence']}%")
        else:
            st.info("Chat endpoint is enabled for saved queue tickets. Manual analysis already shows the grounded answer above.")

st.divider()
st.subheader("Pilot Analytics")
analytics = api_get("/analytics")
a1, a2, a3, a4, a5 = st.columns(5)
a1.metric("Tickets", analytics["ticket_count"])
a2.metric("Recommend Rate", f"{analytics['recommendation_rate']}%")
a3.metric("Escalation Rate", f"{analytics['escalation_rate']}%")
a4.metric("Citation Coverage", f"{analytics['citation_coverage']}%")
a5.metric("Unsupported Recs", analytics["unsupported_recommendations"])
with st.expander("Pilot targets and workflow distribution"):
    st.json({"targets": analytics["pilot_targets"], "workflow_distribution": analytics["workflow_distribution"]})
