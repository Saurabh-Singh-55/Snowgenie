# app.py – Streamlit thin client (pretty chat UI)

import streamlit as st
import requests, socket, json, datetime
from typing import List, Tuple
import re

from constants import (
    LLM_SERVER_URL,
    DEFAULT_LLM_MODEL,
    MCP_SERVER_HOST,
    MCP_SERVER_PORT,
    DEFAULT_USER,
    FALLBACK_MODELS,
)

# ───────────────────── utility helpers ─────────────────────
def check_server(url: str) -> bool:
    try:  # noqa: S310
        return requests.get(f"{url}/health", timeout=2).status_code == 200
    except Exception:
        return False

def check_mcp_server(host: str, port: int, timeout: float = 1) -> bool:
    try:
        with socket.create_connection((host, port), timeout):
            return True
    except OSError:
        return False

def fetch_available_models() -> List[str]:
    try:
        r = requests.get(f"{LLM_SERVER_URL}/models", timeout=5)
        r.raise_for_status()
        return r.json().get("models", FALLBACK_MODELS) or FALLBACK_MODELS
    except Exception:
        return FALLBACK_MODELS

def refresh_schema_cache():
    """Refresh the Snowflake schema cache by running the initialization script."""
    try:
        import subprocess
        import sys
        
        # Run the initialization script
        process = subprocess.run(
            [sys.executable, "SnowMCP_initialize.py"],
            capture_output=True,
            text=True
        )
        
        if process.returncode == 0:
            st.sidebar.success("Schema cache refreshed successfully!")
            # Add more detailed success info if available
            if process.stdout:
                with st.sidebar.expander("Refresh Details"):
                    st.code(process.stdout)
        else:
            st.sidebar.error("Failed to refresh schema cache.")
            with st.sidebar.expander("Error Details"):
                st.error(process.stderr)
    except Exception as e:
        st.sidebar.error(f"Error refreshing cache: {str(e)}")

# ───────────────────── status badge sidebar ─────────────────────
def draw_status():
    llm_ok = check_server(LLM_SERVER_URL)
    llm_icon, llm_lbl, llm_color = ("🟢", "Connected", "#0a7b3e") if llm_ok else ("🔴", "Offline", "#d32f2f")

    mcp_icon, mcp_lbl, mcp_color = "⚪", "Not Configured", "#6b7280"
    if "mcp_host" in st.session_state:
        mcp_ok = check_mcp_server(st.session_state.mcp_host, st.session_state.mcp_port)
        mcp_icon, mcp_lbl, mcp_color = ("🟢", "Connected", "#0a7b3e") if mcp_ok else ("🔴", "Offline", "#d32f2f")

    model_icon, model_lbl, model_color = "⚪", "Unknown", "#6b7280"
    if "model_status" in st.session_state:
        model_icon = "🟢" if st.session_state.model_status else "🔴"
        model_lbl = "Available" if st.session_state.model_status else "Unavailable"
        model_color = "#0a7b3e" if st.session_state.model_status else "#d32f2f"

    st.sidebar.markdown("### Servers Status")
    st.sidebar.markdown(f"""<div style="display: flex; align-items: center; margin-bottom: 0.5rem;">
        <div style="min-width: 95px; font-weight: 500; color: #475569;">LLM Server:</div>
        <div style="display: inline-flex; align-items: center; background-color: #f8fafc; 
        border-radius: 0.5rem; padding: 0.25rem 0.75rem; border: 1px solid #e2e8f0;">
        {llm_icon} <span style="font-weight: 600; color: {llm_color}; margin-left: 0.25rem;">{llm_lbl}</span>
        </div></div>""", unsafe_allow_html=True)
    
    st.sidebar.markdown(f"""<div style="display: flex; align-items: center; margin-bottom: 0.5rem;">
        <div style="min-width: 95px; font-weight: 500; color: #475569;">MCP Server:</div>
        <div style="display: inline-flex; align-items: center; background-color: #f8fafc; 
        border-radius: 0.5rem; padding: 0.25rem 0.75rem; border: 1px solid #e2e8f0;">
        {mcp_icon} <span style="font-weight: 600; color: {mcp_color}; margin-left: 0.25rem;">{mcp_lbl}</span>
        </div></div>""", unsafe_allow_html=True)
    
    st.sidebar.markdown(f"""<div style="display: flex; align-items: center; margin-bottom: 0.5rem;">
        <div style="min-width: 95px; font-weight: 500; color: #475569;">Gemini Model:</div>
        <div style="display: inline-flex; align-items: center; background-color: #f8fafc; 
        border-radius: 0.5rem; padding: 0.25rem 0.75rem; border: 1px solid #e2e8f0;">
        {model_icon} <span style="font-weight: 600; color: {model_color}; margin-left: 0.25rem;">
        {st.session_state.get('model_name','—')}</span>
        </div></div>""", unsafe_allow_html=True)
    
    st.sidebar.markdown(f"""<div style="color: #94a3b8; font-size: 0.75rem; margin-top: 0.5rem;">
    Updated at {datetime.datetime.now():%H:%M:%S}</div>""", unsafe_allow_html=True)

