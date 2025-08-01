import argparse
import asyncio
import logging

# ─── import local packages ─────────────────────────────────────────
# from agent.financial_workflow_agent import run_financial_agent
from agent.Company_Summary_Agent import run_gst_summary_agent

# from kafka_consumer import poll_forever

# ─── logging setup ────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(message)s",
)
log = logging.getLogger("main")

# ─── sample payload for quick testing ─────────────────────────────
SAMPLE_PAYLOAD = {
    "ApplicationId": "67fe64c104c12cad88b3b3be",
    "GstNumber": "24AAEFK8509N1ZZ",
    "PNLSheetUrls": [
        "https://losapplication-production.s3.ap-south-1.amazonaws.com/09ACBPA8035C1Z5/07d0ec82-cf40-4643-9099-824c7e962a49_BALANCE_SHEET.PDF"
    ],
    "BalanceSheetUrls": [
        "https://losapplication-production.s3.ap-south-1.amazonaws.com/09ACBPA8035C1Z5/f8382c93-3bad-4b38-ba09-39579a393371_BALANCE_SHEET.PDF"
    ],
    "AuditReportUrl": [],
}


# ─── CLI & entry-point ────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agent runner")
    parser.add_argument(
        "--kafka",
        action="store_true",
        help="Launch the Kafka consumer (for production use)",
    )
    return parser.parse_args()


# ─── Run your custom GST summary agent (API + auto-browser) ───────
async def run_one_off_test():
    log.info("── running one-off test (custom GST agent) ──")

    summary = await run_gst_summary_agent(
        SAMPLE_PAYLOAD.get("GstNumber", ""), SAMPLE_PAYLOAD.get("ApplicationId", "")
    )

    if summary:
        log.info("✅ Summary written to latest_summary.txt (%s chars)", len(summary))
    else:
        log.warning("⚠️ No summary was generated.")


# ─── Main ─────────────────────────────────────────────────────────
def main():
    args = parse_args()

    # 🔁 Toggle between Kafka mode and one-off test mode
    if args and not args.kafka:
        asyncio.run(run_one_off_test())  # ✅ YOUR agent runs here
    else:
        log.info("── Kafka consumer is currently commented out ──")
        # asyncio.run(poll_forever())  # 🔁 Other coder's Kafka logic (keep commented for now)


if __name__ == "__main__":
    main()
