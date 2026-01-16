# tools/chart_vlm_tool.py
import os
import json
import re
import math
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

load_dotenv()

# --- CONFIGURATION ---
PLOTS_DIR = "generated_plots"
os.makedirs(PLOTS_DIR, exist_ok=True)

class generate_vlm_charts:
    """
    A robust plotting engine that draws professional charts using PIL.
    Acts as both the Drawing Tool AND the AI Orchestrator.
    """
    def __init__(self):
        # 1. Image Settings
        self.width = 1000
        self.height = 700
        self.padding = 80
        self.colors = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#3B1F2B', '#5B8C5A']
        self.bg_color = 'white'
        self.text_color = '#333333'
        
        # 2. AI Settings (Restored this part)
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        model_name = os.getenv("GEMINI_MODEL") or "models/gemini-2.0-flash-exp"
        self.llm = ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key)

    # --- HELPER: Fonts ---
    def _get_font(self, size):
        try: return ImageFont.truetype("arial.ttf", size)
        except: return ImageFont.load_default()

    def _draw_text_centered(self, draw, x, y, text, size, color='black', anchor="mm"):
        font = self._get_font(size)
        draw.text((x, y), str(text), fill=color, font=font, anchor=anchor)

    # --- HELPER: Bar Chart Logic ---
    def create_bar_chart(self, data: dict, title: str) -> str:
        """Draws a professional bar chart."""
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # Title
        self._draw_text_centered(draw, self.width/2, 40, title, 24, anchor="mt")
        
        # Filter Data
        valid_items = {k: v for k, v in data.items() if isinstance(v, (int, float))}
        if not valid_items: return "Error: No numeric data"
        
        keys = list(valid_items.keys())[:8] 
        values = list(valid_items.values())[:8]
        
        max_val = max(max(values), 0)
        min_val = min(min(values), 0)
        y_range = max_val - min_val if max_val != min_val else 1.0
        
        # Dimensions
        top, bottom = self.padding + 50, self.height - self.padding
        left, right = self.padding, self.width - self.padding
        h_avail = bottom - top
        scale = h_avail / y_range
        zero_y = bottom - ((0 - min_val) * scale)

        # Gridlines
        for i in range(6):
            val = min_val + (y_range * i / 5)
            y = bottom - ((val - min_val) * scale)
            draw.line([(left, y), (right, y)], fill='#e0e0e0', width=1)
            self._draw_text_centered(draw, left - 10, y, f"{val:,.0f}", 12, anchor="rm")

        # Bars
        spacing = (right - left) / len(keys)
        bar_width = spacing * 0.6
        
        for i, (k, v) in enumerate(zip(keys, values)):
            center_x = left + (i * spacing) + (spacing / 2)
            bar_h = abs(v) * scale
            
            rect_top = zero_y - bar_h if v >= 0 else zero_y
            rect_bot = zero_y if v >= 0 else zero_y + bar_h
                
            color = self.colors[i % len(self.colors)]
            draw.rectangle([center_x - bar_width/2, rect_top, center_x + bar_width/2, rect_bot], fill=color)
            
            # Label Value
            label_y = rect_top - 15 if v >= 0 else rect_bot + 15
            self._draw_text_centered(draw, center_x, label_y, f"{v:,.0f}", 12)
            
            # Label Category
            label = k[:12] + "..." if len(k) > 12 else k
            self._draw_text_centered(draw, center_x, bottom + 20, label, 12, anchor="mt")

        # Zero Line
        draw.line([(left, zero_y), (right, zero_y)], fill='black', width=2)
        
        filename = f"{PLOTS_DIR}/chart_bar_{len(os.listdir(PLOTS_DIR))}.png"
        img.save(filename)
        return filename

    # --- HELPER: Pie Chart Logic ---
    def create_pie_chart(self, data: dict, title: str) -> str:
        """Draws a professional pie chart."""
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        self._draw_text_centered(draw, self.width/2, 40, title, 24, anchor="mt")
        
        valid_items = {k: v for k, v in data.items() if isinstance(v, (int, float)) and v > 0}
        total = sum(valid_items.values())
        if total == 0: return self.create_bar_chart(data, title)

        cx, cy = self.width // 2 - 150, self.height // 2
        radius = 220
        bbox = [cx - radius, cy - radius, cx + radius, cy + radius]
        
        start_angle = 0
        keys = list(valid_items.keys())
        values = list(valid_items.values())
        
        for i, (k, v) in enumerate(zip(keys, values)):
            extent = (v / total) * 360
            end_angle = start_angle + extent
            color = self.colors[i % len(self.colors)]
            
            draw.pieslice(bbox, start=start_angle, end=end_angle, fill=color, outline='white')
            
            # Legend
            lx, ly = self.width - 250, 150 + (i * 40)
            draw.rectangle([lx, ly, lx+20, ly+20], fill=color)
            self._draw_text_centered(draw, lx + 30, ly+10, f"{k} ({v/total:.1%})", 14, anchor="lm")
            start_angle = end_angle

        filename = f"{PLOTS_DIR}/chart_pie_{len(os.listdir(PLOTS_DIR))}.png"
        img.save(filename)
        return filename

    # --- MAIN ORCHESTRATOR (Fixes the Agent Error) ---
    def generate_chart(self, json_path: str, query: str = "Analyze data") -> str:
        """
        1. Reads JSON.
        2. Asks LLM how to plot it.
        3. Executes the plotting code using 'self' as the plotter.
        """
        try:
            if not os.path.exists(json_path):
                return json.dumps({"status": "error", "message": "File not found"})

            with open(json_path, 'r', encoding="utf-8") as f:
                raw_data = json.load(f)

            # 1. Prompt the LLM
            prompt = f"""
            You are a Data Visualization Expert.
            
            USER QUERY: "{query}"
            DATA SAMPLE: {json.dumps(raw_data, indent=2)[:1500]}...

            TASK:
            1. Analyze the data and choose the best chart (Bar or Pie).
            2. Write Python code to extract data from `raw_data` variable.
            3. Call `generate_vlm_charts.create_bar_chart(data_dict, title)` or `generate_vlm_charts.create_pie_chart(data_dict, title)`.
            
            RULES:
            - `plotter` is already defined (it is 'self').
            - `raw_data` is already defined (injected globally).
            - Create a dictionary `chart_data` with clean numeric values.
            - Return ONLY the function definition `draw()`.

            EXAMPLE OUTPUT:
            ```python
            def draw():
                # Extract
                chart_data = {{ item["Name"]: float(item["Amount"]) for item in raw_data if "Amount" in item }}
                # Plot
                return plotter.create_bar_chart(chart_data, "Stock Summary")
            ```
            """
            
            response = self.llm.invoke(prompt)
            code_match = re.search(r"```python\n(.*?)```", response.content, re.DOTALL)
            
            if not code_match:
                return json.dumps({"status": "error", "message": "No code generated"})

            code = code_match.group(1)
            
           # 2. Execute Code
            # Define a restricted scope
            safe_scope = {
                "plotter": self,
                "raw_data": raw_data,
                "json": json,
                "math": math,
                "print": print # Allowed for debugging
            }
            
            # Execute
            try:
                exec(code, safe_scope)
                if 'draw' in safe_scope:
                    image_path = safe_scope['draw']()
                    return json.dumps({
                        "status": "success", 
                        "images": [image_path],
                        "rationale": "Chart generated."
                    })
                else:
                    return json.dumps({"status": "error", "message": "No draw() function found"})
            except Exception as exec_err:
                 return json.dumps({"status": "error", "message": f"Code execution failed: {exec_err}"})

        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

# Support for standalone testing
if __name__ == "__main__":
    p = generate_vlm_charts()
    # Create dummy file
    with open("test.json", "w") as f: json.dump([{"Name": "A", "Value": 10}, {"Name": "B", "Value": 20}], f)
    print(p.generate_chart("test.json", "Pie chart of values"))