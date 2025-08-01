# prompts.py
GIVE_OUTPUT_STRING = "Return ONLY JSON.**Do not wrap JSON in markdown fences**, **do not prepend language tags, or add commentary**."

COMMON_EXTRACTION_RULES = """\
── **Numerical-Extraction Fidelity**
• Meticulously verify each digit, decimal point, and thousands separator; distinguish similar-looking characters (e.g., “1” vs “7”, “0” vs “8”, “5” vs “S”, “B” vs “8”).

── **Dash & Placeholder Handling**
• A numeric cell that contains only “–”, “—”, or “-” ⇒ **0**.
• Never borrow a number from the row above/below to replace a dash.

── **Blank/Zero Handling**
• If a table cell is blank, assume 0 **only if** the grid clearly shows that a numeric value should be present **and** that same row contains a label recognised from the synonym whitelist.
• Otherwise mark the value **missing**.

── **Note-Reference Mapping Precision (STRICT OVERRIDE POTENTIAL)**
• When a line item references a note number (e.g., “9”), meticulously parse the *entire* referenced note table ("Note_Content") **before** assigning a final value to the line item. The information from the note can **override** values read directly from the main page via strict row-alignment.

_____• **Decision Logic based on Note Content:**
    1.  **Direct Match in Note:** If "Note_Content" contains a specific sub-item, section, or its main title/total whose label clearly and semantically matches the line item label:
        *   The value for the line item is taken directly from this aligned part of "Note_Content".
        *   This note-derived value **replaces** any value that might have been visually associated with the line item on its row on the main page.
    2.  **Mismatch in Categorization (Note subject differs from line item label):** If "Note_Content"'s primary subject, title, or its main summed figure unequivocally pertains to a *different* category (hereafter "ActualNoteSubject") than the line item label, AND "Note_Content" does *not* contain a clear sub-component matching the line item label:
        *   The value for the original line item label is definitively set to **0** (zero). This **overrides** any value visually present on the same row as the original label on the main page.
        *   The total value from "Note_Content" (which pertains to "ActualNoteSubject") must then be assigned to the line item "ActualNoteSubject" where it appears on the main page. This assignment also **overrides** any value (e.g., a dash or a different number) visually present on the row of "ActualNoteSubject" on the main page. If "ActualNoteSubject" is not an explicit field in the target JSON but contributes to a total, ensure the total reflects this reassignment.
    3.  **Simple Breakdown:** If "Note_Content" simply provides a breakdown of items that all fall under the category of the line item label (without introducing a different category for the total), then the sum of this breakdown from the note is the value for the line item label. This sum will also **override** any conflicting visual value on the main page row.

• **Primacy of Note Interpretation:** The semantic content and categorization within a note are paramount. Figures are mapped based on label meaning. A value read via strict row-alignment on the main page *must* be validated against, and potentially corrected or zeroed out by, the referenced note's details, especially if the note indicates the sum belongs to a different heading.
• **No Double Counting or Misappropriation:** Strictly ensure that a single sum from a note is not used for two different line items unless the note explicitly details such a split. If a note's total is reassigned from one label to "ActualNoteSubject", the original label must become 0 (unless it has other sources).

── **Sibling-Row Guard**
• If two consecutive rows map to different line-item labels but share one numeric column, ensure each value remains exclusive:
 – If Row N’s numeric cell is dash/blank but Row N+1 has a value, keep Row N = 0.
 – Flag an **alignment_conflict** if the same numeric value appears mapped to two labels.

── **Dual-Pass OCR for Ambiguous Cells**
• Re-run OCR at 200 % zoom on any cell containing ambiguous glyphs.
• If the two passes disagree, keep the value from the pass with higher OCR confidence; if both confidences < 0.85, tag **low_confidence**.

── **Cross-Validation of Totals**
• Re-sum extracted sub-items and compare with the reported subtotal/total.
• If |reported − computed| ≤ 0.5 % of total, override the OCR’d subtotal with the computed value.
• If a subtotal exists but one or more sub-items are missing (and not dashed), you may infer the missing value **only** when the subtotal context justifies it; otherwise rely on the reported subtotal and set missing sub-items = 0.
"""

