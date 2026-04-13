from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import PromptTemplate
import json

PLAN_PROMPT = """
You are a PMO Planning agent.

Return ONLY valid JSON. No markdown. No explanation. No extra text.

Inputs:
Meeting Notes: {meeting}
SOW Document: {sow}
Emails: {emails}
Teams/SharePoint: {teams_sharepoint}

JSON FORMAT (follow exactly):
{
  "planId": "PLAN-AUTO-001",
  "overview": "",
  "milestones": [
    {"name": "", "targetDate": "", "owner": "", "status": ""}
  ],
  "lineItems": [
    {"taskId": "", "taskName": "", "owner": "", "startDate": "", "endDate": "", "status": "", "dependencies": []}
  ],
  "dependencies": [
    {"dependsOn": "", "type": "", "risk": ""}
  ]
}
"""

def run_plan_agent(context):
    prompt = PromptTemplate(
        input_variables=["meeting", "sow", "emails", "teams_sharepoint"],
        template=PLAN_PROMPT
    )

    llm = ChatMistralAI(
        model="mistral-small-latest",
        temperature=0,
        max_tokens=1200
    )

    response = (prompt | llm).invoke(context).content

    # Use your app.py safe_json_loads if you want,
    # but here we keep it simple:
    return json.loads(response)