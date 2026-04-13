from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import PromptTemplate
import json

CR_PROMPT = """
You are a PMO Change Request agent.

Generate ONLY valid JSON. No markdown. No explanation.

Inputs:
Meeting Notes: {meeting}
SOW Document: {sow}
Emails: {emails}

JSON FORMAT:
{{
  "crId": "CR-AUTO-001",
  "title": "",
  "description": "",
  "reasonForChange": "",
  "impactAnalysis": {{
    "scheduleImpact": "",
    "costImpact": "",
    "scopeImpact": ""
  }},
  "recommendation": ""
  "jira_payload": {{
    "project_key": "SCRUM SPRINT 1",
    "issue_type": "Task",
    "summary": "",
    "description": "",
    "labels": ["SCRUM: My Software Team", "change-request"]
  }}
}}
"""

def run_cr_agent(context):
    prompt = PromptTemplate(
        input_variables=["meeting", "sow", "emails"],
        template=CR_PROMPT
    )

    llm = ChatMistralAI(
        model="mistral-small-latest",
        temperature=0,
        max_tokens=1200
    )

    response = (prompt | llm).invoke(context).content
    return json.loads(response)
