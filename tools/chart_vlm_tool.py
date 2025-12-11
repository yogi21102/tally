import os
import json
import re
import math
import google.generativeai as genai
from langchain.tools import tool
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

load_dotenv()

PLOTS_DIR = "generated_plots"
os.makedirs(PLOTS_DIR, exist_ok=True)

class FinancialPlotter:
    """
    A robust plotting engine that draws professional charts using PIL.
    Handles negative values, auto-scaling, grids, and legends.
    """
    def __init__(self):
        self.width = 1000
        self.height = 700
        self.padding = 80
        self.colors = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#3B1F2B', '#5B8C5A']
        self.bg_color = 'white'
        self.text_color = '#333333'

    def _get_font(self, size):
        try: return ImageFont.truetype("arial.ttf", size)
        except: return ImageFont.load_default()

    def _draw_text_centered(self, draw, x, y, text, size, color='black', anchor="mm"):
        font = self._get_font(size)
        draw.text((x, y), str(text), fill=color, font=font, anchor=anchor)

    def create_bar_chart(self, data: dict, title: str) -> str:
        """Draws a professional bar chart with auto-scaling and gridlines."""
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # 1. Title
        self._draw_text_centered(draw, self.width/2, 40, title, 24, anchor="mt")
        
        # 2. Filter & Scale Data
        valid_items = {k: v for k, v in data.items() if isinstance(v, (int, float))}
        if not valid_items: return "Error: No numeric data"
        
        keys = list(valid_items.keys())[:8] # Limit to 8 items
        values = list(valid_items.values())[:8]
        
        max_val = max(max(values), 0)
        min_val = min(min(values), 0)
        y_range = max_val - min_val if max_val != min_val else 1.0
        
        # Chart Dimensions
        top, bottom = self.padding + 50, self.height - self.padding
        left, right = self.padding, self.width - self.padding
        h_avail = bottom - top
        
        scale = h_avail / y_range
        zero_y = bottom - ((0 - min_val) * scale) # Calculate Zero Line Position

        # 3. Draw Gridlines (5 steps)
        for i in range(6):
            val = min_val + (y_range * i / 5)
            y = bottom - ((val - min_val) * scale)
            draw.line([(left, y), (right, y)], fill='#e0e0e0', width=1)
            self._draw_text_centered(draw, left - 10, y, f"{val:,.0f}", 12, anchor="rm")

        # 4. Draw Bars
        bar_width = (right - left) / len(keys) * 0.6
        spacing = (right - left) / len(keys)
        
        for i, (k, v) in enumerate(zip(keys, values)):
            center_x = left + (i * spacing) + (spacing / 2)
            bar_h = abs(v) * scale
            
            # Determine Top/Bottom based on positive/negative
            if v >= 0:
                rect_top, rect_bot = zero_y - bar_h, zero_y
            else:
                rect_top, rect_bot = zero_y, zero_y + bar_h
                
            # Draw Bar
            color = self.colors[i % len(self.colors)]
            draw.rectangle([center_x - bar_width/2, rect_top, center_x + bar_width/2, rect_bot], fill=color)
            
            # Label Value
            label_y = rect_top - 15 if v >= 0 else rect_bot + 15
            self._draw_text_centered(draw, center_x, label_y, f"{v:,.0f}", 12)
            
            # Label Category (Wrap text if needed)
            label = k[:12] + "..." if len(k) > 12 else k
            self._draw_text_centered(draw, center_x, bottom + 20, label, 12, anchor="mt")

        # Draw Zero Line
        draw.line([(left, zero_y), (right, zero_y)], fill='black', width=2)
        
        filename = f"{PLOTS_DIR}/chart_bar_{len(os.listdir(PLOTS_DIR))}.png"
        img.save(filename)
        return filename

    def create_pie_chart(self, data: dict, title: str) -> str:
        """Draws a professional pie chart."""
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        self._draw_text_centered(draw, self.width/2, 40, title, 24, anchor="mt")
        
        # Filter for positive values only
        valid_items = {k: v for k, v in data.items() if isinstance(v, (int, float)) and v > 0}
        total = sum(valid_items.values())
        if total == 0: return self.create_bar_chart(data, title) # Fallback to bar if negatives exist

        # Layout
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

def execute_pil_code(code_str):
    """Executes code with FinancialPlotter injected."""
    # We inject our robust class so the AI just calls it
    scope = {"FinancialPlotter": FinancialPlotter, "json": json}
    try:
        exec(code_str, scope, scope)
        if 'draw_chart' in scope:
            return scope['draw_chart']()
        return []
    except Exception as e:
        print(f"❌ Execution Error: {e}")
        return []

@tool("generate_vlm_charts")
def generate_vlm_charts(json_file_path: str) -> str:
    """Analyzes JSON and draws charts using the Helper Class."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key: return json.dumps({"error": "Missing API Key"})
    
    if not os.path.exists(json_file_path): return json.dumps({"error": "File not found"})

    with open(json_file_path, "r", encoding="utf-8") as f: data = json.load(f)

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('models/gemini-2.0-flash')

    prompt = f"""
    You are a Data Analyst.
    
    DATA: {json.dumps(data, indent=2)[:5000]} 

    TASK:
    1. Select the **1 best chart type** (Bar or Pie) to show the main insight.
    2. Write a Python script that uses the `FinancialPlotter` class.
    
    API USAGE:
    - **Step 1**: `plotter = FinancialPlotter()`
    - **Step 2**: Create a clean dictionary `data = {{...}}` with numeric values only.
    - **Step 3**: Call `plotter.create_bar_chart(data, "Title")` OR `plotter.create_pie_chart(data, "Title")`.
    - **Step 4**: Return the list of filenames.

    OUTPUT FORMAT:
    ```python
    def draw_chart():
        # Define Data
        data = {{ "Assets": 50000, "Liabilities": 30000 }} 
        
        # Draw
        plotter = FinancialPlotter()
        f1 = plotter.create_bar_chart(data, "Financial Overview")
        return [f1]
    ```
    """

    try:
        response = model.generate_content(prompt)
        match = re.search(r"```python\n(.*?)```", response.text, re.DOTALL)
        
        rationale = "Generated using FinancialPlotter"
        if match:
            image_paths = execute_pil_code(match.group(1))
            return json.dumps({"status": "ok", "rationale": rationale, "images": image_paths})
        return json.dumps({"error": "No code block found"})

    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})
    
    