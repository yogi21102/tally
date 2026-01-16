# tools/summarization_tool.py
from langchain.tools import tool
from dotenv import load_dotenv
import google.generativeai as genai
import os

load_dotenv()

# Configure once at module level if possible
API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)

@tool("summarize_text")
def summarize_text(text: str, focus: str = "general financial insights") -> str:
    """
    Uses an LLM to summarize complex text or JSON data.
    
    Args:
        text: The raw data or text to summarize (e.g., JSON output from Tally).
        focus: (Optional) The specific angle to analyze (e.g., "profitability", "anomalies", "spending trends").
    """
    if not API_KEY:
        return "Error: Missing GEMINI_API_KEY in .env"

    try:
        # Fallback to Flash for speed and large context window (1M tokens)
        model_name = os.getenv("GEMINI_MODEL") or "gemini-2.0-flash-exp"
        model = genai.GenerativeModel(model_name)
        
        prompt = f"""
        ROLE: You are an expert Chartered Accountant (CA) and Financial Analyst.
        
        TASK: Analyze the provided data and generate a summary focusing on: "{focus}".
        
        DATA:
        {text[:100000]} # Truncate safety limit if data is massively huge
        
        GUIDELINES:
        - If the data is JSON, interpret the keys (e.g., 'Dr' = Debit, 'Cr' = Credit).
        - Highlight any red flags or anomalies.
        - Use bullet points for readability.
        - Be concise and professional.
        """
        
        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        return f"Error generating summary: {str(e)}"