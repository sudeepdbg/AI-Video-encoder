
import streamlit as st
import backend
st.set_page_config(page_title="MSC Monitor Ops", layout="wide")
def badge(text,mode="neutral"):
    colors={"success":("#DCFCE7","#166534"),"warning":("#FEF9C3","#854D0E"),"danger":("#FEE2E2","#991B1B"),"info":("#DBEAFE","#1E40AF"),"neutral":("#F3F4F6","#374151")}; bg,fg=colors.get(mode,colors["neutral"])
    st.markdown("<span style='background:"+bg+";color:"+fg+";padding:4px 10px;border-radius:999px;font-size:12px;font-weight:600'>"+text+"</span>",unsafe_allow_html=True)
def mode_color(m): return "success" if m=="Recommend" else "warning" if m=="Suggest Investigation" else "danger" if m=="Escalate" else "neutral"
def status_color(s): return {"Open":"info","Assigned":"warning","Escalated":"danger","Auto Resolved":"success"}.get(s,"neutral")
if "tickets" not in st.session_state: st.session_state.tickets=list(backend.list_tickets())
if "manual" not in st.session_state: st.session_state.manual=None
if "chat" not in st.session_state: st.session_state.chat={}
st.title("MSC Monitor Ops - AI Assisted Operations Support")
st.caption("Standalone Streamlit app: UI app.py + backend.py module. No localhost/FastAPI required.")
with st.sidebar:
    st.header("Prototype Controls"); st.success("Standalone Streamlit deployment"); st.caption("backend.py runs in-process")
    if st.button("Refresh App",use_container_width=True): st.rerun()
    st.divider(); st.header("Manual Ticket Analysis")
    with st.form("manual_form"):
        source=st.selectbox("Source",["Manual","ServiceNow","Jira","E-Mail"]); title=st.text_input("Title","Amazon PVC delivery failed")
        desc=st.text_area("Description","Delivery failed from Prism with manifest validation error and missing territory metadata.",height=110)
        logs=st.text_area("Logs, one per line","manifest_validation_failed\nmissing territoryCode\npartner=Amazon PVC",height=90)
        submit=st.form_submit_button("Analyze Without Saving",use_container_width=True)
    if submit:
        st.session_state.manual={"id":"MANUAL","source":source,"status":"Open","title":title,"description":desc,"created":"Manual","requester":"Operator","logs":[x.strip() for x in logs.splitlines() if x.strip()],"monitor_context":{"workflow_status":"Unknown","processing_status":"Manual analysis","current_step":"Operator supplied","partner":"Manual"}}
        st.rerun()
    if st.session_state.manual and st.button("Exit Manual Analysis",use_container_width=True): st.session_state.manual=None; st.rerun()
    with st.expander("Knowledge Library"):
        for k in backend.list_knowledge(True): st.write("- "+k["id"]+" | "+k["source"]+" "+k["version"]+" | "+k["title"])
left,center,right=st.columns([.95,1.55,1.35],gap="large")
with left:
    st.subheader("Ticket Queue")
    if st.session_state.manual:
        badge("Manual Analysis Mode","info"); ticket=st.session_state.manual
    else:
        filt=st.radio("Status Filter",["All","Open","Assigned","Escalated","Auto Resolved"])
        ft=[t for t in st.session_state.tickets if filt=="All" or t.get("status")==filt]
        labels=[t["id"]+" | "+t.get("status","Open")+" | "+t["title"] for t in ft]
        sel=st.selectbox("Select Ticket",labels); ticket=next(t for t in ft if t["id"]==sel.split(" | ")[0])
        st.markdown("#### Queue Items")
        for t in ft:
            with st.container(border=True): st.write("**"+t["id"]+"**"); st.write(t["title"]); badge(t.get("status","Open"),status_color(t.get("status","Open")))
a=backend.analyze(ticket); c=a["classification"]; assistant=a["assistant"]; s=a["similar_summary"]
with center:
    st.subheader("Ticket Investigation")
    with st.container(border=True): st.write("### "+ticket.get("id","Manual")+" - "+ticket.get("title","")); st.write(ticket.get("description","")); st.caption("Source: "+str(ticket.get("source"))+" | Requester: "+str(ticket.get("requester"))+" | Created: "+str(ticket.get("created")))
    st.markdown("#### Classification"); cols=st.columns(5)
    for col,(lab,val) in zip(cols,[("Workflow",c["workflow"]),("Product",c["product"]),("Type",c["incident_type"]),("Severity",c["severity"]),("Classifier",str(c["confidence"])+"%")]): col.metric(lab,val)
    st.markdown("#### Similar Incidents"); m=st.columns(3); m[0].metric("Matches",s["count"]); m[1].metric("Recurrence",str(s["resolution_recurrence"])+"%"); m[2].metric("Outcome",s["outcome"])
    for inc in a["similar_incidents"]:
        with st.expander(inc["id"]+" - "+inc["title"]+" | score="+str(inc["score"])): st.write("Resolution: "+str(inc.get("resolution")))
    st.markdown("#### Monitor Context"); st.json(a["monitor_context"])
    st.markdown("#### Documentation Gap Signals")
    if a["documentation_gaps"]:
        for g in a["documentation_gaps"]: st.warning(g["type"]+": "+g["message"]+" -> "+g["action"])
    else: st.success("No documentation gap detected.")
with right:
    st.subheader("AI Resolution Assistant"); badge(assistant["mode"],mode_color(assistant["mode"])); st.metric("Guidance Confidence",str(assistant["confidence"])+"%")
    if assistant["unsupported_recommendation_blocked"]: st.error("Unsupported recommendation blocked. Escalation required.")
    st.caption("Human approval required for all operational actions."); st.markdown("#### Likely Cause"); st.write(assistant["likely_cause"])
    st.markdown("#### Recommended / Investigation Actions")
    for i,x in enumerate(assistant["recommended_actions"],1): st.write(str(i)+". "+x)
    st.markdown("#### Evidence")
    if assistant["evidence"]:
        for e in assistant["evidence"]: st.info(e)
    else: st.warning("No approved source evidence found.")
    st.markdown("#### Sources, Version, Lineage")
    if assistant["sources"]: st.dataframe(assistant["sources"],use_container_width=True,hide_index=True); st.code("\n".join(assistant["source_lineage"]),language="text")
    else: st.write("No eligible citations.")
    st.markdown("#### Ownership / Escalation"); st.json(assistant["escalation_package"] if assistant["escalation_package"] else a["ownership"])
    st.markdown("#### Conversational Support")
    q=st.text_input("Ask about this ticket","Why did this fail?")
    if st.button("Ask Assistant",use_container_width=True):
        r=backend.ask(ticket,q); st.write(r["answer"]); st.caption("Mode: "+r["mode"]+" | Confidence: "+str(r["confidence"])+"%")
st.divider(); st.subheader("Pilot Analytics"); an=backend.get_analytics(st.session_state.tickets); cols=st.columns(6)
for col,(lab,val) in zip(cols,[("Tickets",an["ticket_count"]),("Recommend",str(an["recommendation_rate"])+"%"),("Investigate",str(an["investigation_rate"])+"%"),("Escalate",str(an["escalation_rate"])+"%"),("Citation",str(an["citation_coverage"])+"%"),("Unsupported Recs",an["unsupported_recommendations"])]): col.metric(lab,val)
with st.expander("Workflow Distribution"): st.json(an["workflow_distribution"])
with st.expander("Documentation Gaps"): st.json(an["documentation_gaps"])
with st.expander("Pilot Targets"): st.json(an["pilot_targets"])
