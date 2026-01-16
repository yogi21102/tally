from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import os
import re

# Import your existing Agent logic
from SupervisorAgent import SupervisorAgent

app = FastAPI(title="Tally Smart Agent API", version="1.0")

# --- ENABLE CORS (Crucial for React) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURATION ---
HARDCODED_COMPANY = "Modi Chemplast Materials Pvt Ltd"

class ChatRequest(BaseModel):
    query: str
    chat_history: Optional[List[str]] = []

class ChatResponse(BaseModel):
    response_text: str
    image_paths: List[str]
    status: str

agent = SupervisorAgent()

@app.get("/")
def health_check():
    return {"status": "running", "service": "Tally Agent API", "active_company": HARDCODED_COMPANY}

@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    try:
        print(f"📥 Received Query: {request.query}")
        
        # 1. Set Context
        agent.set_active_company(HARDCODED_COMPANY)
        
        # 2. Run Agent
        raw_response = agent.chat(request.query)
        print("✅ Agent finished.")

        # 3. Parse Response
        clean_text = raw_response
        image_files = []
        
        # Regex to find [Charts]: path/to/image.png
        match = re.search(r"\[Charts\]: (.*?)(?:\n|$)", raw_response, re.IGNORECASE)
        if match:
            path_str = match.group(1)
            # Remove tag from text
            clean_text = raw_response.replace(match.group(0), "").strip()
            
            paths = path_str.split(",")
            for p in paths:
                p = p.strip()
                if p: 
                    # --- CRITICAL FIX: FORCE FORWARD SLASHES ---
                    # Windows paths use '\', but URLs must use '/'
                    safe_path = p.replace("\\", "/")
                    image_files.append(safe_path)
        
        print(f"📤 Sending Response: '{clean_text}' | Images={image_files}")

        return {
            "response_text": clean_text,
            "image_paths": image_files,
            "status": "success"
        }

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return {
            "response_text": f"Error processing request: {str(e)}",
            "image_paths": [],
            "status": "error"
        }

# --- SERVE IMAGES ---
os.makedirs("generated_plots", exist_ok=True)
app.mount("/generated_plots", StaticFiles(directory="generated_plots"), name="images")

if __name__ == "__main__":
    import uvicorn
    # Listen on all interfaces to ensure ngrok connects properly
    uvicorn.run(app, host="0.0.0.0", port=8000)