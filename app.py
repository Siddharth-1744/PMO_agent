import json
import io
import os
from datetime import datetime

import streamlit as st
import pandas as pd
from dotenv import load_dotenv

# --- Optional readers (install packages listed above) ---
from PyPDF2 import PdfReader
from docx import Document
 
from agents.cr_agent import run_cr_agent
from agents.plan_agent import run_plan_agent
from agents.raid_agent import run_raid_agent

load_dotenv()

# ✅ Jira integration imports (Step 4)
from integrations.jira_client import create_jira_issue, test_jira_connection #just added


# -----------------------------
# Page configuration
# -----------------------------
st.set_page_config(
    page_title="PMO Agent",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------
# Small UI helpers
# -----------------------------
def section_title(text: str):
    st.markdown(f"### {text}")

def text_stats(label: str, text: str):
    count = len(text.strip()) if text else 0
    st.caption(f"{label}: **{count} characters**")

def safe_json_loads(maybe_json):
    """
    If the agent returns dict -> return dict
    If it returns JSON string -> parse
    If it returns plain text -> return {"raw_text": "..."}
    """
    if isinstance(maybe_json, dict):
        return maybe_json
    if maybe_json is None:
        return {"raw_text": ""}

    if isinstance(maybe_json, str):
        s = maybe_json.strip()
        if not s:
            return {"raw_text": ""}

        try:
            return json.loads(s)
        except Exception:
            start = s.find("{")
            end = s.rfind("}")
            if start != -1 and end != -1 and end > start:
                candidate = s[start:end + 1]
                try:
                    return json.loads(candidate)
                except Exception:
                    pass

            return {"raw_text": s}

    return {"raw_output": str(maybe_json)}


def read_uploaded_file(uploaded_file) -> str:
    if uploaded_file is None:
        return ""

    name = uploaded_file.name.lower()

    if name.endswith(".txt") or name.endswith(".md"):
        return uploaded_file.getvalue().decode("utf-8", errors="ignore")

    if name.endswith(".json"):
        raw = uploaded_file.getvalue().decode("utf-8", errors="ignore")
        try:
            obj = json.loads(raw)
            return json.dumps(obj, indent=2)
        except Exception:
            return raw

    if name.endswith(".pdf"):
        pdf_bytes = uploaded_file.getvalue()
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages_text = []
        for p in reader.pages:
            pages_text.append(p.extract_text() or "")
        return "\n".join(pages_text).strip()

    if name.endswith(".docx"):
        doc_bytes = uploaded_file.getvalue()
        doc = Document(io.BytesIO(doc_bytes))
        return "\n".join([p.text for p in doc.paragraphs]).strip()

    if name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
        return df.to_csv(index=False)

    if name.endswith(".xlsx"):
        df = pd.read_excel(uploaded_file, engine="openpyxl")
        return df.to_csv(index=False)

    return ""


def copy_to_clipboard_button(text: str, label="📋 Copy JSON to Clipboard"):
    safe_text = text.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
    html = f"""
    <div style="margin-top: 6px;">
      <button id="copyBtn"
        style="
          background:#111827;color:white;border:none;padding:10px 14px;
          border-radius:10px;cursor:pointer;font-weight:600;">
        {label}
      </button>
      <span id="copyMsg" style="margin-left:10px;color:#16a34a;font-weight:600;"></span>
    </div>
    <script>
      const btn = document.getElementById("copyBtn");
      const msg = document.getElementById("copyMsg");
      const text = `{safe_text}`;
      btn.addEventListener("click", async () => {{
        try {{
          await navigator.clipboard.writeText(text);
          msg.textContent = "Copied!";
          setTimeout(() => msg.textContent = "", 1500);
        }} catch (e) {{
          msg.textContent = "Copy failed (browser blocked).";
          setTimeout(() => msg.textContent = "", 2000);
        }}
      }});
    </script>
    """
    st.components.v1.html(html, height=60)


# -----------------------------
# Session state init
# -----------------------------
if "history" not in st.session_state:
    st.session_state.history = []

if "meeting_text" not in st.session_state:
    st.session_state.meeting_text = ""
if "sow_text" not in st.session_state:
    st.session_state.sow_text = ""
if "emails_text" not in st.session_state:
    st.session_state.emails_text = ""

# -----------------------------
# Header
# -----------------------------
st.markdown(
    """
    <div style="display:flex;align-items:center;justify-content:space-between;">
      <div>
        <h1 style="margin-bottom:0;">📊 PMO Agent Dashboard</h1>
        <p style="margin-top:6px;color:#6b7280;">Upload files or paste text • Run CR / Plan / RAID • Download structured outputs</p>
      </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.divider()

# -----------------------------
# Sidebar controls
# -----------------------------
with st.sidebar:
    st.markdown("## ⚙️ Control Panel")

    agent_type = st.radio(
        "Choose PMO Task",
        options=["Change Request (CR)", "Project Plan", "RAID"],
        index=0
    )

    st.markdown("---")

    st.markdown("### 🔧 Options")
    merge_inputs = st.checkbox("Merge all inputs into one context text", value=False)
    show_previews = st.checkbox("Show input previews", value=True)
    keep_history = st.checkbox("Keep run history", value=True)

    # ✅ Jira Step 4 UI controls (only for CR)
    st.markdown("---")
    create_jira = False
    if agent_type == "Change Request (CR)":
        create_jira = st.checkbox("🧩 Create Jira ticket after CR output", value=True)

    if st.button("🔌 Test Jira Connection", use_container_width=True):
        try:
            me = test_jira_connection()
            st.success(f"✅ Jira connected as: {me.get('displayName', 'Unknown User')}")
        except Exception as e:
            st.error(str(e))

    st.markdown("---")

    run = st.button("🚀 Run PMO Agent", use_container_width=True)
    clear_all = st.button("🧹 Clear All Inputs", use_container_width=True)

    st.markdown("---")

    load_sample = st.button("📋 Load Sample Meeting Notes", use_container_width=True)


# -----------------------------
# Buttons actions
# -----------------------------
if clear_all:
    st.session_state.meeting_text = ""
    st.session_state.sow_text = ""
    st.session_state.emails_text = ""
    st.toast("Cleared inputs ✅")

if load_sample:
    st.session_state.meeting_text = (
        "The meeting started with a discussion on a new change request related to the reporting module. "
        "The client requested a new real-time dashboard refreshing every five minutes. "
        "Backend API optimization and a new frontend UI component are required. "
        "Estimated effort is three additional sprints, causing a four-week delay. "
        "Risks include performance degradation at peak load and increased cloud costs. "
        "Decision: proceed subject to approval of revised cost and timeline. "
        "Updated CR document and estimates will be shared by end of week for sign-off."
    )
    st.session_state.sow_text = (
        "The CR (Change Request) Agent is an AI-powered component within the PMO Agent ecosystem designed "
        "to automatically generate structured change requests by analyzing various project inputs such as "
        "meeting recordings, Statement of Work (SOW) documents, kickoff meeting notes, email threads, and "
        "collaboration platforms like Microsoft Teams and SharePoint. Its primary objective is to streamline "
        "the change management process by identifying deviations from the original scope, summarizing required "
        "changes, and reducing the manual effort typically involved in documenting and tracking these updates. "
        "The agent processes both structured and unstructured data, converts meeting recordings into usable "
        "transcripts, and extracts relevant context to detect explicit and implicit change requirements.\n\n"

        "Based on this analysis, the CR Agent generates standardized change request outputs that include key "
        "elements such as change title, description, reason for change, impact on scope, timeline and deliverables, "
        "priority, dependencies, and draft approval status. It also performs a preliminary impact analysis to "
        "highlight potential risks and flag high-impact changes. Once generated, these change requests can be "
        "reviewed and validated by users before being automatically integrated into project tracking systems like "
        "Jira, ensuring traceability and alignment with the original scope. The system supports API-based integration "
        "for creating and updating CR tickets, enabling seamless synchronization between the agent and project "
        "management workflows.\n\n"

        "Functionally, the agent is expected to accurately interpret inputs, detect scope changes, generate structured "
        "outputs, and support user interaction for review and approval. Non-functional expectations include high "
        "performance with quick processing times, scalability across multiple projects, strong data security, and "
        "high system availability. While the agent significantly enhances efficiency, it assumes that input data is "
        "accessible and of sufficient quality, and that users will validate outputs before submission. Features such "
        "as manual approval workflows, advanced financial forecasting, and real-time meeting intervention are "
        "currently out of scope but may be considered for future enhancements. Overall, the CR Agent aims to improve "
        "accuracy, speed, and consistency in managing project changes while integrating seamlessly into existing PMO "
        "tools and processes."
    )

    st.toast("Sample meeting + SOW loaded ✅")


# -----------------------------
# Main layout tabs
# -----------------------------
tab_inputs, tab_output, tab_history = st.tabs(["📝 Inputs", "✅ Output", "🕘 History"])


# -----------------------------
# Inputs Tab
# -----------------------------
with tab_inputs:
    section_title("PMO Inputs (Paste or Upload)")

    c1, c2, c3 = st.columns(3, gap="large")

    with c1:
        st.markdown("#### Meeting Notes")
        meeting_files = st.file_uploader(
            "Upload files (txt, pdf, docx, json, md)",
            type=["txt", "pdf", "docx", "json", "md"],
            accept_multiple_files=True,
            key="meeting_uploader"
        )
        meeting_text = st.text_area(
            "Or paste meeting notes here",
            height=220,
            value=st.session_state.meeting_text,
            placeholder="Paste meeting discussion notes here..."
        )
        st.session_state.meeting_text = meeting_text
        text_stats("Meeting notes", meeting_text)

    with c2:
        st.markdown("#### SOW / Scope Document")
        sow_files = st.file_uploader(
            "Upload files (txt, pdf, docx, xlsx, csv, json, md)",
            type=["txt", "pdf", "docx", "xlsx", "csv", "json", "md"],
            accept_multiple_files=True,
            key="sow_uploader"
        )
        sow_text = st.text_area(
            "Or paste SOW/scope here",
            height=220,
            value=st.session_state.sow_text,
            placeholder="Paste SOW or scope baseline here..."
        )
        st.session_state.sow_text = sow_text
        text_stats("SOW/Scope", sow_text)

    with c3:
        st.markdown("#### Email Threads")
        email_files = st.file_uploader(
            "Upload files (txt, pdf, docx, json, md)",
            type=["txt", "pdf", "docx", "json", "md"],
            accept_multiple_files=True,
            key="emails_uploader"
        )
        emails_text = st.text_area(
            "Or paste email threads here",
            height=220,
            value=st.session_state.emails_text,
            placeholder="Paste important email discussions here..."
        )
        st.session_state.emails_text = emails_text
        text_stats("Email threads", emails_text)

    meeting_from_files = "\n\n".join([read_uploaded_file(f) for f in (meeting_files or [])]).strip()
    sow_from_files = "\n\n".join([read_uploaded_file(f) for f in (sow_files or [])]).strip()
    emails_from_files = "\n\n".join([read_uploaded_file(f) for f in (email_files or [])]).strip()

    meeting_final = "\n\n".join([meeting_from_files, st.session_state.meeting_text]).strip()
    sow_final = "\n\n".join([sow_from_files, st.session_state.sow_text]).strip()
    emails_final = "\n\n".join([emails_from_files, st.session_state.emails_text]).strip()

    st.markdown("---")
    st.markdown("#### ✅ Effective Inputs (what the agent will actually see)")
    colA, colB = st.columns([2, 1], gap="large")

    with colA:
        if show_previews:
            with st.expander("Preview combined Meeting Notes"):
                st.write(meeting_final if meeting_final else "— empty —")
            with st.expander("Preview combined SOW / Scope"):
                st.write(sow_final if sow_final else "— empty —")
            with st.expander("Preview combined Email Threads"):
                st.write(emails_final if emails_final else "— empty —")

    with colB:
        st.markdown("##### Input health")
        st.metric("Meeting chars", len(meeting_final))
        st.metric("SOW chars", len(sow_final))
        st.metric("Emails chars", len(emails_final))
        st.caption("Tip: Extremely large inputs may slow down responses or cause truncation.")

    if merge_inputs:
        merged = (
            f"MEETING NOTES:\n{meeting_final}\n\n"
            f"SOW / SCOPE:\n{sow_final}\n\n"
            f"EMAIL THREADS:\n{emails_final}"
        ).strip()
        context = {"context": merged}
    else:
        context = {"meeting": meeting_final, "sow": sow_final, "emails": emails_final}


# -----------------------------
# Run logic
# -----------------------------
result_payload = None
error_payload = None

# ✅ Jira run results (Step 4)
jira_result = None
jira_error = None

if run:
    has_any = False
    if merge_inputs:
        has_any = bool(context.get("context", "").strip())
    else:
        has_any = bool(context["meeting"].strip() or context["sow"].strip() or context["emails"].strip())

    if not has_any:
        error_payload = "Please provide at least one input (paste text or upload file)."
    else:
        with st.spinner("PMO Agent is working..."):
            try:
                if agent_type == "Change Request (CR)":
                    raw = run_cr_agent(context)
                    agent_invoked = "CR_AGENT"
                elif agent_type == "Project Plan":
                    raw = run_plan_agent(context)
                    agent_invoked = "PLAN_AGENT"
                else:
                    raw = run_raid_agent(context)
                    agent_invoked = "RAID_AGENT"

                parsed = safe_json_loads(raw)

                result_payload = {
                    "pmoAgent": "PMO_AGENT_V1",
                    "agentInvoked": agent_invoked,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "inputMode": "MERGED" if merge_inputs else "SEPARATE",
                    "output": parsed
                }

                # ✅ Step 4: Create Jira ticket automatically after CR output
                # Jira Cloud issue creation uses POST /rest/api/3/issue with Basic Auth (email + API token). [2](https://myoffice.accenture.com/personal/gundeti_siddharth_accenture_com/Documents/Microsoft%20Copilot%20Chat%20Files/result.json)[3](https://myoffice.accenture.com/personal/gundeti_siddharth_accenture_com/Documents/Microsoft%20Copilot%20Chat%20Files/main.py)
                if agent_type == "Change Request (CR)" and create_jira:
                    try:
                        if isinstance(parsed, dict) and "jira_payload" in parsed:
                            jira_payload = parsed["jira_payload"]
                        else:
                            # ✅ Build jira_payload from existing CR fields (fallback)
                            jira_payload = {
                                "project_key": os.getenv("JIRA_PROJECT_KEY", ""),
                                "issue_type": os.getenv("JIRA_ISSUE_TYPE", "Task"),
                                "summary": parsed.get("title", "PMO Change Request"),
                                "description": parsed.get("description", ""),
                                "labels": ["pmo", "change-request"]
                            }

                        jira_result = create_jira_issue(jira_payload)
                    except Exception as je:
                        jira_error = str(je)

                    # Attach Jira result into the downloaded JSON (optional but useful)
                    result_payload["jira"] = {
                        "enabled": True,
                        "created": jira_result is not None,
                        "result": jira_result,
                        "error": jira_error
                    }

                # ✅ ✅ ✅ POPUP (existing) ✅ ✅ ✅
                st.toast("✅ Output file generated successfully!", icon="✅")

                if keep_history:
                    st.session_state.history.insert(0, result_payload)

            except Exception as e:
                error_payload = str(e)


# -----------------------------
# Output Tab
# -----------------------------
with tab_output:
    section_title("Output")

    if error_payload:
        st.error(f"❌ Error: {error_payload}")
        st.info("Tip: If this error is JSONDecodeError, your agent returned plain text instead of JSON. We can enforce strict JSON in the agent prompt.")
    elif result_payload:
        st.success("✅ PMO Agent execution completed")

        # ✅ Show Jira result if created
        if jira_result:
            issue_key = jira_result.get("key")
            base = (os.getenv("JIRA_BASE_URL") or "").rstrip("/")
            st.success(f"✅ Jira ticket created: {issue_key}")
            if base and issue_key:
                st.markdown(f"🔗 Open in Jira: {base}/browse/{issue_key}")
        if jira_error:
            st.error(f"❌ Jira ticket creation failed: {jira_error}")

        st.markdown("#### Structured Output (JSON)")
        st.json(result_payload)

        json_text = json.dumps(result_payload, indent=2)

        copy_to_clipboard_button(json_text)

        st.markdown("#### Downloads")
        cdl1, cdl2 = st.columns(2)

        with cdl1:
            st.download_button(
                label="📥 Download JSON",
                data=json_text,
                file_name="pmo_output.json",
                mime="application/json",
                use_container_width=True
            )

        with cdl2:
            st.download_button(
                label="📥 Download Output as TXT",
                data=json_text,
                file_name="pmo_output.txt",
                mime="text/plain",
                use_container_width=True
            )

        if isinstance(result_payload.get("output"), dict) and "raw_text" in result_payload["output"]:
            st.warning("Model returned plain text (not strict JSON). Showing it below:")
            st.code(result_payload["output"]["raw_text"], language="text")

    else:
        st.info("Run an agent to see output here ✅")


# -----------------------------
# History Tab
# -----------------------------
with tab_history:
    section_title("Run History")

    if not st.session_state.history:
        st.info("No history yet. Run an agent to store results here.")
    else:
        for idx, item in enumerate(st.session_state.history[:10]):
            with st.expander(f"#{idx+1} • {item['timestamp']} • {item['agentInvoked']}"):
                st.json(item)
                st.download_button(
                    label="Download this run as JSON",
                    data=json.dumps(item, indent=2),
                    file_name=f"pmo_output_{idx+1}.json",
                    mime="application/json"
                )

        if st.button("🗑️ Clear History"):
            st.session_state.history = []
            st.toast("History cleared ✅")
