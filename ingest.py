"""
Ingest P&L and Balance-sheet docs → JSON → persist (placeholder)
"""

import asyncio
import json
from typing import Dict, List

from database.balance_sheet_data import BalanceSheetDataDatabase
from database.database_config import NetworkConnections
from database.pnl_sheet_data import ProfitAndLossSheetDatabase
from langchain.tools import Tool
from models.balance_sheet import BalanceSheetData as ModelBalanceSheetData
from models.pnl_sheet import ProfitAndLossSheetData as ModelPnLSheetData
from pydantic import ValidationError

from . import prompts
from .llm_tools import GeminiFileQATool

_extractor = GeminiFileQATool()
_db_connection = NetworkConnections()  # Instantiate NetworkConnections once
_balance_sheet_db = BalanceSheetDataDatabase(_db_connection)
_pnl_sheet_db = ProfitAndLossSheetDatabase(_db_connection)


async def process_documents(
    docs: List[Dict[str, str]], companyGst: str
) -> Dict[str, list]:
    results = {"balance-sheet": [], "pnl-sheet": []}

    for d in docs:
        doc_type = d.get("doc_type")
        s3_url = d.get("s3_url")

        if not doc_type or not s3_url:
            print(f"Skipping document due to missing 'doc_type' or 's3_url': {d}")
            continue

        # Use asyncio.to_thread for synchronous blocking calls in async code
        raw_json = await asyncio.to_thread(_extractor._run, s3_url, doc_type)

        current_doc_data_items = []
        try:
            parsed_data = json.loads(raw_json)
            if isinstance(parsed_data, dict):
                current_doc_data_items = [parsed_data]
            elif isinstance(parsed_data, list):
                current_doc_data_items = parsed_data
            else:
                print(
                    f"Skipping document {s3_url}: Extractor returned unsupported format. Raw: {raw_json[:200]}"
                )
                continue

            results[doc_type].extend(
                current_doc_data_items
            )  # Accumulate for function's return value

            # Persistence logic moved inside the loop for each document's data
            for item_data in current_doc_data_items:
                try:
                    if doc_type == "balance-sheet":
                        balance_sheet_item = ModelBalanceSheetData(**item_data)
                        balance_sheet_item.companyGst = companyGst
                        await _balance_sheet_db.upsert_sheet_data(balance_sheet_item)
                        print(
                            f"Successfully upserted balance sheet data for {balance_sheet_item.companyGst} - {balance_sheet_item.fiscalYearEnd}"
                        )
                    elif doc_type == "pnl-sheet":
                        pnl_sheet_item = ModelPnLSheetData(**item_data)
                        pnl_sheet_item.companyGst = companyGst
                        await _pnl_sheet_db.upsert_sheet_data(pnl_sheet_item)
                        print(
                            f"Successfully upserted PnL sheet data for {pnl_sheet_item.companyGst} - {pnl_sheet_item.fiscalYearEnd}"
                        )
                    else:
                        print(
                            f"Unsupported document type for persistence: {doc_type} for {s3_url}"
                        )
                except ValidationError as e_val:
                    print(
                        f"Pydantic validation error for {doc_type} from {s3_url} with data {item_data}: {e_val}"
                    )
                except Exception as e_persist:
                    print(
                        f"Error persisting {doc_type} data for {s3_url} with data {item_data}: {e_persist}"
                    )

        except json.JSONDecodeError as e:
            print(
                f"Error decoding JSON for {s3_url}: {e}. Raw JSON: '{raw_json[:200]}'"
            )
            continue
        except Exception as e:
            print(f"An unexpected error occurred processing document {s3_url}: {e}")
            continue

    return results
