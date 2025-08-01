
# 🚀 Automation of GST-based Financial Summary using LangChain & Gemini

## 📌 Project Overview

This project automates the generation of company financial summaries using GST numbers. It integrates a custom LangChain agent with Gemini (via Vertex AI) to fetch company data through API calls and dynamically generate insightful summaries — eliminating the need for manual data analysis.

---

## 🔧 Tech Stack

* **LangChain** – for tool and agent orchestration
* **Vertex AI + Gemini Pro** – for prompt-based financial summary generation
* **Python (Async/Await)** – for tool integration and logic flow
* **MongoDB (Initially used)** – deprecated in final version (API-only as per latest iteration)
* **Kuberx GST API** – for fetching real-time GST firm data
* **.env Configs** – for secure environment management
* **Command-Line Interface (CLI)** – currently used; Web UI to be developed

---

## 🧠 Core Features

| Feature                        | Description                                               |
| ------------------------------ | --------------------------------------------------------- |
| 🔍 **GST Number Input**        | Accepts GSTIN to fetch firm data via API                  |
| 📦 **Data Source Fallback**    | Tries MongoDB first (early version), then uses Kuberx API |
| 🧠 **LLM Summary Agent**       | Custom LangChain agent prompts Gemini to generate summary |
| 🔧 **Tool Abstraction**        | Modular tool logic split into API & Mongo summary tools   |
| 🖥️ **CLI-first Architecture** | Simple testing interface with plans for web integration   |

---

## 🛠️ Project Structure

```
├── main.py                         # Entry point for CLI execution
├── agent/Company_Summary_Agent.py # LangChain agent with tools and prompt
├── tools/
│   ├── GSTAPISummaryTool.py       # Tool to fetch GST data via API & prompt Gemini
│   └── GSTMongoSummaryTool.py     # (Deprecated) Tool for fetching from MongoDB
├── prompts.py                     # Centralized prompt templates
├── utils/browsing_logic.py        # Converted into LangChain tool (don't include directly)
├── .env                           # Contains API keys and secrets (not committed)
```

---

## 📈 Outcomes

* ⏱️ Reduced manual effort in generating summaries by **90%**
* 🤖 Agent logic adaptable for other financial document workflows
* 🧪 Successfully demoed to mentors with real-time GST test cases
* ✅ Approved and integrated as an internal automation prototype at CredFlow

---

## 🧑‍💻 Intern Contribution – *Lakshy Mittal*

* Designed and implemented complete summary pipeline using LangChain
* Wrote Gemini-compatible prompts to structure summaries
* Converted utility logic (`browsing.py`) into tool-based agent integration
* Debugged API & database issues and aligned to mentor feedback
* Followed scalable, modular Python code architecture

---

## 📌 Next Steps

* [ ] Build Web UI for input + output display
* [ ] Add testing framework for tool verification
* [ ] Extend tool support for PAN/TAN-based summary
* [ ] Modular plugin-based architecture for company-wide internal tools

---

## 📄 License

Private – Developed under CredFlow Internship Program. Do not redistribute without permission.
