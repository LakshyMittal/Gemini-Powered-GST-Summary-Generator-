"""
LangChain chain that summarises parsed JSON data – no file input required.
"""

import json
import logging  # Added logging

import config
from agent import prompts
from database.database_config import NetworkConnections
from database.los_application_tracker import LosApplicationTrackerDatabase
from google.oauth2 import service_account  # NEW
from langchain.prompts import ChatPromptTemplate
from langchain_google_vertexai import ChatVertexAI  # type: ignore


_db_connection = NetworkConnections()


_los_application_tracker_db = LosApplicationTrackerDatabase(_db_connection)

log = logging.getLogger(__name__)

_creds = None
if config.GOOGLE_KEY_FILE:
    _creds = service_account.Credentials.from_service_account_file(
        config.GOOGLE_KEY_FILE,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )


_summary_llm = ChatVertexAI(
    model_name=config.VERTEX_MODEL,
    temperature=config.TEMPERATURE,
    project=config.PROJECT_ID,
    location=config.LOCATION,
    credentials=_creds,
)

_summary_template = ChatPromptTemplate.from_messages(
    [
        ("system", "{summary_prompt}"),
        (
            "human",
            """ For the data below **Just provide the Markdown not the thinking**
            Here is Profit-and-Loss data JSON:
            {pnl}

            Here is Balance-sheet data JSON:
            {bs}
            """,
        ),
    ]
)


async def create_summary(
    pnl_data: list, bs_data: list, application_id: str, gst_number: str
) -> str:
    """
    Creates a summary using Vertex AI based on P&L and Balance Sheet data,
    then updates the LOS application tracker with the generated summary.

    Args:
        pnl_data (list): List of P&L data dictionaries.
        bs_data (list): List of Balance Sheet data dictionaries.
        application_id (str): The ID of the LOS application to update.

    Returns:
        str: The generated summary text.
    """
    log.info(f"Generating summary for application ID: {application_id}")
    try:
        # Invoke the LLM to generate the summary
        rtn = await _summary_llm.ainvoke(  # Use ainvoke for async
            _summary_template.format_prompt(
                pnl=json.dumps(pnl_data, indent=2) if pnl_data else "[]",
                bs=json.dumps(bs_data, indent=2) if bs_data else "[]",
                summary_prompt=prompts.SUMMARY_PROMPT,
            ).to_messages()
        )
        text = rtn.content
        log.info(
            f"Summary generated successfully for application ID: {application_id}. Summary: {text[:100]}..."
        )
        text = text.strip("```json").strip("```").strip()

        await _los_application_tracker_db.update_los_application_tracker_by_identifier(
            application_id, {"balanceSheetSummary": text}
        )
        log.info(
            f"LOS application tracker updated with summary for ID: {application_id}"
        )
        return text
    except Exception as e:
        log.exception(
            f"Error creating balance sheet summary for application ID {application_id}. Falling back to GST summary. Details: {e}"
        )
