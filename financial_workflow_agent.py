import logging
from typing import List

from agent import summarizer as summarizer_module
from agent.llm_tools import (
    FinancialSummarizerTool,
    GeminiFileQATool,
    PersistFinancialDataTool,
)
from langchain import hub
from langchain.agents import AgentExecutor, create_react_agent
from pydantic import BaseModel

log = logging.getLogger(__name__)


class FinancialAgentInput(BaseModel):
    pnl_s3_urls: List[str]
    bs_s3_urls: List[str]
    application_id: str
    company_gst: str


agent_llm = summarizer_module._summary_llm
tools = [GeminiFileQATool(), PersistFinancialDataTool(), FinancialSummarizerTool()]

prompt = hub.pull("hwchase17/react")

prompt.input_variables = [
    "pnl_s3_urls",
    "bs_s3_urls",
    "application_id",
    "company_gst",
    "agent_scratchpad",
    "tools",
    "tool_names",
]

prompt.template = """You are an expert financial analyst agent. Your purpose is to process financial documents, save the data, and create a summary.

**YOUR WORKFLOW:**
1.  **EXTRACT:** You will be given JSON lists of S3 URLs for PNL and Balance Sheet documents. You must process EACH URL from both lists using the `FinancialDocumentExtractor` tool.
    - For PNL URLs, set `doc_type` to "pnl-sheet".
    - For Balance Sheet URLs, set `doc_type` to "balance-sheet".
    - Collect all JSON data returned by the tool. If you get an error, retry once.
2.  **PERSIST:** After successfully extracting data from ALL documents, you MUST use the `PersistFinancialDataTool` ONCE.
    - Combine all extracted PNL JSON objects into a single JSON array string.
    - Combine all extracted Balance Sheet JSON objects into a single JSON array string.
    - Pass these arrays and other required IDs to the tool.
    -**PERSIST step – required Action Input**
    ```json
    Action: PersistFinancialDataTool
    Action Input: {{"pnl_json_list_str": "[{{...}}]",       // ← PNL array **as a string**
                "bs_json_list_str" : "[{{...}}]",       // ← BS array **as a string**
                "application_id"   : "ApplicationId",
                "company_gst"      : "GstNumber"}}
3.  **SUMMARIZE:** After the data has been persisted successfully, you MUST use the `FinancialSummarizerTool` ONCE to generate the final report.
    - Combine all extracted PNL JSON objects into a single JSON array string.
    - Combine all extracted Balance Sheet JSON objects into a single JSON array string.
    - Pass these arrays and the application ID to the tool.
    -**SUMMARIZE step – required Action Input**
    ```json
    Action: FinancialSummarizerTool
    Action Input: {{"pnl_json_list_str": "[{{...}}]",       // ← PNL array **as a string**
                "bs_json_list_str" : "[{{...}}]",       // ← BS array **as a string**
                "application_id"   : "ApplicationId"}}

**IMPORTANT NOTE ON FORMATTING:**

When calling a tool, always pass the `Action Input` as a valid **JSON object**, matching the required fields exactly.

✅ Correct:
Action: gemini_pdf_extractor  
Action Input: {{"s3_url": "https://example.com/sample.pdf", "doc_type": "pnl-sheet"}}

❌ Incorrect:
Action Input: "s3_url": "\"s3_url\": \"https://example.com/sample.pdf\", \"doc_type\": \"pnl-sheet\""


You have access to the following tools:
{tools}

Use the following format for your thought process:

Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action, as a valid JSON object
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I have completed all steps and have the final summary.
Final Answer: The final result of the entire workflow.

Begin!

{input}
{agent_scratchpad}"""

agent = create_react_agent(agent_llm, tools, prompt)

agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True,
    max_iterations=20,
)


async def run_financial_agent(
    pnl_s3_urls: List[str], bs_s3_urls: List[str], application_id: str, company_gst: str
) -> str:
    """
    Runs the financial agent to process documents and generate a summary.
    """
    log.info(
        f"Starting financial agent for AppID: {application_id}, GST: {company_gst}"
    )

    try:
        # 1. Validate the input arguments
        validated_inputs = FinancialAgentInput(
            pnl_s3_urls=pnl_s3_urls,
            bs_s3_urls=bs_s3_urls,
            application_id=application_id,
            company_gst=company_gst,
        )

        # 2. Prepare the input dictionary for the agent executor
        agent_input = {
            "input": {
                "pnl_s3_urls": validated_inputs.pnl_s3_urls,
                "bs_s3_urls": validated_inputs.bs_s3_urls,
                "application_id": validated_inputs.application_id,
                "company_gst": validated_inputs.company_gst,
            },
            "agent_scratchpad": "",
        }

        # 3. Invoke the agent with the correctly formatted input
        response = await agent_executor.ainvoke(agent_input)

        final_answer = response.get("output", "Agent did not return a final answer.")
        log.info(
            f"Agent for AppID {application_id} finished. Final Answer: {final_answer}"
        )
        return final_answer
    except Exception as e:
        log.exception(
            f"CRITICAL: Agent execution failed for AppID {application_id}. Error: {e}"
        )
        return f"Agent failed with a critical error: {e}"