# --- Output Format Instructions Section ---
# This section defines the strict output format requirements.
STRICT_JSON_OUTPUT_INSTRUCTIONS = """\
**STRICT OUTPUT FORMAT:**
- Return **ONLY** JSON.
- **DO NOT** wrap the JSON in markdown fences (```json).
- **DO NOT** prepend language tags (like `json`).
- **DO NOT** append any commentary or explanation before or after the JSON.
- Reply with EITHER a single JSON object (if only current year data is found) OR an array with two such objects (if both current and prior year data are found, current year first).
"""

# --- BALANCE SHEET PROMPT ---
BALANCE_SHEET_PROMPT = f"""\
You are an AI model specialized in OCR and financial data extraction. You will receive a multi-page PDF or image containing audited financial statements mixed with audit notes.
0. **Validate Input**
- If the document is not a valid multi-page PDF/image of financial statements, or if **no Balance Sheet** section can be located, respond with:

Error: No balance sheet detected or invalid input.

and do **not** output any JSON.
1. **Ignore** any page or section that is clearly an audit note.
2. **Locate** the Balance Sheet (and associated schedules) only.
3. **Extract** all line items and numeric values for the **current year** and, if present, the **prior year**, outputting each as a JSON object.  

{COMMON_EXTRACTION_RULES}

4. **Output** your result as follows:
{STRICT_JSON_OUTPUT_INSTRUCTIONS}

Each JSON object **MUST exactly match** this structure:
{{
    "companyName": "...",
    "fiscalYearEnd": "YYYY-MM-DD",
    "balanceSheet": {{
      "shareholdersFunds": {{
        "shareCapital": number,
        "reservesAndSurplus": number,
        "totalShareholdersFunds": number
      }},
      "nonCurrentLiabilities": {{
        "longTermBorrowings": number,
        "otherLongTermLiabilities": number,
        "deferredTaxLiability": number,
        "totalNonCurrentLiabilities": number
      }},
      "currentLiabilities": {{
        "shortTermBorrowings": number,
        "tradePayables": number,
        "otherCurrentLiabilities": number,
        "shortTermProvisions": number,
        "totalCurrentLiabilities": number
      }},
      "totalLiabilities": number,
      "nonCurrentAssets": {{
        "tangibleAssets": number,
        "intangibleAssets": number,
        "capitalWorkInProgress": number,
        "nonCurrentInvestments": number,
        "deferredTaxAssets": number,
        "longTermLoansAndAdvances": number,
        "totalNonCurrentAssets": number
      }},
      "currentAssets": {{
        "currentInvestments": number,
        "inventories": number,
        "tradeReceivables": number,
        "cashAndCashEquivalents": number,
        "shortTermLoansAndAdvances": number,
        "otherCurrentAssets": number,
        "totalCurrentAssets": number
      }},
      "totalAssets": number
    }},
    "camSheetObject": {{
      "receivable": number,
      "payables": number,
      "inventory": number,
      "currentAssets": number,
      "currentLiabilities": number,
      "loansAndAdvancesInBs": number,
      "longTermDebt": number,
      "shortTermDebt": number,
      "currentDebt": number,
      "equity": number
    }},
    "summary": "…" // Up to 500 characters summarizing liquidity, solvency, and key year-over-year trends
  }}
  
5. Construct the camSheetObject by mapping from your extracted data (apply logic, not exact key names). Extract values only from the exact or closest semantically equivalent line item. If a label is present but its value cell is blank, treat its value as 0. Do not infer values from adjacent or unrelated items.
receivable ← “Sundry Debtors”
payables ← “Sundry Creditors (As per list)”
inventory ← “Closing Stock”
current_assets ← sum of “Current Assets” + “Cash & Bank Balances”
current_liabilities ← “Current Liabilities”
loans_and_advances_in_bs ← “Loans and Advances (As per List)”
Example: Identify “Long Term Loans and Advances” in Non-current Assets and “Short Term Loans and Advances” in Current Assets. Sum only those exact labels; blanks → 0.
long_term_debt ← sum of “Unsecured Loans” + “Secured Loans” **Do NOT include Quasi equity and loan from individual names** 
short_term_debt ← “Secured / OD / CC”
current_debt ← same as “Current Liabilities”
equity ← sum of “Equity” + “Share Capital” + “Reserves and Surplus”
"""

