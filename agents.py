import json
import logging
import os
from typing import Any, Dict, List, Optional
import google.generativeai as genai
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

try:
    from tools.company_list_tool import get_company_list
    from tools.get_report_tool import get_report
    from tools.chart_vlm_tool import generate_vlm_charts
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from tools.company_list_tool import get_company_list
    from tools.get_report_tool import get_report
    from tools.chart_vlm_tool import generate_vlm_charts

logger = logging.getLogger(__name__)

class TallyWorkerAgent:
    def __init__(self, *, retry: int = 1):
        self.retry = max(1, int(retry))

    def fetch_companies(self) -> List[Dict[str, Any]]:
        try:
            names = get_company_list.invoke({})
            if isinstance(names, list):
                return [{"name": n, "id": n} for n in names]
            return []
        except Exception as e:
            logger.error(f"Error fetching companies: {e}")
            return []

    def fetch_report(self, company_name: str, report_name: str) -> str:
        try:
            logger.info(f"Fetching report '{report_name}' for '{company_name}'")
            raw = get_report.invoke({"company_name": company_name, "report_name": report_name})
            
            safe_co = "".join([c for c in company_name if c.isalnum()]).strip()
            safe_rep = "".join([c for c in report_name if c.isalnum()]).strip()
            filename = f"data_{safe_co}_{safe_rep}.json"
            
            data_to_save = raw
            if isinstance(raw, str):
                try: data_to_save = json.loads(raw)
                except: data_to_save = {"raw": raw}
            
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, indent=4)
            
            return json.dumps({"status": "ok", "json_file_path": filename})
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e)})

class ChartAgent:
    def create_charts(self, json_file_path: str) -> str:
        try:
            logger.info(f"Generating charts from {json_file_path}")
            return generate_vlm_charts.invoke({"json_file_path": json_file_path})
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e)})

class SummarizerAgent:
    def __init__(self):
        # Read from ENV
        self.model_name = os.getenv("GEMINI_MODEL") or "models/gemini-2.0-flash"

    def analyze_visual(self, query: str, json_file_path: str, image_paths: List[str], rationale: str) -> str:
        return self._run_gemini(query, json_file_path, image_paths, rationale)

    def analyze_text_only(self, query: str, json_file_path: str) -> str:
        return self._run_gemini(query, json_file_path, [], "No charts needed.")

    def _run_gemini(self, query, json_path, image_paths, rationale):
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(self.model_name)

        data_text = ""
        if os.path.exists(json_path):
            with open(json_path, 'r') as f:
                data_text = f.read()

        images = []
        for path in image_paths:
            if os.path.exists(path):
                images.append(Image.open(path))

        prompt = [
            f"User Query: {query}",
            f"Context: {rationale}",
            f"Raw Data: {data_text[:5000]}",
            "INSTRUCTIONS:",
            "1. Answer the query precisely based on the Raw Data.",
            "2. If charts (images) are provided, reference them explicitly.",
            "3. If NO charts are provided, simply state the facts/values requested."
        ]
        
        try:
            response = model.generate_content(prompt + images)
            return response.text
        except Exception as e:
            return f"Analysis failed: {e}"