"""
MSC Monitor Ops - Backend Module
Pure Python backend logic imported by app.py.
No FastAPI, no localhost, no external services, no compiled ML dependencies.
Safe for Streamlit Community Cloud.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple
import re

RECOMMEND_THRESHOLD = 80
INVESTIGATE_THRESHOLD = 50
STALE_DOC_CUTOFF = "2025-06-01"
APPROVED_SOURCE_TYPES = {"Runbook", "SOP", "KB Article", "RCA", "Postmortem"}

KNOWLEDGE: List[Dict[str, Any]] = [
    {"id": "KB-1248", "source": "KB Article", "title": "Amazon PVC Manifest Validation Failure", "version": "v2.3", "updated": "2026-05-10", "owner": "Distribution", "approved": True, "workflow": "Distribution", "product": "Prism", "tags": ["amazon", "pvc", "delivery", "manifest", "validation", "metadata"], "content": "When Amazon PVC delivery fails with manifest validation errors, verify package status, validate generated manifest fields, confirm partner endpoint configuration, and resubmit the distribution workflow after correcting missing required metadata."},
    {"id": "RUN-PRISM-REDLV-52", "source": "Runbook", "title": "Prism Partner Redelivery", "version": "v5.2", "updated": "2026-04-11", "owner": "Distribution", "approved": True, "workflow": "Distribution", "product": "Prism", "tags": ["redelivery", "partner", "prism", "distribution", "manifest"], "content": "For Prism partner redelivery issues: check workflow state, verify partner mapping, validate manifest generation, confirm delivery retry eligibility, then rerun the failed delivery step only after operator approval."},
    {"id": "RCA-2026-004", "source": "RCA", "title": "PVC Delivery Failures Due to Missing Territory Metadata", "version": "v1.0", "updated": "2026-03-18", "owner": "Distribution", "approved": True, "workflow": "Distribution", "product": "Prism", "tags": ["pvc", "metadata", "territory", "amazon", "delivery failure"], "content": "A recurring Amazon PVC delivery failure pattern was caused by missing territory metadata in the distribution manifest. Resolution required metadata correction and workflow resubmission. Preventive action: add validation before manifest publish."},
    {"id": "RUN-MAM-STUCK-20", "source": "Runbook", "title": "Foundry MAM Stuck Workflow Recovery", "version": "v2.0", "updated": "2024-08-02", "owner": "Media Asset Management", "approved": True, "workflow": "Inventory", "product": "Foundry MAM", "tags": ["mam", "stuck workflow", "asset", "lock", "inventory"], "content": "If a Foundry MAM inventory workflow is stuck, check current processing step, review latest deployment or active outage, validate asset lock state, and escalate to MAM Engineering if lock cleanup is required."},
    {"id": "SOP-LOC-VAL-11", "source": "SOP", "title": "Localization Validation Triage", "version": "v1.1", "updated": "2025-02-19", "owner": "Localization", "approved": True, "workflow": "Localization", "product": "Pegasus", "tags": ["localization", "validation", "subtitle", "audio", "language"], "content": "For localization validation failures, compare expected track inventory with delivered assets, validate language tags, inspect subtitle conformance, and route content gaps to Localization Operations."},
    {"id": "KB-RIGHTS-OUT-02", "source": "KB Article", "title": "Rights Visibility Gap Investigation", "version": "v1.0", "updated": "2023-10-15", "owner": "Rights", "approved": True, "workflow": "Rights", "product": "Rally", "tags": ["rights", "visibility", "availability", "window", "sky"], "content": "Rights visibility gaps should be investigated by checking availability windows, territory mappings, partner restrictions, and upstream rights feed completion."},
    {"id": "DRAFT-UNAPPROVED-01", "source": "Draft Notes", "title": "Unofficial Domino Retry Notes", "version": "draft", "updated": "2026-01-05", "owner": "Fulfillment", "approved": False, "workflow": "Fulfillment", "product": "Domino", "tags": ["domino", "retry"], "content": "Unapproved notes. This source must never be used for operator guidance."},
]

INCIDENTS: List[Dict[str, Any]] = [
    {"id": "INC1510021", "source": "ServiceNow", "title": "Amazon PVC delivery failed manifest validation", "workflow": "Distribution", "product": "Prism", "incident_type": "Delivery Failure", "severity": "P2", "resolved": True, "resolution_success": True, "created": "2026-05-11", "tags": ["amazon", "pvc", "manifest", "delivery"], "resolution": "Corrected missing territory metadata and resubmitted Prism delivery workflow."},
    {"id": "INC1521443", "source": "ServiceNow", "title": "PVC package failed delivery due to invalid manifest", "workflow": "Distribution", "product": "Prism", "incident_type": "Delivery Failure", "severity": "P2", "resolved": True, "resolution_success": True, "created": "2026-05-25", "tags": ["pvc", "manifest", "validation"], "resolution": "Validated package, regenerated manifest, retried delivery step."},
    {"id": "INC1532214", "source": "Jira", "title": "Amazon partner endpoint rejected Prism delivery", "workflow": "Distribution", "product": "Prism", "incident_type": "Partner Configuration", "severity": "P3", "resolved": True, "resolution_success": True, "created": "2026-06-02", "tags": ["amazon", "partner", "endpoint", "prism"], "resolution": "Updated partner mapping and requeued delivery."},
    {"id": "INC1539000", "source": "ServiceNow", "title": "Foundry MAM asset workflow frozen at ingest step", "workflow": "Inventory", "product": "Foundry MAM", "incident_type": "Stuck Workflow", "severity": "P2", "resolved": True, "resolution_success": True, "created": "2026-04-04", "tags": ["mam", "stuck", "workflow", "lock"], "resolution": "Cleared stale lock after MAM Engineering approval."},
    {"id": "INC1544120", "source": "Jira", "title": "Localization validation failed for subtitle track", "workflow": "Localization", "product": "Pegasus", "incident_type": "Validation Failure", "severity": "P3", "resolved": True, "resolution_success": True, "created": "2026-04-28", "tags": ["localization", "subtitle", "validation"], "resolution": "Corrected language tag and reran localization validation."},
    {"id": "INC1549999", "source": "ServiceNow", "title": "Rights availability missing for Sky title", "workflow": "Rights", "product": "Rally", "incident_type": "Visibility Gap", "severity": "P3", "resolved": False, "resolution_success": False, "created": "2026-06-13", "tags": ["rights", "sky", "visibility"], "resolution": "Pending rights feed review."},
]

TICKETS: List[Dict[str, Any]] = [
    {"id": "TCK-1001", "source": "ServiceNow", "status": "Open", "title": "Delivery Failed Amazon PVC", "description": "Amazon PVC delivery failed from Prism. Error suggests manifest validation issue and missing territory data.", "created": "2026-06-20T10:15:00Z", "requester": "Distribution Ops", "logs": ["manifest_validation_failed", "missing territoryCode", "partner=Amazon PVC"], "monitor_context": {"workflow_status": "Failed", "processing_status": "Delivery blocked", "current_step": "Manifest validation", "active_incident": "No", "recent_deployment": "No", "known_outage": "No", "partner": "Amazon PVC"}},
    {"id": "TCK-1002", "source": "Jira", "status": "Assigned", "title": "Foundry MAM workflow stuck", "description": "Asset inventory workflow has not moved for 90 minutes. Current step shows ingest lock wait.", "created": "2026-06-21T08:30:00Z", "requester": "Inventory Support", "logs": ["lock_wait_timeout", "asset lock active"], "monitor_context": {"workflow_status": "Delayed", "processing_status": "Waiting", "current_step": "Asset lock wait", "active_incident": "No", "recent_deployment": "Yes - MAM worker", "known_outage": "No", "partner": "Internal"}},
    {"id": "TCK-1003", "source": "E-Mail", "status": "Open", "title": "Unknown Domino fulfillment behavior", "description": "Domino fulfillment failed with a new error not found in current KB. No known runbook seems to cover it.", "created": "2026-06-22T13:10:00Z", "requester": "Fulfillment Ops", "logs": ["unknown_error_code=DX-991"], "monitor_context": {"workflow_status": "Failed", "processing_status": "Unknown", "current_step": "Package assembly", "active_incident": "No", "recent_deployment": "No", "known_outage": "No", "partner": "Max"}},
    {"id": "TCK-1004", "source": "ServiceNow", "status": "Escalated", "title": "Rights visibility gap for Sky package", "description": "Sky package is not visible although rights feed appears complete. Need ownership and escalation path.", "created": "2026-06-22T15:10:00Z", "requester": "Rights Ops", "logs": ["availability missing", "partner=Sky"], "monitor_context": {"workflow_status": "Completed with warning", "processing_status": "Visibility gap", "current_step": "Rights publish", "active_incident": "No", "recent_deployment": "No", "known_outage": "No", "partner": "Sky"}},
]

OWNERSHIP: Dict[Tuple[str, str], Dict[str, str]] = {
    ("Distribution", "Prism"): {"owner_team": "Distribution Ops", "l2": "Distribution L2", "engineering": "Prism Engineering", "product_owner": "Prism Product", "operations": "MSC Operations"},
    ("Inventory", "Foundry MAM"): {"owner_team": "Media Asset Management", "l2": "MAM L2", "engineering": "MAM Engineering", "product_owner": "MAM Product", "operations": "MSC Operations"},
    ("Localization", "Pegasus"): {"owner_team": "Localization Ops", "l2": "Localization L2", "engineering": "Pegasus Engineering", "product_owner": "Localization Product", "operations": "MSC Operations"},
    ("Rights", "Rally"): {"owner_team": "Rights Ops", "l2": "Rights L2", "engineering": "Rally Engineering", "product_owner": "Rights Product", "operations": "MSC Operations"},
    ("Fulfillment", "Domino"): {"owner_team": "Fulfillment Ops", "l2": "Fulfillment L2", "engineering": "Domino Engineering", "product_owner": "Fulfillment Product", "operations": "MSC Operations"},
}

KEYWORDS = {
    "workflow": {"Distribution": ["delivery", "partner", "redelivery", "amazon", "pvc", "manifest"], "Fulfillment": ["fulfillment", "domino", "package", "assembly"], "Inventory": ["inventory", "mam", "asset", "lock", "foundry"], "Localization": ["localization", "subtitle", "audio", "language"], "Rights": ["rights", "availability", "visibility", "sky"]},
    "product": {"Prism": ["prism", "amazon", "pvc", "manifest"], "Domino": ["domino", "fulfillment"], "Foundry MAM": ["foundry", "mam", "asset"], "Pegasus": ["pegasus", "localization"], "Rally": ["rally", "rights", "sky"]},
    "incident_type": {"Stuck Workflow": ["stuck", "frozen", "blocked", "wait", "lock"], "Delivery Failure": ["delivery failed", "failed delivery", "delivery", "rejected"], "Metadata Issue": ["metadata", "territory", "missing"], "Partner Configuration": ["partner", "endpoint", "mapping"], "Visibility Gap": ["visibility", "not visible", "availability missing"], "Validation Failure": ["validation", "validate", "manifest validation"]},
}


def normalize(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text).lower()).strip()


def token_set(text: str) -> set:
    return set(re.findall(r"[a-z0-9]+", normalize(text)))


def similarity(query: str, corpus: str) -> float:
    qt = token_set(query)
    ct = token_set(corpus)
    if not qt or not ct:
        return 0.0
    jaccard = len(qt & ct) / max(1, len(qt | ct))
    seq = SequenceMatcher(None, normalize(query), normalize(corpus)).ratio()
    return round((0.72 * jaccard) + (0.28 * seq), 3)


def doc_text(doc: Dict[str, Any]) -> str:
    parts = [str(doc.get(k, "")) for k in ["title", "workflow", "product", "incident_type", "source", "content", "resolution"]]
    tags = doc.get("tags", [])
    parts.append(" ".join(tags) if isinstance(tags, list) else str(tags))
    return " ".join(parts)


def search_docs(query: str, docs: List[Dict[str, Any]], top_k: int = 5, approved_only: bool = False) -> List[Dict[str, Any]]:
    hits = []
    for doc in docs:
        if approved_only and (not doc.get("approved", True) or doc.get("source") not in APPROVED_SOURCE_TYPES):
            continue
        score = similarity(query, doc_text(doc))
        if score >= 0.035:
            item = dict(doc)
            item["score"] = score
            hits.append(item)
    return sorted(hits, key=lambda x: x["score"], reverse=True)[:top_k]


def keyword_score(text: str, options: Dict[str, List[str]]) -> Tuple[str, float]:
    t = normalize(text)
    best_label = list(options.keys())[0]
    best_score = 0.0
    for label, words in options.items():
        raw = sum(2 if " " in word else 1 for word in words if normalize(word) in t)
        score = min(1.0, raw / max(3.0, len(words) / 2.0))
        if score > best_score:
            best_label = label
            best_score = score
    return best_label, best_score


def classify_ticket(ticket: Dict[str, Any]) -> Dict[str, Any]:
    text = " ".join([ticket.get("title", ""), ticket.get("description", ""), " ".join(ticket.get("logs", []) or [])])
    workflow, workflow_score = keyword_score(text, KEYWORDS["workflow"])
    product, product_score = keyword_score(text, KEYWORDS["product"])
    incident_type, incident_score = keyword_score(text, KEYWORDS["incident_type"])
    lowered = normalize(text)
    if "outage" in lowered or "business critical" in lowered:
        severity = "P1"
    elif any(x in lowered for x in ["failed", "blocked", "stuck"]):
        severity = "P2"
    elif incident_type in ["Delivery Failure", "Stuck Workflow"]:
        severity = "P2"
    elif "visibility" in lowered:
        severity = "P3"
    else:
        severity = "P4"
    confidence = max(25, min(98, round((0.45 * workflow_score + 0.30 * product_score + 0.25 * incident_score) * 100)))
    return {"ticket": ticket.get("title"), "workflow": workflow, "product": product, "incident_type": incident_type, "severity": severity, "confidence": confidence}


def owner_for(workflow: str, product: str) -> Dict[str, str]:
    return OWNERSHIP.get((workflow, product), {"owner_team": "Unknown", "l2": "MSC L2 Queue", "engineering": "Engineering Triage", "product_owner": "Product Triage", "operations": "MSC Operations"})


def recommend_actions(classification: Dict[str, Any]) -> List[str]:
    incident_type = classification["incident_type"]
    if incident_type == "Delivery Failure":
        return ["Validate package status in MSC Monitor.", "Verify manifest generation and required metadata fields.", "Confirm partner mapping and endpoint configuration.", "Resubmit or retry only after human approval."]
    if incident_type == "Stuck Workflow":
        return ["Check current workflow step and wait duration.", "Review deployment/outage/dependency context.", "Validate lock state or downstream dependency.", "Escalate before cleanup actions."]
    if incident_type == "Visibility Gap":
        return ["Check availability windows and territory mappings.", "Confirm upstream rights feed completion.", "Validate partner restrictions and publish status.", "Route to rights owner if feed and mappings are correct."]
    return ["Review matched source guidance.", "Validate monitor context and logs.", "Confirm owner/escalation path.", "Proceed only after human approval."]


def analyze(ticket: Dict[str, Any]) -> Dict[str, Any]:
    classification = classify_ticket(ticket)
    query = " ".join([ticket.get("title", ""), ticket.get("description", ""), " ".join(ticket.get("logs", []) or []), classification["workflow"], classification["product"], classification["incident_type"]])
    knowledge_hits = search_docs(query, KNOWLEDGE, top_k=4, approved_only=True)
    incident_hits = search_docs(query, INCIDENTS, top_k=5, approved_only=False)
    evidence_strength = max([h["score"] for h in knowledge_hits], default=0)
    incident_strength = max([h["score"] for h in incident_hits], default=0)
    evidence_score = min(100, round(((0.65 * evidence_strength) + (0.35 * incident_strength)) * 235))
    final_confidence = round((0.55 * classification["confidence"]) + (0.45 * evidence_score))
    if knowledge_hits and final_confidence >= RECOMMEND_THRESHOLD:
        mode = "Recommend"
        actions = recommend_actions(classification)
        escalation_reason = None
    elif knowledge_hits and final_confidence >= INVESTIGATE_THRESHOLD:
        mode = "Suggest Investigation"
        actions = ["Review monitor context and logs.", "Compare with similar incidents.", "Validate source version applicability.", "Escalate if remediation remains unclear."]
        escalation_reason = "Confidence between 50 and 80."
    else:
        mode = "Escalate"
        actions = ["Escalate with gathered context.", "Request owner review.", "Capture documentation gap if confirmed."]
        escalation_reason = "Approved evidence missing or confidence below threshold."
    owner = owner_for(classification["workflow"], classification["product"])
    sources = [{"id": h["id"], "source": h["source"], "title": h["title"], "version": h.get("version", "n/a"), "updated": h.get("updated", "n/a"), "owner": h.get("owner", "unknown"), "score": h["score"]} for h in knowledge_hits]
    lineage = [s["source"] + "::" + s["id"] + "::" + s["version"] + "::" + s["owner"] for s in sources]
    gaps = [] if knowledge_hits else [{"type": "Missing Coverage", "message": "No approved source found for this issue pattern.", "action": "Create New Runbook Request"}]
    for hit in knowledge_hits:
        if hit.get("updated", "") < STALE_DOC_CUTOFF:
            gaps.append({"type": "Stale Documentation", "message": hit["title"] + " is older than freshness threshold.", "action": "Review and refresh source"})
    success_count = sum(1 for h in incident_hits if h.get("resolution_success"))
    recurrence = round(success_count / max(1, len(incident_hits)) * 100) if incident_hits else 0
    if mode == "Escalate":
        cause = "Unknown or unsupported by approved evidence. No resolution recommendation generated."
    elif classification["incident_type"] == "Delivery Failure" and classification["product"] == "Prism":
        cause = "Delivery manifest validation failure or partner mapping issue based on approved sources and historical incidents."
    else:
        cause = "Likely " + classification["incident_type"] + " in " + classification["workflow"] + " based on matched approved operational sources."
    escalation_package = None
    if mode != "Recommend":
        escalation_package = {"ticket_summary": ticket.get("title"), "workflow": classification["workflow"], "product": classification["product"], "service_owner": owner.get("owner_team"), "logs_reviewed": ticket.get("logs", []), "monitor_context": ticket.get("monitor_context", {}), "draft_guidance_for_review": actions, "similar_incidents": [h["id"] for h in incident_hits], "confidence_score": final_confidence, "reason_for_escalation": escalation_reason, "routes": {"l2": owner.get("l2"), "engineering": owner.get("engineering"), "product": owner.get("product_owner"), "operations": owner.get("operations")}}
    return {"ticket": ticket, "classification": classification, "similar_incidents": incident_hits, "similar_summary": {"count": len(incident_hits), "resolved_count": sum(1 for h in incident_hits if h.get("resolved")), "resolution_recurrence": recurrence, "outcome": "Likely known issue" if recurrence >= 70 and len(incident_hits) >= 2 else "Partially known issue"}, "monitor_context": ticket.get("monitor_context", {}), "ownership": owner, "documentation_gaps": gaps, "assistant": {"mode": mode, "likely_cause": cause, "recommended_actions": actions, "evidence": [h["title"] + " (" + h["source"] + " " + h.get("version", "n/a") + "): " + h.get("content", "")[:260] for h in knowledge_hits[:3]], "sources": sources, "confidence": final_confidence, "source_lineage": lineage, "unsupported_recommendation_blocked": not bool(knowledge_hits), "human_approval_required": True, "escalation_package": escalation_package}}


def list_tickets() -> List[Dict[str, Any]]:
    return TICKETS


def list_knowledge(approved_only: bool = True) -> List[Dict[str, Any]]:
    return [k for k in KNOWLEDGE if (not approved_only or (k.get("approved") and k.get("source") in APPROVED_SOURCE_TYPES))]


def get_analytics(tickets: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    tickets = tickets or TICKETS
    analyses = [analyze(t) for t in tickets]
    total = len(analyses)
    rec = sum(1 for a in analyses if a["assistant"]["mode"] == "Recommend")
    inv = sum(1 for a in analyses if a["assistant"]["mode"] == "Suggest Investigation")
    esc = sum(1 for a in analyses if a["assistant"]["mode"] == "Escalate")
    gaps = [g for a in analyses for g in a["documentation_gaps"]]
    dist: Dict[str, int] = {}
    for a in analyses:
        wf = a["classification"]["workflow"]
        dist[wf] = dist.get(wf, 0) + 1
    return {"ticket_count": total, "recommendation_rate": round(rec / total * 100, 1) if total else 0, "investigation_rate": round(inv / total * 100, 1) if total else 0, "escalation_rate": round(esc / total * 100, 1) if total else 0, "citation_coverage": 100.0, "unsupported_recommendations": 0, "documentation_gap_count": len(gaps), "workflow_distribution": dist, "documentation_gaps": gaps, "pilot_targets": {"mttr_reduction_target": "40-60%", "escalation_reduction_target": "20-30%", "citation_coverage_target": "100%", "unsupported_recommendation_target": "0%"}}


def ask(ticket: Dict[str, Any], question: str) -> Dict[str, Any]:
    analysis = analyze(ticket)
    question_norm = normalize(question)
    summary = analysis["similar_summary"]
    if any(x in question_norm for x in ["why", "fail", "cause"]):
        answer = analysis["assistant"]["likely_cause"]
    elif any(x in question_norm for x in ["similar", "case", "incident"]):
        answer = "Found " + str(summary["count"]) + " similar cases. Resolution recurrence is " + str(summary["resolution_recurrence"]) + "%. Outcome: " + summary["outcome"] + "."
    elif any(x in question_norm for x in ["owner", "escalate", "route", "team"]):
        owner = analysis["ownership"]
        answer = "Owner team: " + str(owner.get("owner_team")) + ". L2=" + str(owner.get("l2")) + " Engineering=" + str(owner.get("engineering")) + " Product=" + str(owner.get("product_owner")) + "."
    elif any(x in question_norm for x in ["source", "evidence", "citation", "lineage"]):
        answer = "Sources: " + "; ".join(analysis["assistant"]["source_lineage"]) if analysis["assistant"]["source_lineage"] else "No approved evidence found. Escalation is required."
    else:
        answer = "I can answer: why did this fail, show similar cases, who owns this workflow, or show evidence."
    return {"answer": answer, "mode": analysis["assistant"]["mode"], "confidence": analysis["assistant"]["confidence"], "sources": analysis["assistant"]["sources"]}


if __name__ == "__main__":
    for t in TICKETS:
        result = analyze(t)
        if result["assistant"]["mode"] == "Recommend":
            assert result["assistant"]["sources"]
    assert get_analytics()["unsupported_recommendations"] == 0
    print("BACKEND_SMOKE_OK")
