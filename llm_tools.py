# llm_tools.py

"""
Custom LangChain tools for the financial agent.
1.  GeminiFileQATool: Extracts data from a single PDF document.
2.  PersistFinancialDataTool: Saves extracted data to the database.
3.  FinancialSummarizerTool: Generates a final summary from the data.
"""
import asyncio
import json
import logging
import uuid
from typing import Type  # add at top of file
from typing import Any, Dict, Union
import httpx  # Import httpx for async requests
import requests
import vertexai
from agent import prompts, summarizer
from database.los_application_tracker import LosApplicationTrackerDatabase
import config

from database.balance_sheet_data import BalanceSheetDataDatabase
from database.database_config import NetworkConnections

from database.pnl_sheet_data import ProfitAndLossSheetDatabase
from google.cloud import storage
from google.oauth2 import service_account  # ← NEW
from langchain.tools import BaseTool
from models.balance_sheet import BalanceSheetData as ModelBalanceSheetData
from models.pnl_sheet import ProfitAndLossSheetData as ModelPnLSheetData
from pydantic import BaseModel, Field, ValidationError, model_validator, validator
from requests import RequestException
from vertexai.generative_models import GenerationConfig, GenerativeModel
from agent.prompts import API_SUMMARY_PROMPT


# from app.database.gst_data import GSTDataDatabase


from langchain.tools.base import BaseTool
from typing import Optional, Type
from pydantic import BaseModel
import webbrowser
from .tool_utils import _normalise_inputs
from dotenv import load_dotenv
from typing import Literal
from langchain.tools import BaseTool
import httpx
import os

_db_connection = NetworkConnections()  # Instantiate NetworkConnections once

load_dotenv()
log = logging.getLogger(__name__)

_los_application_tracker_db = LosApplicationTrackerDatabase(_db_connection)


_creds = None
if config.GOOGLE_KEY_FILE:
    _creds = service_account.Credentials.from_service_account_file(
        config.GOOGLE_KEY_FILE,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )

vertexai.init(
    project=config.PROJECT_ID,
    location=config.LOCATION,
    credentials=_creds,
)

_vertex_model = GenerativeModel(
    model_name=config.VERTEX_MODEL,
    generation_config=GenerationConfig(temperature=0.2),
)

_storage = storage.Client(credentials=_creds, project=config.PROJECT_ID)
_bucket = _storage.bucket(config.GCS_BUCKET)

# --- Input Schemas ---


class FileQAInput(BaseModel):
    """Input schema for the GeminiFileQATool."""

    s3_url: str = Field(
        ..., description="A pre-signed S3 URL pointing to the PDF financial document."
    )
    doc_type: str = Field(
        ...,
        description='The type of the document. Must be either "balance-sheet" or "pnl-sheet".',
    )

    @model_validator(mode="before")
    def _unpack_stringified_json(cls, values: dict):
        raw = values.get("s3_url")
        if isinstance(raw, str):
            text = raw.strip()

            if text.startswith('"') and text.endswith('"'):
                try:
                    text = json.loads(text)
                except Exception:
                    pass

            if text.startswith("{") and "doc_type" not in values:
                try:
                    inner = json.loads(text)
                    values["s3_url"] = inner["s3_url"]
                    values["doc_type"] = inner["doc_type"]
                except Exception:
                    pass
        return values


