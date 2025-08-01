# app/agent/Company_Summary_Agent.py

import logging
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain_core.tools import Tool

from agent.llm_tools import GSTAPISummaryTool
from agent.summarizer import _summary_llm  # Gemini LLM

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Define the Custom Prompt Template
# ─────────────────────────────────────────────

CUSTOM_REACT_PROMPT = PromptTemplate.from_template(
    """
You are an intelligent agent that performs two tasks based on the provided GST number:
1. Generates a financial summary using GST API data.
2. Opens the company's Indiamart profile page in a browser.

You have access to the following tools:
{tool_names}

Tool Descriptions:
{tools}

⚠ You must strictly follow the ReAct format:
Thought: Explain your next step.
Action: Write the exact tool name (e.g., gst_summary_from_api, open_indiamart_profile)
Action Input: Provide JSON inputs (e.g., 
  - For `gst_summary_from_api`: {{ "gst_number": "27AAAFZ6602R1ZK", "application_id": "your_app_id_here" }}
  - For `open_indiamart_profile`: {{ "gst_number": "27AAAFZ6602R1ZK" }} ← ⚠️ Only GST number!

Rules:
❗ Use only **one tool at a time**.
❗ Do not mix multiple thoughts or actions.
❗ Action and Action Input must always be present.
❗ Use correct input fields for each tool (don't pass `application_id` to `open_indiamart_profile`).

After calling tools, give a clear and professional financial summary using Gemini.

Begin.

Input: {input}
{agent_scratchpad}
"""
)


# ─────────────────────────────────────────────
# Define the Tools
# open_indiamart_profile_tool = OpenIndiamartProfileTool()
gst_api_summary_tool = GSTAPISummaryTool()

tools = [
    # open_indiamart_profile_tool,
    gst_api_summary_tool,
]

# ─────────────────────────────────────────────
agent = create_react_agent(
    llm=_summary_llm,
    tools=tools,
    prompt=CUSTOM_REACT_PROMPT,
)

agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True,
    max_iterations=8,
)


# ─────────────────────────────────────────────
#  Run Agent with GST Number Input
# ─────────────────────────────────────────────
async def run_gst_summary_agent(gst_number: str, application_id: str) -> str:
    try:
        log.info(f"🧠 Running GST Summary Agent for GST: {gst_number}")
        response = await agent_executor.ainvoke(
            {
                "input": {"gst_number": gst_number, "application_id": application_id},
                "agent_scratchpad": "",
            }
        )
        return response.get("output", "No final answer returned.")
    except Exception as e:
        log.exception("❌ Agent execution failed.")
        return f"Error: {e}"