# --- PNL PROMPT ---
PNL_PROMPT = f"""\
You are an AI model specialized in OCR and financial-statement extraction.  
You will receive a multi-page PDF or image that contains audited financial statements intermixed with audit notes.

0. **Validate Input**  
   • If the document is not a valid multi-page PDF/image of financial statements, **or** if **no Profit & Loss (P&L) Statement** can be located, reply **exactly** with:  
     ```
     Error: No profit and loss statement detected or invalid input.
     ```  
     and **do not** output any JSON.

1. **Ignore** any page or section that is clearly an audit note.

2. **Locate** only the Statement of Profit & Loss (and any schedules/notes it references).

3. **Extract** every line-item label and its numeric value(s) for the **current year** and, if present, the **prior year**.

{COMMON_EXTRACTION_RULES}

4. **Output** the result as follows:  
{STRICT_JSON_OUTPUT_INSTRUCTIONS}  
  • If two numeric columns are visible (e.g., labelled “2025” and “2024”), you **must** output an **array with two objects** – **current year first**.  
  • If only one numeric column is present, output a single JSON object.

Each JSON object **must exactly match** this structure (missing numbers ⇒ 0, never null):

{{
  "companyName": "...",
  "fiscalYearEnd": "YYYY-MM-DD",

  "profitAndLoss": {{
    "income": {{
      "revenueFromOperations": number,
      "otherIncome": number,
      "totalIncome": number
    }},
    "expenses": {{
      "costOfMaterialsConsumed": number,
      "purchaseOfStockInTrade": number,
      "changesInInventory": number,
      "employeeBenefitExpenses": number,
      "financeCosts": number,
      "depreciationAndAmortization": number,
      "otherExpenses": number,
      "totalExpenses": number
    }},
    "profit": {{
      "ebitda": number,
      "profitBeforeTax": number,
      "taxExpenseCurrent": number,
      "taxExpenseDeferred": number,
      "totalTaxExpense": number,
      "profitAfterTax": number
    }},
    "earningsPerShare": {{
      "basicEPS": number,
      "dilutedEPS": number
    }}
  }},

  "pnlMetricsObject": {{
    "grossProfit": number,             // = totalIncome − (costOfMaterialsConsumed + purchaseOfStockInTrade + changesInInventory)
    "ebit": number,                   // = ebitda − depreciationAndAmortization
    "ebitdaMargin": number,           // (%) = ebitda ÷ totalIncome
    "netProfitMargin": number,        // (%) = profitAfterTax ÷ totalIncome
    "interestCoverageRatio": number   // = ebit ÷ financeCosts
  }},

  "camSheetObject": {{
    "turnover": number,               // copy of totalIncome
    "grossProfit": number,            // copy of pnlMetricsObject.grossProfit
    "interestExpenses": number,       // copy of financeCosts
    "netProfit": number               // copy of profitAndLoss.profit.profitAfterTax
  }},

  "summary": "…"                      // up to 500 chars on growth, profitability & YoY trends
}}

────────── Metric-building rules ──────────  
• grossProfit  = totalIncome − (costOfMaterialsConsumed + purchaseOfStockInTrade + changesInInventory)  
• ebit         = ebitda − depreciationAndAmortization  
• ebitdaMargin = (ebitda ÷ totalIncome) × 100  
• netProfitMargin = (profitAfterTax ÷ totalIncome) × 100  
• interestCoverageRatio = ebit ÷ financeCosts  
If any component for a metric is missing or low_confidence, set that metric = null.

────────── camSheetObject mapping ──────────  
turnover         ← profitAndLoss.income.totalIncome  
grossProfit      ← pnlMetricsObject.grossProfit  
interestExpenses ← profitAndLoss.expenses.financeCosts  
netProfit        ← profitAndLoss.profit.profitAfterTax
"""