# ───────────────────── session bootstrap ────────────────────
def bootstrap_session():
    if "session_id" in st.session_state:
        return

    st.session_state.update(
        mcp_host=MCP_SERVER_HOST,
        mcp_port=MCP_SERVER_PORT,
        user_name=DEFAULT_USER,
        model_name=DEFAULT_LLM_MODEL,
        model_status=False,
    )

    mcp_url = f"http://{MCP_SERVER_HOST}:{MCP_SERVER_PORT}/sse"
    try:
        res = requests.post(
            f"{LLM_SERVER_URL}/create_session",
            json={"mcp_server": mcp_url, "model_name": DEFAULT_LLM_MODEL},
            timeout=6,
        )
        res.raise_for_status()
        data = res.json()
        st.session_state.session_id = data["session_id"]
        st.session_state.model_status = data.get("model_status", False)
        st.success("LLM session established.")
    except Exception as e:
        st.session_state.session_id = None
        st.error(f"Cannot create session: {e}")

# ───────────────────── sidebar configuration ─────────────────
st.sidebar.markdown("""<h2 style="color: #1e293b; font-weight: 600; margin-bottom: 1rem;">Configuration</h2>""", unsafe_allow_html=True)

# Gemini model selector
with st.sidebar.expander("🤖 Gemini AI Model", True):
    models = fetch_available_models()
    idx = models.index(st.session_state.get("model_name", DEFAULT_LLM_MODEL)) if st.session_state.get("model_name") in models else 0
    choice = st.selectbox("Select Gemini model", models, index=idx, key="model_choice", 
                         help="Choose from available Google Gemini models")
    if st.button("Apply Model", type="primary"):
        st.session_state.model_name = choice
        # Simply update the model name without testing with empty prompt
        # since Gemini doesn't accept empty prompts
        st.session_state.model_status = True  # Assume model is available if API key is configured
        st.sidebar.success("Gemini model updated!")

# MCP server
with st.sidebar.expander("MCP Server"):
    h = st.text_input("Host", st.session_state.get("mcp_host", MCP_SERVER_HOST))
    p = st.number_input("Port", value=st.session_state.get("mcp_port", MCP_SERVER_PORT), step=1)
    if st.button("Apply MCP", type="primary"):
        st.session_state.update(mcp_host=h, mcp_port=int(p))
        # Update MCP configuration without sending empty prompt
        # Will be applied on next actual query
        st.sidebar.success("MCP endpoint updated.")

# user name
with st.sidebar.expander("User"):
    name = st.text_input("Name", st.session_state.get("user_name", DEFAULT_USER))
    if st.button("Apply User", type="primary"):
        st.session_state.user_name = name
        st.sidebar.success("User name saved.")

if st.sidebar.button("🔄 Refresh Status", type="secondary"):
    draw_status()

# Add this after the "Refresh Status" button in the sidebar
if st.sidebar.button("🔄 Refresh Schema Cache", type="secondary", help="Rebuild the Snowflake schema cache"):
    refresh_schema_cache()

# ───────────────────── main chat area ──────────────────────
st.markdown("""
<h1 style="color: #0f172a; font-weight: 700; border-bottom: 2px solid #3366ff; 
padding-bottom: 0.5rem; margin-bottom: 1.5rem;">🚀 SnowGenie AI Assistant</h1>
<p style="color: #64748b; font-size: 1.1rem; margin-bottom: 1.5rem;">
Powered by Google Gemini AI for intelligent data insights
</p>
""", unsafe_allow_html=True)

bootstrap_session()
draw_status()

if "messages" not in st.session_state:
    st.session_state.messages = []

# show history
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# ---------- helpers to consume SSE stream ----------
def stream_agent(prompt: str):
    """Yield (kind, content) tuples from SSE."""
    resp = requests.post(
        f"{LLM_SERVER_URL}/query",
        json={"session_id": st.session_state.session_id, "prompt": prompt, "stream": True},
        headers={"Accept": "text/event-stream"},
        stream=True,
        timeout=60,
    )
    for raw in resp.iter_lines(decode_unicode=True):
        if not raw or not raw.startswith("data:"):
            continue
        data = json.loads(raw.removeprefix("data:").strip())
        if data.get("done"):
            break
        yield data["kind"], data["content"]

