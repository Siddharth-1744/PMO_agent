from agents.cr_agent import run_cr_agent
from agents.plan_agent import run_plan_agent
from agents.raid_agent import run_raid_agent
import json
from dotenv import load_dotenv
load_dotenv()

from integrations.jira_client import create_jira_issue, test_jira_connection # just added

def load_inputs():
    def read(path):
        try:
            return open(path, encoding="utf-8").read()
        except:
            return ""

    return {
        "meeting": read("input/meeting.txt"),
        "sow": read("input/sow.txt"),
        "emails": read("input/emails.txt")
    }

context = load_inputs()

print("Select PMO Task")
print("1 - Change Request (CR)")
print("2 - Project Plan")
print("3 - RAID")

choice = input("Enter choice (1/2/3): ")

if choice == "1":
    output = run_cr_agent(context)
    agent = "CR_AGENT"
elif choice == "2":
    output = run_plan_agent(context)
    agent = "PLAN_AGENT"
elif choice == "3":
    output = run_raid_agent(context)
    agent = "RAID_AGENT"
else:
    raise ValueError("Invalid selection")

final_output = {
    "pmoAgent": "PMO_AGENT_V1",
    "agentInvoked": agent,
    "inputsUsed": list(context.keys()),
    "output": output
}

with open("output/result.json", "w") as f:
    json.dump(final_output, f, indent=2)

print("✅ PMO JSON output generated → output/result.json")