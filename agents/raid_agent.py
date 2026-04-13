from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import PromptTemplate
import json

RAID_PROMPT = """
You are a PMO RAID agent.

Return ONLY valid JSON. No markdown. No explanation. No extra text.

Inputs:
Meeting Notes: {meeting}
SOW Document: {sow}
Emails: {emails}
Teams/SharePoint: {teams_sharepoint}

JSON FORMAT (follow exactly):
{
  "raidId": "RAID-AUTO-001",
  "risks": [
    {"id": "", "description": "", "owner": "", "probability": "", "impact": "", "mitigation": "", "status": ""}
  ],
  "assumptions": [
    {"id": "", "description": "", "owner": "", "status": ""}
  ],
  "issues": [
    {"id": "", "description": "", "owner": "", "severity": "", "resolution": "", "status": ""}
  ],
  "dependencies": [
    {"id": "", "description": "", "dependsOn": "", "owner": "", "status": ""}
  ]
}
"""

def run_raid_agent(context):
    prompt = PromptTemplate(
        input_variables=["meeting", "sow", "emails", "teams_sharepoint"],
        template=RAID_PROMPT
    )

    llm = ChatMistralAI(
        model="mistral-small-latest",
        temperature=0,
        max_tokens=1200
    )

    response = (prompt | llm).invoke(context).content
    return json.loads(response)