class PersistDataInput(BaseModel):
    """Input schema for the PersistFinancialDataTool."""

    pnl_json_list_str: str = Field(
        description="A JSON string representing a list of extracted PNL data objects."
    )
    bs_json_list_str: str = Field(
        description="A JSON string representing a list of extracted Balance Sheet data objects."
    )
    application_id: str = Field(
        description="The application ID associated with this data."
    )
    company_gst: str = Field(description="The GST number of the company.")

    # Updated validator to be more robust and explicit
    @model_validator(mode="before")
    @classmethod
    def _handle_stringified_json_input(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Handles the case where the entire tool input JSON is stringified
            # and passed as the value of 'pnl_json_list_str',
            # and 'pnl_json_list_str' is the only key in the input dict.
            if len(data) == 1 and "pnl_json_list_str" in data:
                pnl_str_val = data.get("pnl_json_list_str")
                if isinstance(pnl_str_val, str) and pnl_str_val.strip().startswith("{"):
                    try:
                        unpacked_data = json.loads(pnl_str_val)
                        if isinstance(unpacked_data, dict):
                            # If unpacking is successful, use the unpacked data for validation
                            return unpacked_data
                    except json.JSONDecodeError:
                        # If it's not valid JSON, let Pydantic try to validate `data` as is.
                        pass
        # If not the specific nested structure, or if input is not a dict,
        # return the data as is for standard Pydantic validation.
        return data


class SummarizerInput(BaseModel):
    pnl_json_list_str: str = Field(
        description="A JSON string of all extracted PNL data."
    )
    bs_json_list_str: str = Field(
        description="A JSON string of all extracted Balance Sheet data."
    )
    application_id: str = Field(
        description="The application ID to associate the summary with."
    )

    @model_validator(mode="before")
    @classmethod
    def _handle_stringified_json_input_summarizer(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Handles the case where the entire tool input JSON is stringified
            # and passed as the value of the first field (e.g., 'pnl_json_list_str'),
            # and that first field is the only key in the input dict.
            if len(data) == 1:
                first_field_name = next(iter(cls.model_fields.keys()), None)
                if first_field_name and first_field_name in data:
                    potential_json_str = data.get(first_field_name)
                    if isinstance(
                        potential_json_str, str
                    ) and potential_json_str.strip().startswith("{"):
                        try:
                            unpacked_data = json.loads(potential_json_str)
                            if isinstance(unpacked_data, dict):
                                # If unpacking is successful, use the unpacked data for validation
                                return unpacked_data
                        except json.JSONDecodeError:
                            # If it's not valid JSON, let Pydantic try to validate `data` as is.
                            pass
        return data


# --- Tool Definitions ---


class GeminiFileQATool(BaseTool):
    """
    A LangChain Tool that downloads a PDF from an S3 URL, uploads it to Google Cloud
    Storage, calls the Gemini model with the document to extract structured data,
    and returns the resulting JSON as a string.
    """

    name: str = "gemini_pdf_extractor"
    description: str = (
        "Extracts structured JSON data from a financial document (PNL or Balance Sheet). "
        "Input must be a pre-signed S3 URL for the PDF and the document type."
    )
    args_schema: Type[BaseModel] = FileQAInput

    def _run(self, *args, **kwargs) -> str:
        kwargs = _normalise_inputs(*args, **kwargs)
        s3_url = kwargs.get("s3_url")
        doc_type = kwargs.get("doc_type")
        """
        The core logic of the tool.
        This synchronous method is called by the LangChain agent.
        """
        print(f"Tool starting for doc_type: '{doc_type}' at URL: {s3_url}")
        if not s3_url or not doc_type:
            return (
                'Error: "s3_url" and "doc_type" are required. '
                f"Received s3_url={s3_url!r}, doc_type={doc_type!r}"
            )
        try:
            # 1. Download the file from the pre-signed S3 URL
            print(f"Step 1: Downloading file from S3 URL...")
            pdf_bytes = requests.get(s3_url, timeout=60).content
            print("Step 1: Download complete.")

            # 2. Upload the file to a temporary folder in Google Cloud Storage (GCS)
            object_name = f"tmp/{uuid.uuid4()}.pdf"
            blob = _bucket.blob(object_name)
            print(f"Step 2: Uploading file to GCS as '{object_name}'...")
            blob.upload_from_string(
                pdf_bytes, content_type="application/pdf", timeout=120
            )
            gs_uri = f"{config.GS_URI_PREFIX}/{object_name}"
            print(f"Step 2: Upload to GCS complete. URI: {gs_uri}")

            # 3. Generate the prompt for the Gemini model based on the document type
            print("Step 3: Selecting prompt...")
            sys_prompt = (
                prompts.BALANCE_SHEET_PROMPT
                if doc_type == "balance-sheet"
                else prompts.PNL_PROMPT
            )
            print(f"Step 3: Prompt selected for '{doc_type}'.")

            # 4. Call the Vertex AI Gemini model with the prompt and file reference
            print("Step 4: Calling Gemini model...")
            resp = _vertex_model.generate_content(
                contents=[
                    {"role": "user", "parts": [{"text": prompts.GIVE_OUTPUT_STRING}]},
                    {
                        "role": "user",
                        "parts": [
                            {"text": sys_prompt.strip()},
                            {
                                "file_data": {
                                    "file_uri": gs_uri,
                                    "mime_type": "application/pdf",
                                }
                            },
                        ],
                    },
                ]
            )
            print("Step 4: Gemini call complete.")

            # 5. Process the response and clean up the temporary file
            # Extract text, remove markdown code fences, and strip whitespace
            text = (
                resp.candidates[0]
                .content.parts[0]
                .text.strip()
                .strip("```json")
                .strip("```")
                .strip()
                if resp.candidates
                else ""
            )

            print("Step 5: Cleaning up temporary GCS file...")
            try:
                blob.delete()
                print("Step 5: Cleanup complete.")
            except Exception as e:
                print(f"Warning: Could not delete temporary file {gs_uri}. Error: {e}")
                pass  # Continue even if cleanup fails

            return text

        except RequestException as e:
            return f"Error: Failed to download file from S3 URL: {e}"
        except Exception as e:
            # Catch any other potential errors during the process
            return f"An unexpected error occurred: {e}"

    async def _arun(self, *args, **kwargs) -> str:
        kwargs = _normalise_inputs(*args, **kwargs)
        s3_url = kwargs.get("s3_url")
        doc_type = kwargs.get("doc_type")
        """
        The core asynchronous logic of the tool.
        This asynchronous method is called by the LangChain agent executor.
        """
        log.info(f"Tool starting async for doc_type: '{doc_type}' at URL: {s3_url}")
        if not s3_url or not doc_type:
            return (
                'Error: "s3_url" and "doc_type" are required. '
                f"Received s3_url={s3_url!r}, doc_type={doc_type!r}"
            )
        try:
            # 1. Download the file from the pre-signed S3 URL asynchronously
            log.info(f"Step 1: Downloading file from S3 URL asynchronously...")
            async with httpx.AsyncClient() as client:
                response = await client.get(s3_url, timeout=60)
                response.raise_for_status()  # Raise an exception for bad status codes
                pdf_bytes = response.content
            log.info(f"Step 1: Download complete. Downloaded {len(pdf_bytes)} bytes.")

            # 2. Upload the file to a temporary folder in Google Cloud Storage (GCS) asynchronously
            object_name = f"tmp/{uuid.uuid4()}.pdf"
            blob = _bucket.blob(object_name)
            log.info(
                f"Step 2: Uploading file to GCS as '{object_name}' asynchronously..."
            )
            await asyncio.to_thread(
                blob.upload_from_string,
                pdf_bytes,
                content_type="application/pdf",
                timeout=120,
            )
            gs_uri = f"{config.GS_URI_PREFIX}/{object_name}"
            log.info(f"Step 2: Upload to GCS complete. URI: {gs_uri}")

            # 3. Generate the prompt for the Gemini model based on the document type
            log.info("Step 3: Selecting prompt...")
            sys_prompt = (
                prompts.BALANCE_SHEET_PROMPT
                if doc_type == "balance-sheet"
                else prompts.PNL_PROMPT
            )
            log.info(f"Step 3: Prompt selected for '{doc_type}'.")

            # 4. Call the Vertex AI Gemini model asynchronously with the prompt and file reference
            log.info("Step 4: Calling Gemini model asynchronously...")
            resp = await asyncio.to_thread(
                _vertex_model.generate_content,
                contents=[
                    {"role": "user", "parts": [{"text": prompts.GIVE_OUTPUT_STRING}]},
                    {
                        "role": "user",
                        "parts": [
                            {"text": sys_prompt.strip()},
                            {
                                "file_data": {
                                    "file_uri": gs_uri,
                                    "mime_type": "application/pdf",
                                }
                            },
                        ],
                    },
                ],
            )
            log.info("Step 4: Gemini call complete.")

            # 5. Process the response and clean up the temporary file
            # Extract text, remove markdown code fences, and strip whitespace
            text = (
                resp.candidates[0]
                .content.parts[0]
                .text.strip()
                .strip("```json")
                .strip("```")
                .strip()
                if resp.candidates
                else ""
            )

            log.info("Step 5: Cleaning up temporary GCS file...")
            try:
                # Deleting a blob is also blocking, use asyncio.to_thread
                await asyncio.to_thread(blob.delete)
                log.info("Step 5: Cleanup complete.")
            except Exception as e:
                log.warning(
                    f"Warning: Could not delete temporary file {gs_uri}. Error: {e}"
                )
                pass  # Continue even if cleanup fails

            return text

        except httpx.HTTPError as e:
            log.error(f"Error downloading file from S3 URL asynchronously: {e}")
            return f"Error: Failed to download file from S3 URL: {e}"
        except Exception as e:
            # Catch any other potential errors during the process
            log.exception(
                f"An unexpected error occurred during async tool execution: {e}"
            )
            return f"An unexpected error occurred: {e}"


class PersistFinancialDataTool(BaseTool):
    """A tool to save extracted financial data to the database."""

    name: str = "PersistFinancialDataTool"
    description: str = (
        "Saves the extracted financial data (from PNL and Balance Sheets) to the database. "
        "This must be called after all documents have been processed by FinancialDocumentExtractor."
    )
    args_schema: Type[BaseModel] = PersistDataInput
    _db_connection = NetworkConnections()
    _balance_sheet_db = BalanceSheetDataDatabase(_db_connection)
    _pnl_sheet_db = ProfitAndLossSheetDatabase(_db_connection)

    def _run(self, *args, **kwargs) -> str:
        # Normalize inputs first
        normalized_kwargs = _normalise_inputs(*args, **kwargs)
        return asyncio.run(self._arun(**normalized_kwargs))

    async def _arun(self, *args, **kwargs) -> str:
        # 1. Normalize inputs
        # This handles if LLM sends a single string (JSON blob for the whole input) or a dict.
        normalized_kwargs = _normalise_inputs(*args, **kwargs)

        # 2. Validate using the Pydantic model
        try:
            validated_input = PersistDataInput(**normalized_kwargs)
        except ValidationError as ve:
            log.error(
                f"PersistFinancialDataTool validation error: {ve}. Normalized kwargs: {normalized_kwargs}"
            )
            return f"Error: Input validation failed for PersistFinancialDataTool. Details: {ve}"

        # 3. Extract validated data
        pnl_json_list_str = validated_input.pnl_json_list_str
        bs_json_list_str = validated_input.bs_json_list_str
        application_id = validated_input.application_id
        company_gst = validated_input.company_gst

        log.info(f"Persisting data for AppID: {application_id}, GST: {company_gst}")

        try:
            # Ensure strings are valid JSON or default to an empty list string
            pnl_data_list_outer = json.loads(
                pnl_json_list_str
                if pnl_json_list_str and pnl_json_list_str.strip()
                else "[]"
            )
            bs_data_list_outer = json.loads(
                bs_json_list_str
                if bs_json_list_str and bs_json_list_str.strip()
                else "[]"
            )

            pnl_data_list = [
                item
                for sublist in pnl_data_list_outer
                for item in (sublist if isinstance(sublist, list) else [sublist])
            ]
            bs_data_list = [
                item
                for sublist in bs_data_list_outer
                for item in (sublist if isinstance(sublist, list) else [sublist])
            ]

            for item_list, doc_type in [
                (pnl_data_list, "pnl-sheet"),
                (bs_data_list, "balance-sheet"),
            ]:
                for (
                    item_data
                ) in (
                    item_list
                ):  # Iterate directly over items after potential flattening
                    if doc_type == "balance-sheet":
                        item = ModelBalanceSheetData(**item_data)
                        item.companyGst = company_gst
                        await self._balance_sheet_db.upsert_sheet_data(item)
                    elif doc_type == "pnl-sheet":
                        item = ModelPnLSheetData(**item_data)
                        item.companyGst = company_gst
                        await self._pnl_sheet_db.upsert_sheet_data(item)

            return f"Successfully persisted data for PNL ({len(pnl_data_list)} items) and Balance Sheet ({len(bs_data_list)} items) for application {application_id}."
        except (json.JSONDecodeError, ValidationError) as e:
            log.error(
                f"Error processing/persisting data for AppID {application_id}: {e}. Input pnl_str: '{pnl_json_list_str}', bs_str: '{bs_json_list_str}'"
            )
            return f"Error: Data validation or JSON format error during persistence. Details: {e}"
        except Exception as e:
            log.exception(
                f"Unexpected error in PersistFinancialDataTool for AppID {application_id}"
            )
            return f"Error: An unexpected error occurred: {e}"


class FinancialSummarizerTool(BaseTool):
    """A tool to generate a final financial summary."""

    name: str = "FinancialSummarizerTool"
    description: str = (
        "Generates a final markdown summary of the financial data after it has been extracted and persisted. "
        "This should be the very last tool you use."
    )
    args_schema: Type[BaseModel] = SummarizerInput

    async def _arun(self, *args, **kwargs) -> str:
        # 1. Normalize inputs
        normalized_kwargs = _normalise_inputs(*args, **kwargs)

        # 2. Validate using the Pydantic model
        try:
            validated_input = SummarizerInput(**normalized_kwargs)
        except ValidationError as ve:
            log.error(
                f"FinancialSummarizerTool validation error: {ve}. Normalized kwargs: {normalized_kwargs}"
            )
            return f"Error: Input validation failed for FinancialSummarizerTool. Details: {ve}"

        # 3. Extract validated data
        pnl_json_list_str = validated_input.pnl_json_list_str
        bs_json_list_str = validated_input.bs_json_list_str
        application_id = validated_input.application_id

        log.info(f"Summarizer tool invoked for AppID: {application_id}")
        try:
            pnl_data = json.loads(
                pnl_json_list_str
                if pnl_json_list_str and pnl_json_list_str.strip()
                else "[]"
            )
            bs_data = json.loads(
                bs_json_list_str
                if bs_json_list_str and bs_json_list_str.strip()
                else "[]"
            )

            if not pnl_data and not bs_data:
                return "Error: Cannot generate summary. Both PNL and Balance Sheet data are empty."

            summary_text = await summarizer.create_summary(
                pnl_data=pnl_data, bs_data=bs_data, application_id=application_id  # type: ignore
            )
            return f"Summary generated successfully for application {application_id}. The summary has also been saved to the application tracker."
        except json.JSONDecodeError as e:
            log.error(
                f"Error decoding JSON for summarizer, AppID {application_id}: {e}. Input pnl_str: '{pnl_json_list_str}', bs_str: '{bs_json_list_str}'"
            )
            return f"Error: Data validation or JSON format error for summarizer. Details: {e}"
        except Exception as e:
            log.exception(
                f"Error in FinancialSummarizerTool for app_id {application_id}"
            )
            return f"An unexpected error occurred in FinancialSummarizerTool: {e}"

    def _run(self, *args, **kwargs) -> str:
        normalized_kwargs = _normalise_inputs(*args, **kwargs)
        return asyncio.run(self._arun(**normalized_kwargs))


class GSTAPISummaryTool(BaseTool):
    name: Literal["gst_summary_from_api"] = "gst_summary_from_api"
    description: str = (
        "Generates a GST company summary from live API response using Gemini."
    )

    def _run(self, input: dict) -> str:
        return asyncio.run(self._arun(input))

    async def _arun(self, input: dict) -> str:
        gst_number = None
        application_id = ""

        if isinstance(input, dict):
            application_id = input.get("application_id", "")
            val = input.get("gst_number")
            if isinstance(val, str):
                try:
                    if val.strip().startswith("{"):
                        val = json.loads(val)
                        gst_number = val.get("gst_number", val)
                    else:
                        gst_number = val
                except Exception:
                    gst_number = val
            else:
                gst_number = val
        elif isinstance(input, str):
            try:
                if input.strip().startswith("{"):
                    val = json.loads(input)
                    gst_number = val.get("gst_number", input)
                else:
                    gst_number = input
            except Exception:
                gst_number = input
        else:
            gst_number = input

        if not gst_number:
            return "Error: 'gst_number' is required for API summary."

        try:
            url = config.ALL_MIGHT_BASE_URL + "/master-india/get-gst-details"
            headers = {
                "x_source_name": config.SOURCE_NAME,
                "x_bizcon_auth": config.BIZCON_AUTH_KEY,
                "Content-Type": "application/json",
            }
            payload = {"gstNumber": gst_number, "createdBy": "nitesh.reddy@credflow.in"}

            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload)
                log.info(f"📥 Response status: {response.status_code}")
                log.info(f"📥 Response content: {response.text}")

            response.raise_for_status()
            parsed = response.json().get("gstData", {})

            formatted_prompt = API_SUMMARY_PROMPT.format(
                tradeNameOfBusiness=parsed.get("tradeNameOfBusiness", "N/A"),
                legalNameOfBusiness=parsed.get("legalNameOfBusiness", "N/A"),
                constitutionOfBusiness=parsed.get("constitutionOfBusiness", "N/A"),
                stateJurisdiction=parsed.get("stateJurisdiction", "N/A"),
                status=parsed.get("status", "N/A"),
                natureOfBusinessActivities=", ".join(
                    parsed.get("natureOfBusinessActivities", [])
                ),
                gstNumber=gst_number,
            )

            log.info("📡 Calling Gemini model with API GST data summary prompt...")
            response = await asyncio.to_thread(
                _vertex_model.generate_content,
                contents=[{"role": "user", "parts": [{"text": formatted_prompt}]}],
            )

            if response.candidates:
                final_summary = response.candidates[0].content.parts[0].text.strip()
                log.info(f"✅ GST Summary generated: {final_summary}")
                return final_summary
            else:
                return "⚠️ No summary generated from Gemini model."

        except Exception as e:
            log.exception("Error generating GST summary from API data")
            return f"Error: {e}"


# class OpenIndiamartProfileToolInput(BaseModel):
#     gst_number: str
#     application_id: Optional[str] = None


# class OpenIndiamartProfileTool(BaseTool):
#     name = "open_indiamart_profile"
#     description = "Searches and opens the Indiamart profile page using the GST number."

#     args_schema: Type[BaseModel] = OpenIndiamartProfileToolInput

#     async def _arun(self, input_data: str, **kwargs):
#         query = f"{gst_number}+indiamart"
#         url = config.BING_SEARCH + f"?q={query.replace(' ', '+')}"  # optional encoding
#         log.info(f"Opening Indiamart profile for GST: {gst_number} → {url}")
#         await webbrowser.open(url)
#         return f"Opened browser for: {url}"

#     def _run(self, gst_number: str, **kwargs):
#         return asyncio.to_thread(self._arun, gst_number, **kwargs)
  
  
  
  