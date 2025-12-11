import json
import os
import ast
from langchain.agents import Tool, AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.memory import ConversationBufferMemory
from dotenv import load_dotenv

from agents import TallyWorkerAgent, ChartAgent, SummarizerAgent

load_dotenv()
TALLY_AGENT = TallyWorkerAgent()
CHART_AGENT = ChartAgent()
SUMMARIZER_AGENT = SummarizerAgent()

# --- Tools ---
def tool_fetch_companies(_input: str = "") -> str:
    comps = TallyWorkerAgent().fetch_companies()
    return json.dumps(comps)

def tool_analyze_visual(input_str: str) -> str:
    """Use this when the user needs GRAPHS/COMPARISONS/TRENDS."""
    try:
        try: payload = json.loads(input_str)
        except: payload = ast.literal_eval(input_str)
        
        company = payload.get("company")
        query = payload.get("query")
        report_type = payload.get("report_type", "Balance Sheet")

        print(f"\n⚙️ WORKER: Fetching '{report_type}' for Visual Analysis...")
        fetch_res = json.loads(TALLY_AGENT.fetch_report(company, report_type))
        if fetch_res.get("status") == "error": return f"Error: {fetch_res.get('error')}"
        
        json_path = fetch_res.get("json_file_path")
        
        print(f"⚙️ WORKER: Drawing Professional Charts...")
        chart_res = json.loads(CHART_AGENT.create_charts(json_path))
        image_paths = chart_res.get("images", [])
        rationale = chart_res.get("rationale", "")
        
        print(f"⚙️ WORKER: Analyzing Visuals...")
        final_ans = SUMMARIZER_AGENT.analyze_visual(query, json_path, image_paths, rationale)
        
        return f"ANALYSIS:\n{final_ans}\n\n[Charts]: {', '.join(image_paths)}\n[Rationale]: {rationale}"
    except Exception as e: return f"Error: {str(e)}"

def tool_analyze_text_only(input_str: str) -> str:
    """Use this for SPECIFIC VALUE lookups (e.g. 'What is my loan amount?'). NO GRAPHS."""
    try:
        try: payload = json.loads(input_str)
        except: payload = ast.literal_eval(input_str)
        
        company = payload.get("company")
        query = payload.get("query")
        report_type = payload.get("report_type", "Balance Sheet")

        print(f"\n⚙️ WORKER: Fetching '{report_type}' for Text Analysis (No Graphs)...")
        fetch_res = json.loads(TALLY_AGENT.fetch_report(company, report_type))
        if fetch_res.get("status") == "error": return f"Error: {fetch_res.get('error')}"
        
        json_path = fetch_res.get("json_file_path")
        
        final_ans = SUMMARIZER_AGENT.analyze_text_only(query, json_path)
        return f"ANSWER:\n{final_ans}"
    except Exception as e: return f"Error: {str(e)}"


TOOLS = [
    Tool(name="list_companies", func=tool_fetch_companies, description="List companies."),
    Tool(name="analyze_visual", func=tool_analyze_visual, description="For COMPARISON, TRENDS, ANALYSIS. Returns Graphs + Text. Input JSON: {'company': '...', 'query': '...', 'report_type': '...'}"),
    Tool(name="analyze_text_only", func=tool_analyze_text_only, description="For SPECIFIC VALUES/FACTS. Returns Text Only. Input JSON: {'company': '...', 'query': '...', 'report_type': '...'}")
]

class SupervisorAgent:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        model_name = os.getenv("GEMINI_MODEL") or "models/gemini-2.0-flash"
        
        self.llm = ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key)
        self.memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
        
        template = """You are a Tally Reasoning Agent.
        
        TOOLS:
        {tools}
        
        DECISION PROTOCOL (Chain-of-Thought):
        1. **Retrieve Context**: Get 'company' from Chat History.
        2. **Classify Query**:
           - **Visual Needed?**: "Compare", "Trend", "Analysis", "Breakdown", "Graph" -> Use `analyze_visual`.
           - **Text Only?**: "What is", "How much", "Value of", "Specific Number" -> Use `analyze_text_only`.
             "What is the value of my current loans?", "How much are my fixed assets worth?, "What's the value of my indirect incomes (P&L)" -> Use `analyze_text_only`.
           - Basically you have too generate charts only when the user explicitly needs COMPARISONS, TRENDS, or ANALYSIS or dealing multpile data points and large dataset.
           -You to avoid generating charts for simple lookups of specific values or facts.
        3. **Map Report Type**:
           - "stocks" -> "Stock Summary"
           - "balance" -> "Balance Sheet"
           - "profit", "loss" -> "Profit and Loss"
           - "day book" -> "Day Book"

        FORMAT:
        Thought: [Reasoning]
        Action: the action to take, should be one of [{tool_names}]
        Action Input: [JSON Input]
        Observation: [Result]
        Final Answer: [Response]

        Chat History: {chat_history}
        User Input: {input}
        Thought:{agent_scratchpad}"""
        
        prompt = PromptTemplate.from_template(template)
        agent = create_react_agent(self.llm, TOOLS, prompt)
        self.agent_executor = AgentExecutor(agent=agent, tools=TOOLS, verbose=True, memory=self.memory, handle_parsing_errors=True)

    def run(self):
        print("\n=== Tally Smart Agent ===")
        print("Fetching companies...")
        try:
            companies = json.loads(tool_fetch_companies())
        except:
            print("Error connecting to Tally. Check ODBC.")
            return

        if not companies:
            print("No companies found open in Tally.")
            return

        print("\nAvailable Companies:")
        for i, c in enumerate(companies):
            name = c.get('name') or c.get('id')
            print(f"{i+1}. {name}")

        selected = None
        while not selected:
            choice = input("\nSelect Company (Number): ").strip()
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(companies):
                    selected = companies[idx].get('name') or companies[idx].get('id')
            except: pass

        print(f"\n✅ Active Company: {selected}")
        self.memory.chat_memory.add_user_message(f"Selected company: {selected}")
        
        while True:
            u_input = input("\nUser: ")
            if u_input.lower() in ["exit", "quit"]: break
            try:
                self.agent_executor.invoke({"input": u_input})
            except Exception as e: print(e)