SUMMARY_PROMPT = """\
    You are a financial-analysis assistant.  
I will send you the **current-year raw figures** in JSON.  
  
Your tasks, in order:


──────────────────────── 1. COMPUTE ALL RATIOS ────────────────────────  
Use the exact formulas and cell references shown.  
*Round every numeric result to 2 decimals unless the result is an integer.*


| Metric                              | Formula (cell refs → JSON keys)                                                        |
| ----------------------------------- | -------------------------------------------------------------------------------------- |
| **Return on Capital Employed**      | B3 **(grossProfit)** ÷ Total Working Capital                                           |
| **Total Working Capital**           | B4 **(receivable)** − B5 **(payables)** + B6 **(inventory)**                           |
| **Cash-Conversion Cycle**           | D11 + D9 − D10 *(uses previously-computed Inventory Days, DSO, DPO)*                   |
| **Quick Ratio**                     | B7 **(currentAssets)** ÷ B8 **(currentLiabilities)**                                   |
| **Interest-Service Coverage Ratio** | B10 **(interestExpense)** ÷ B3 **(grossProfit)**                                       |
| **Leverage Ratio**                  | (B11 **longTermDebt** + B12 **shortTermDebt** + B13 **currentDebt**) ÷ B2 **turnover** |
| **Days Sales Outstanding**          | (B4 **receivable** ÷ B2 **turnover**) × 365                                            |
| **Days Payables Outstanding**       | (B5 **payables** ÷ (B2 **turnover** − B3 **grossProfit**)) × 365                       |
| **Inventory Days**                  | (B6 **inventory** ÷ B2 **turnover**) × 365                                             |
| **Gross-Profit Margin %**           | B3 **grossProfit** ÷ B2 **turnover** × 100                                             |
| **Net-Profit Margin %**             | B15 **netProfit** ÷ B2 **turnover** × 100                                              |
| **Debt-to-Equity**                  | (B11 **longTermDebt** + B12 **shortTermDebt** + B13 **currentDebt**) ÷ B16 **equity**  |



─────────────────────── 2. FLAG EACH RATIO (RED / GREEN) ──────────────  
Apply these thresholds:


| Ratio | Red-flag if … | Otherwise | Notes |
|-------|---------------|-----------|-------|
| ROCE |  < 30 % | GREEN | |
| Total Working Capital  | value < 0 | GREEN | |
| Cash-Conversion Cycle | > 120 days | GREEN | |
| Quick Ratio  | ≤ 0.8 | GREEN | |
| Interest Service Coverage | < 1 .0 | GREEN | exactly 1.0 is GREEN |
| Leverage | ≥ 0.30 (30 %) | GREEN | ratio in decimal |
| DSO | > 90 days | GREEN | |
| DPO | > 90 days | GREEN | |
| Inventory days | > 75 days | GREEN | |
| Gross-Profit % | — (always GREEN; just report) | | |
| Net-Profit % | value < 0 (negative) | GREEN | |
| Debt-to-Equity | ≥ 3.0 | GREEN | |
──────────────────────── 3. OUTPUT ─────────────────────────
3. OUTPUT — **return one JSON string**
Produce exactly one UTF-8 JSON object (no code-fences, no extra text).
 The top-level shape is:

{
  "fiscalYears": [
    {
      "year": "YYYY-YYYY",
      "pointsOfConcern": [
        {
          "metric": "Metric Name",
          "value": "12.3 Cr",
          "note": "Short friendly explanation"
        }
        // …repeat for every red-flag metric
      ],
      "strongPoints": [
        {
          "metric": "Metric Name",
          "value": "56 days",
          "note": "Brief positive note"
        }
        // …repeat for every green metric
      ],
      "overallSummary": "One wrap-up paragraph 500-1000 characters."
    }
    // …repeat this block for each fiscal year in the input JSON
  ]
}
Formatting rules
No additional keys beyond those shown.
pointsOfConcern and strongPoints are arrays.
If a list is empty, output an empty array [].
No nulls – omit a list only if you omit its heading entirely (rule 4).
If there are no green metrics, omit the strongPoints field.
 If there are no red flags, set pointsOfConcern to an empty array.
Round all numbers and use human-friendly units exactly as in the original
 prompt.
**Return only the JSON string** (**no surrounding text**, **no “markdown”**,
 **no back-ticks, no HTML**).

──────────────────────── FINAL MARKDOWN FORMAT ────────────────────────
• No back-ticks, no code fences, no word “markdown”.  
• Output is a single JSON string.
."""
# COMPANY_SUMMARY_PROMPT = """\
# Given the GST Number: {gstNumber}
# You have access to structured data obtained from either:
# 1. MongoDB (internal GST cache), or
# 2. Live GST API (Kuberx)
# Please:
# 1. Generate a concise, single-paragraph company summary in **500 to 700 characters**, starting directly with the **company name**.
#    - Trade name
#    - Legal name
#    - Constitution (type of entity)
#    - Director/Proprietor’s name
#    - State and jurisdiction
#    - GST status (active/inactive)
#    - Nature of business
#    - IndiaMART link (if any)
#    - Official website (if any)
#    - **Data Source**: Mention `MongoDB` or `Live API`
# 2. Include a **"Sources and References"** from where you search the details
# ⚠️ Use plain text. No markdown or bullet points.
# If a field is not available, write: "Not available".
# """


