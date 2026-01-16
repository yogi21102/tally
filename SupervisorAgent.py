# SupervisorAgent.py
import json
import os
import ast
from langchain_core.tools import Tool
from langchain_classic.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_classic.memory import ConversationBufferMemory
from report_config import REPORT_DEFINITIONS
from tools.report_lookup import lookup_tally_report
from dotenv import load_dotenv

try:
    from agents import TallyWorkerAgent, ChartAgent, SummarizerAgent, TableAgent
except ImportError:
    from .agents import TallyWorkerAgent, ChartAgent, SummarizerAgent, TableAgent

# --- INITIALIZE SUB-AGENTS ---
TALLY_AGENT = TallyWorkerAgent()
CHART_AGENT = ChartAgent()
TABLE_AGENT = TableAgent()
SUMMARIZER_AGENT = SummarizerAgent()

# --- WRAPPER TOOLS ---
def tool_fetch_companies(_input: str = "") -> str:
    """Returns a list of companies open in Tally."""
    comps = TallyWorkerAgent().fetch_companies()
    return json.dumps(comps)

def tool_analyze_visual(input_str: str) -> str:
    """
    Generate CHARTS.
    Input must be a JSON string: {"company": "Name", "query": "User Question", "report_type": "Tally Report Name"}
    """
    try:
        cleaned_input = input_str.replace("'", '"')
        try: payload = json.loads(cleaned_input)
        except: payload = ast.literal_eval(input_str)
        
        company = payload.get("company")
        query = payload.get("query")
        report_type = payload.get("report_type")

        print(f"⚙️ [Visual] Fetching {report_type}...")
        fetch_res = json.loads(TALLY_AGENT.fetch_report(company, report_type))
        if fetch_res.get("status") == "error": return f"Error: {fetch_res.get('error')}"
        json_path = fetch_res.get("json_file_path")
        
        print(f"⚙️ [Visual] Plotting...")
        chart_res = json.loads(CHART_AGENT.create_charts(json_path, query))
        image_paths = chart_res.get("images", [])
        rationale = chart_res.get("rationale", "")
        
        print(f"⚙️ [Visual] Summarizing...")
        final_ans = SUMMARIZER_AGENT.analyze_visual(query, json_path, image_paths, rationale)
        
        return f"ANALYSIS:\n{final_ans}\n\n[Charts]: {', '.join(image_paths)}"
    except Exception as e: return f"Error in visual tool: {str(e)}"

def tool_analyze_table(input_str: str) -> str:
    """
    Generate TABLES.
    Input must be a JSON string: {"company": "Name", "query": "User Question"}
    """
    try:
        cleaned_input = input_str.replace("'", '"')
        try: payload = json.loads(cleaned_input)
        except: payload = ast.literal_eval(input_str)

        company = payload.get("company")
        query = payload.get("query")
        
        # Smart Lookup
        correct_report_name = lookup_tally_report.invoke(query)
        
        fetch_res = json.loads(TALLY_AGENT.fetch_report(company, correct_report_name))
        json_path = fetch_res.get("json_file_path")
        
        print(f"⚙️ [Table] Generating table from {correct_report_name}...")
        table_res = json.loads(TABLE_AGENT.create_table(json_path, query))
        
        if table_res.get("status") == "error":
             return f"Error: {table_res.get('message')}"
             
        image_paths = table_res.get("images", [])
        return f"ANALYSIS: Table generated for {correct_report_name}.\n\n[Charts]: {', '.join(image_paths)}"
    except Exception as e: return f"Error in table tool: {str(e)}"

def tool_analyze_text_only(input_str: str) -> str:
    """
    Text-based lookup.
    Input: {"company": "Name", "query": "Question", "report_type": "Report Name"}
    """
    try:
        cleaned_input = input_str.replace("'", '"')
        try: payload = json.loads(cleaned_input)
        except: payload = ast.literal_eval(input_str)
        
        company = payload.get("company")
        query = payload.get("query")
        report_type = payload.get("report_type")

        fetch_res = json.loads(TALLY_AGENT.fetch_report(company, report_type))
        if fetch_res.get("status") == "error": return f"Error: {fetch_res.get('error')}"
        
        json_path = fetch_res.get("json_file_path")
        final_ans = SUMMARIZER_AGENT.analyze_text_only(query, json_path)
        return f"ANSWER:\n{final_ans}"
    except Exception as e: return f"Error: {str(e)}"

# --- TOOLS LIST ---
TOOLS = [
    Tool(
        name="list_companies",
        func=tool_fetch_companies,
        description="Returns list of active companies."
    ),
    Tool(
        name="analyze_visual",
        func=tool_analyze_visual,
        description="Generates CHARTS. Input JSON: {'company': '...', 'query': '...', 'report_type': '...'}"
    ),
    Tool(
        name="analyze_table",
        func=tool_analyze_table,
        description="Generates TABLES. Input JSON: {'company': '...', 'query': '...'}"
    ),
    Tool(
        name="analyze_text_only",
        func=tool_analyze_text_only,
        description="Analyzes specific text values. Input JSON: {'company': '...', 'query': '...', 'report_type': '...'}"
    )
]

class SupervisorAgent:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp", 
            google_api_key=api_key, 
            temperature=0
        )
        
        self.memory = ConversationBufferMemory(
            memory_key="chat_history", 
            return_messages=True
        )
        
        self.active_company = None
        
        # --- FIXED PROMPT TEMPLATE ---
        # Removed {active_company} from here to avoid input errors.
        # We will inject the company name directly into {input}
        template = """
Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action (must be valid JSON)
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question. If images are returned, include them.

Begin!

User Input: {input}

AVAILABLE REPORT TYPES for 'report_type':
""" + REPORT_DEFINITIONS + """

Chat History:
{chat_history}

Thought:{agent_scratchpad}
"""
        
        prompt = PromptTemplate.from_template(template)
        
        agent = create_react_agent(self.llm, TOOLS, prompt)
        
        self.agent_executor = AgentExecutor(
            agent=agent, 
            tools=TOOLS, 
            verbose=True, 
            memory=self.memory, 
            handle_parsing_errors=True
        )

    def set_active_company(self, company_name):
        self.active_company = company_name

    def get_companies(self):
        try:
            return json.loads(tool_fetch_companies())
        except:
            return []

    def chat(self, user_input):
        if not self.active_company:
            return "Please select a company first."
        
        # --- THE FIX: Merge company into the single 'input' string ---
        # This satisfies LangChain's requirement for a single input key.
        augmented_input = (
            f"User Question: {user_input}\n"
            f"Context: The Active Company is '{self.active_company}'. "
            f"Always include this company name in your tool inputs."
        )
        
        try:
            # We only pass 'input', avoiding the "multiple keys" error
            response = self.agent_executor.invoke({"input": augmented_input})
            return response['output']
        except Exception as e:
            return f"Agent Error: {str(e)}"