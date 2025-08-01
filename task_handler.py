from agent.Company_Summary_Agent import run_gst_summary_agent
from agent.financial_workflow_agent import run_financial_agent
from graph.gstr3b.gstr3b_summary import run_gstr3b_summary_workflow
from agent.Company_Summary_Agent import run_gst_summary_agent


async def handle_financial_summary(payload: dict) -> str:
    return await run_financial_agent(
        pnl_s3_urls=payload.get("PNLSheetUrls", []),
        bs_s3_urls=payload.get("BalanceSheetUrls", []),
        application_id=payload.get("ApplicationId", ""),
        company_gst=payload.get("GstNumber", ""),
    )


async def gstr3b_summary(payload: dict) -> str:
    return await run_gstr3b_summary_workflow(data=payload)


async def handle_gst_summary(payload: dict) -> str:
    gst_number = payload.get("GstNumber")
    application_id = payload.get("ApplicationId")
    if not gst_number:
        raise ValueError("GST number missing in payload")

    return await run_gst_summary_agent(gst_number, application_id)


TASK_DISPATCH = {
    "FINANCIAL_SUMMARY": handle_financial_summary,
    "GSTR3B_SUMMARY": gstr3b_summary,
    "GST_SUMMARY": handle_gst_summary,
}
