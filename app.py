import streamlit as st
import re
import os
# Import the SupervisorAgent class
from SupervisorAgent import SupervisorAgent

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Tally Financial AI", page_icon="📊", layout="wide")

# --- INITIALIZATION ---
# Create plots directory if missing
if not os.path.exists("generated_plots"):
    os.makedirs("generated_plots")

@st.cache_resource
def get_agent_instance():
    return SupervisorAgent()

agent = get_agent_instance()

# Session State
if "messages" not in st.session_state: st.session_state.messages = []
if "active_company" not in st.session_state: st.session_state.active_company = None
if "company_list" not in st.session_state: st.session_state.company_list = []

# --- SIDEBAR ---
with st.sidebar:
    st.header("🏢 Tally Connection")
    
    col1, col2 = st.columns([3,1])
    with col1:
        if st.button("🔄 Connect / Refresh"):
            with st.spinner("Connecting to Tally..."):
                raw_companies = agent.get_companies()
                # Handle list of strings or dicts
                cleaned = []
                for c in raw_companies:
                    if isinstance(c, dict): cleaned.append(c.get('name', 'Unknown'))
                    else: cleaned.append(str(c))
                st.session_state.company_list = cleaned
                
                if not cleaned:
                    st.error("No companies found in Tally.")
                else:
                    st.success(f"Found {len(cleaned)} companies.")

    if st.session_state.company_list:
        selected = st.selectbox("Select Company", st.session_state.company_list)
        if selected != st.session_state.active_company:
            st.session_state.active_company = selected
            agent.set_active_company(selected)
            st.rerun()

    st.divider()
    if st.session_state.active_company:
        st.success(f"Active: **{st.session_state.active_company}**")
    else:
        st.warning("Please select a company.")

    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()

# --- CHAT AREA ---
st.title("📊 Tally Financial Assistant")
st.caption("Ask about Balance Sheet, P&L, Stock, or specific ledgers.")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("images"):
            for img_path in msg["images"]:
                if os.path.exists(img_path):
                    st.image(img_path)

if prompt := st.chat_input("Ex: Show me a pie chart of my stock groups"):
    if not st.session_state.active_company:
        st.error("Please connect to a Tally company first.")
        st.stop()

    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            response_text = agent.chat(prompt)
            
            # --- Extract Images ---
            # Regex to find paths like [Charts]: generated_plots/abc.png
            # It handles comma separated paths too
            image_files = []
            
            # 1. Regex find the tag
            match = re.search(r"\[Charts\]: (.*?)(?:\n|$)", response_text, re.IGNORECASE)
            clean_text = response_text
            
            if match:
                path_str = match.group(1)
                clean_text = response_text.replace(match.group(0), "") # Remove tag from text
                
                paths = path_str.split(",")
                for p in paths:
                    p = p.strip()
                    if os.path.exists(p):
                        image_files.append(p)
            
            # Display text
            st.markdown(clean_text)
            
            # Display images
            for img in image_files:
                st.image(img, caption="Generated Visual")

            # Save to history
            st.session_state.messages.append({
                "role": "assistant",
                "content": clean_text,
                "images": image_files
            })