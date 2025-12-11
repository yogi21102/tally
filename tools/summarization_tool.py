# tools/summarization_tool.py
from langchain.tools import tool
from dotenv import load_dotenv
import google.generativeai as genai
import os

load_dotenv()

@tool("summarize_text")
def summarize_text(text: str) -> str:
    """
    Summarize text using Gemini.
    """
    # FIX: Check both key names to be safe
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if not api_key:
        return "Error: Missing GEMINI_API_KEY or GOOGLE_API_KEY in .env"

    try:
        genai.configure(api_key=api_key)
        # Use a fallback model if the specific one isn't set
        model_name = os.getenv("GEMINI_MODEL") or "gemini-1.5-flash"
        
        model = genai.GenerativeModel(model_name)
        prompt = f"Summarize this Tally financial report data into clear insights:\n\n{text}"
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Summary failed: {str(e)}"