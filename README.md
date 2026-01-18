# Tally AI Supervisor Agent 

A powerful AI-driven financial assistant that connects directly to **Tally Prime** to analyze data, generate financial reports, and visualize insights. Built with **LangChain**, **FastAPI**, **Google Gemini**, and the **Tally XML Interface**.

## 🚀 Features

* **Natural Language Queries:** Ask questions like "Show me the Profit & Loss for last month" or "What is the total debit for today?".
* **Real-time Tally Integration:** Fetches live data directly from your local Tally instance using XML over HTTP.
* **Multi-Agent Architecture:**
    * **Supervisor Agent:** Orchestrates tasks and delegates work.
    * **Report Agent:** Fetches and cleans Tally reports (Day Book, Balance Sheet, etc.) using "Nuclear" XML sanitization.
    * **Chart Agent:** Generates visualizations (Pie charts, Bar graphs) dynamically using Python.
    * **Analysis Agent:** Provides text summaries and financial insights using Gemini 1.5.
* **Robust API:** Exposes all functionality via a RESTful API (FastAPI) for easy frontend integration (React/Node.js).
* **Async Performance:** Optimized with `run_in_threadpool` for non-blocking concurrent requests.

---

## 🛠️ Tech Stack

* **Backend:** Python 3.9+, FastAPI, Uvicorn
* **AI/LLM:** LangChain, Google Gemini 1.5 Flash/Pro
* **Database:** ChromaDB (Vector Store for report lookups)
* **Tally Connectivity:** Requests (XML Interface), PyODBC (optional)
* **Visualization:** Matplotlib, Pillow

---

## ⚙️ Installation & Setup

### Prerequisites
1.  **Python 3.9+** installed.
2.  **Tally Prime** running on your local machine.
3.  **Google Gemini API Key** (Get it from Google AI Studio).

### 1. Clone the Repository
```bash
git clone <your-repo-url>
cd <your-repo-folder>