def render_chunk(kind: str, text: str, container):
    """Render different kinds of response chunks with interactive elements and styled badges."""

    print(f"Rendering chunk: {kind}")
    if kind == "tool":
        container.markdown(
            f"""<div style="display: inline-flex; align-items: center; background-color: #f7f9fc; 
            border-radius: 0.5rem; padding: 0.5rem; margin-bottom: 0.5rem; border-left: 4px solid #3366ff;">
            <span style="font-weight: bold; margin-right: 0.5rem; color: #3366ff;">🛠️ TOOL CALL</span>
            <code style="background-color: #1e293b; color: #e2e8f0; padding: 0.25rem 0.5rem; 
            border-radius: 0.25rem; font-family: monospace;">{text}</code>
            </div>""", unsafe_allow_html=True)
    
    elif kind == "function":
        # Instead of using expander which might have issues, use a custom collapsible layout
        try:
            # Try to parse JSON for prettier display
            json_data = json.loads(text)
            json_str = json.dumps(json_data, indent=2)
            container.markdown(
                f"""<details style="margin-bottom: 1rem;">
                <summary style="background-color: #f7f9fc; padding: 0.5rem; border-radius: 0.5rem 0.5rem 0 0; 
                font-weight: 600; cursor: pointer; border: 1px solid #e2e8f0; border-bottom: none; color: #1e293b;">
                Tool Response</summary>
                <div style="background-color: #f8fafc; padding: 1rem; border: 1px solid #e2e8f0; 
                border-radius: 0 0 0.5rem 0.5rem;">
                <pre style="background-color: #f1f5f9; padding: 0.75rem; border-radius: 0.25rem; overflow: auto;"><code>{json_str}</code></pre>
                </div></details>""", unsafe_allow_html=True)
        except json.JSONDecodeError:
            # Fall back to code display if not valid JSON
            container.markdown(
                f"""<details style="margin-bottom: 1rem;">
                <summary style="background-color: #f7f9fc; padding: 0.5rem; border-radius: 0.5rem 0.5rem 0 0; 
                font-weight: 600; cursor: pointer; border: 1px solid #e2e8f0; border-bottom: none; color: #1e293b;">
                Tool Response</summary>
                <div style="background-color: #f8fafc; padding: 1rem; border: 1px solid #e2e8f0; 
                border-radius: 0 0 0.5rem 0.5rem;">
                <pre style="background-color: #f1f5f9; padding: 0.75rem; border-radius: 0.25rem; overflow: auto;"><code>{text}</code></pre>
                </div></details>""", unsafe_allow_html=True)
    
    elif kind == "think":
        # Use direct styling instead of expander
        # Extract thinking and answer parts
        thinking_parts = re.findall(r"<think>(.*?)</think>", text, re.DOTALL)
        thinking_content = "\n".join(t.strip() for t in thinking_parts) if thinking_parts else ""
        answer_content = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        
        container.markdown(
            f"""<div style="background-color: #f8fafc; border-radius: 0.5rem; padding: 1rem; 
            border-left: 4px solid #667eea; margin-top: 0.5rem; color: #334155;">
            <div style="font-weight: 600; margin-bottom: 0.5rem; color: #4f46e5;">🧠 Reasoning Process</div>
            {thinking_content}</div>
            <div style="background-color: #f8fafc; border-radius: 0.5rem; padding: 1rem; 
            border-left: 4px solid #8B4513; margin-top: 0.5rem; color: #334155;">
            <div style="font-weight: 600; margin-bottom: 0.5rem; color: #8B4513;">Final Answer</div>
            {answer_content}</div>""", 
            unsafe_allow_html=True
        )
    
    elif kind == "answer" or kind == "chunk":
        # Treat both chunk and answer types the same way since the LLM server doesn't distinguish them
        container.markdown(
            f"""<div style="background-color: #f0f7ff; border-radius: 0.5rem; padding: 1rem; 
            border-left: 4px solid #0050e6; margin-top: 0.5rem; color: #1e293b;">{text}</div>""", 
            unsafe_allow_html=True
        )

# ---------- input ----------
if st.session_state.get("model_status"):
    user_prompt = st.chat_input("Ask me anything about your Snowflake data with Gemini AI…", key="chat_input")
else:
    user_prompt = None
    st.markdown("""
    <div style="background-color: #fff8f1; border-left: 4px solid #f59e0b; padding: 1rem; 
    border-radius: 0.5rem; margin: 1rem 0;">
      <div style="display: flex; align-items: center;">
        <span style="font-size: 1.25rem; margin-right: 0.5rem;">⚠️</span>
        <span style="font-weight: 600; color: #92400e;">Gemini AI Unavailable</span>
      </div>
      <p style="color: #92400e; margin-top: 0.5rem; margin-bottom: 0;">
        Please check your Gemini API key configuration and ensure the model is properly loaded.
      </p>
    </div>
    """, unsafe_allow_html=True)

if user_prompt:
    # echo user
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    # assistant stream container
    with st.chat_message("assistant"):
        outer_box = st.container()
        live_answer = ""
        thinking_displayed = False
        
        for k, cnt in stream_agent(user_prompt):
            # Handle various response types
            if k == "chunk":
                # Accumulate the answer text
                live_answer += cnt
                # Update the display
                final_container = outer_box.container()
                final_container.empty()
                final_container.markdown(
                    f"""<div style="background-color: #f0f7ff; border-radius: 0.5rem; padding: 1rem; 
                    border-left: 4px solid #0050e6; margin-top: 0.5rem; color: #1e293b;">{live_answer}</div>""", 
                    unsafe_allow_html=True
                )
            elif k == "think" and not thinking_displayed:
                # Only show the thinking process once
                thinking_displayed = True
                render_chunk(k, cnt, outer_box)
            elif k in ["tool", "function"]:
                # Always show tool calls and function outputs
                render_chunk(k, cnt, outer_box)

        # final answer stored
        st.session_state.messages.append({"role": "assistant", "content": cnt})