# MONGO_SUMMARY_PROMPT = """\
# Given the GST Number: {gstNumber}

# This data was fetched from our **internal MongoDB database**.

# Generate a concise single-paragraph company summary (500–700 characters). Start directly with the company name. Do not say “Here is the summary.” Then provide a **"Sources and References"** section listing:

# - Trade name: {tradeNameOfBusiness}
# - Legal name: {legalNameOfBusiness}
# - Constitution of business: {constitutionOfBusiness}
# - State and jurisdiction: {stateJurisdiction}
# - GST status: {status}
# - Nature of business: {natureOfBusinessActivities}
# - Source: MongoDB
# - IndiaMART or official website: Not available (if not found)

# Use plain text (no bullet points or markdown). If a value is missing, say "Not available".
# """

API_SUMMARY_PROMPT = """\
You are provided with GST data retrieved from the **live Kuberx GST API** for the GST Number: {gstNumber}.

Based on the following data, perform two tasks:

1. Write a **single-paragraph company summary** (500–700 characters). Start with the company name. Clearly describe its legal identity, trade name, constitution, business activities, jurisdiction, and GST compliance status.

2. Create a **Sources and References** section using bullet points. Clearly map each detail to its original source — either the GST API field or an external link.

Input Data:
- Trade Name: {tradeNameOfBusiness}
- Legal Name: {legalNameOfBusiness}
- Constitution of Business: {constitutionOfBusiness}
- State and Jurisdiction: {stateJurisdiction}
- GST Status: {status}
- Nature of Business Activities: {natureOfBusinessActivities}
- GST Number: {gstNumber}

Additional Rules:
- For the **IndiaMART profile**, perform a Google or Bing search using this GST number and include the Indiamart "about us" page if found.
- For the **Official Website**, only include it if the website clearly matches the GST data. Otherwise, mention "Not available".

Output Format:
<Company Summary Paragraph>

Sources and References:
• Trade Name: {tradeNameOfBusiness} (Source: GST API - tradeNameOfBusiness)  
• Legal Name: {legalNameOfBusiness} (Source: GST API - legalNameOfBusiness)  
• Constitution of Business: {constitutionOfBusiness} (Source: GST API - constitutionOfBusiness)  
• State and Jurisdiction: {stateJurisdiction} (Source: GST API - stateJurisdiction)  
• GST Status: {status} (Source: GST API - status)  
• Nature of Business Activities: {natureOfBusinessActivities} (Source: GST API - natureOfBusinessActivities)  
• GST Number: {gstNumber} (Source: GST API - gstNumber)  
• IndiaMART Profile: <link or "Not available"> (Source: External Search)  
• Official Website: <link or "Not available"> (Source: External Search)  

⚠️ Do not use markdown formatting like `**`, `#`, or bullet symbols. Use plain text bullets (•) only.
Ensure the tone is factual, formal, and readable.
"""
