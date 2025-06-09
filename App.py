# app.py – SnowGenie Streamlit thin client (rich history, throttled streaming)

import streamlit as st
import requests, socket, json, datetime, time, re
from typing import List
import threading, queue
from streamlit_autorefresh import st_autorefresh

from constants import (
    LLM_SERVER_URL,
    DEFAULT_LLM_MODEL,
    MCP_SERVER_HOST,
    MCP_SERVER_PORT,
    DEFAULT_USER,
    FALLBACK_MODELS,
)
# ───────────── balloon fragment ─────────────
@st.fragment
def celebrate():
    """Independent fragment: click ⇒ balloons, no full rerun."""
    if st.button("🎈 Celebrate", key="balloon_btn", help="Click to release balloons"):
        st.balloons()

with st.sidebar:
    celebrate()

def start_stream_worker(prompt: str):
    if "stream_q" in st.session_state:      # already running
        return

    # Create a FIFO queue the worker will push tuples (kind, text) into
    st.session_state.stream_q = queue.Queue()
    st.session_state.stream_done = False

    # Capture everything the worker needs *now*, on the main thread
    session_id = st.session_state.session_id

    def worker(prompt, sid, out_q):
        for kind, text in stream_agent(prompt, sid):  # stream_agent now takes sid
            out_q.put((kind, text))
        out_q.put(("__END__", ""))          # sentinel
    threading.Thread(
        target=worker, args=(prompt, session_id, st.session_state.stream_q), daemon=True
    ).start()

# ───────────────────── utility helpers ─────────────────────
def check_server(url: str) -> bool:
    try:
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


def refresh_schema_cache() -> None:
    """Run SnowMCP_initialize.py to rebuild Snowflake schema cache."""
    import subprocess, sys

    proc = subprocess.run([sys.executable, "SnowMCP_initialize.py"], capture_output=True, text=True)
    if proc.returncode == 0:
        st.sidebar.success("Schema cache refreshed!")
        if proc.stdout:
            with st.sidebar.expander("Details"):
                st.code(proc.stdout)
    else:
        st.sidebar.error("Schema‑refresh failed.")
        with st.sidebar.expander("Error details"):
            st.error(proc.stderr)


# ───────────────────── session‑state helpers ─────────────────────
def store_event(html: str) -> None:
    if "assistant_buffer" not in st.session_state:
        st.session_state.assistant_buffer = []
    st.session_state.assistant_buffer.append(html)


# ───────────────────── status badge sidebar ─────────────────────
def draw_status() -> None:
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
    st.sidebar.markdown(
        f"""<div style="display:flex;align-items:center;margin-bottom:.5rem;">
        <div style="min-width:95px;font-weight:500;color:#475569;">LLM Server:</div>
        <div style="display:inline-flex;align-items:center;background-color:#f8fafc;
        border-radius:.5rem;padding:.25rem .75rem;border:1px solid #e2e8f0;">
        {llm_icon}<span style="font-weight:600;color:{llm_color};margin-left:.25rem;">{llm_lbl}</span>
        </div></div>""",
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        f"""<div style="display:flex;align-items:center;margin-bottom:.5rem;">
        <div style="min-width:95px;font-weight:500;color:#475569;">MCP Server:</div>
        <div style="display:inline-flex;align-items:center;background-color:#f8fafc;
        border-radius:.5rem;padding:.25rem .75rem;border:1px solid #e2e8f0;">
        {mcp_icon}<span style="font-weight:600;color:{mcp_color};margin-left:.25rem;">{mcp_lbl}</span>
        </div></div>""",
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        f"""<div style="display:flex;align-items:center;margin-bottom:.5rem;">
        <div style="min-width:95px;font-weight:500;color:#475569;">Gemini Model:</div>
        <div style="display:inline-flex;align-items:center;background-color:#f8fafc;
        border-radius:.5rem;padding:.25rem .75rem;border:1px solid #e2e8f0;">
        {model_icon}<span style="font-weight:600;color:{model_color};margin-left:.25rem;">
        {st.session_state.get('model_name','—')}</span>
        </div></div>""",
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        f"""<div style="color:#94a3b8;font-size:.75rem;margin-top:.5rem;">
        Updated at {datetime.datetime.now():%H:%M:%S}</div>""",
        unsafe_allow_html=True,
    )


# ───────────────────── bootstrap ─────────────────────
def bootstrap() -> None:
    if "session_id" in st.session_state:
        return

    st.session_state.update(
        mcp_host=MCP_SERVER_HOST,
        mcp_port=MCP_SERVER_PORT,
        user_name=DEFAULT_USER,
        model_name=DEFAULT_LLM_MODEL,
        model_status=False,
    )

    try:
        res = requests.post(
            f"{LLM_SERVER_URL}/create_session",
            json={"mcp_server": f"http://{MCP_SERVER_HOST}:{MCP_SERVER_PORT}/sse", "model_name": DEFAULT_LLM_MODEL},
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


# ───────────────────── sidebar config ─────────────────
st.sidebar.markdown(
    """<h2 style="color:#1e293b;font-weight:600;margin-bottom:1rem;">Configuration</h2>""",
    unsafe_allow_html=True,
)

with st.sidebar.expander("🤖 Gemini AI Model", True):
    models = fetch_available_models()
    idx = models.index(st.session_state.get("model_name", DEFAULT_LLM_MODEL)) if st.session_state.get(
        "model_name"
    ) in models else 0
    choice = st.selectbox("Select Gemini model", models, index=idx)
    if st.button("Apply Model", type="primary"):
        st.session_state.model_name = choice
        st.session_state.model_status = True
        st.sidebar.success("Gemini model updated!")

with st.sidebar.expander("MCP Server"):
    h = st.text_input("Host", st.session_state.get("mcp_host", MCP_SERVER_HOST))
    p = st.number_input("Port", value=st.session_state.get("mcp_port", MCP_SERVER_PORT), step=1)
    if st.button("Apply MCP", type="primary"):
        st.session_state.update(mcp_host=h, mcp_port=int(p))
        st.sidebar.success("MCP endpoint updated.")

with st.sidebar.expander("User"):
    name = st.text_input("Name", st.session_state.get("user_name", DEFAULT_USER))
    if st.button("Apply User", type="primary"):
        st.session_state.user_name = name
        st.sidebar.success("User name saved.")

if st.sidebar.button("🔄 Refresh Status", type="secondary"):
    draw_status()

if st.sidebar.button("🔄 Refresh Schema Cache", type="secondary"):
    refresh_schema_cache()

# ───────────────────── layout header ─────────────────
st.markdown(
    """
<h1 style="color:#0f172a;font-weight:700;border-bottom:2px solid #3366ff;
padding-bottom:.5rem;margin-bottom:1.5rem;">🚀 SnowGenie AI Assistant</h1>
<p style="color:#64748b;font-size:1.1rem;margin-bottom:1.5rem;">
Powered by Google Gemini AI for intelligent data insights
</p>
""",
    unsafe_allow_html=True,
)

bootstrap()
draw_status()

if "messages" not in st.session_state:
    st.session_state.messages = []

# ─────────── replay history ───────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg.get("is_html"):
            st.markdown(msg["content"], unsafe_allow_html=True)
        else:
            st.markdown(msg["content"])

# ───────────────────── streaming ─────────────────────
UPDATE_INTERVAL = 0.35  # seconds


def stream_agent(prompt: str, sid: str):
    resp = requests.post(
        f"{LLM_SERVER_URL}/query",
        json={"session_id": sid, "prompt": prompt, "stream": True},
        headers={"Accept": "text/event-stream"},
        stream=True, timeout=60,
    )

    buf, last = "", time.time()
    for raw in resp.iter_lines(decode_unicode=True):
        if not raw or not raw.startswith("data:"):
            continue
        data = json.loads(raw[5:].strip())

        if data.get("done"):
            if buf:
                yield "chunk", buf
            break

        kind, txt = data["kind"], data["content"]
        if kind == "chunk":
            buf += txt
            if time.time() - last >= UPDATE_INTERVAL:
                yield "chunk", buf
                buf, last = "", time.time()
        else:
            yield kind, txt

    if buf:
        yield "chunk", buf


# ───────────────────── renderer ─────────────────────
def render(kind: str, txt: str, box) -> str:
    """Render to Streamlit and return the HTML fragment."""
    if kind == "tool":
        html = (
            f'<div style="display:inline-flex;align-items:center;background-color:#f7f9fc;'
            f'border-radius:.5rem;padding:.5rem;margin-bottom:.5rem;border-left:4px solid #3366ff;">'
            f'<span style="font-weight:bold;margin-right:.5rem;color:#3366ff;">🛠️ TOOL CALL</span>'
            f'<code style="background-color:#1e293b;color:#e2e8f0;padding:.25rem .5rem;'
            f'border-radius:.25rem;font-family:monospace;">{txt}</code></div>'
        )
        box.markdown(html, unsafe_allow_html=True)
        return html

    if kind == "function":
        try:
            pretty = json.dumps(json.loads(txt), indent=2)
        except json.JSONDecodeError:
            pretty = txt
        html = (
            "<details style='margin-bottom:1rem;'>"
            "<summary style='background-color:#f7f9fc;padding:.5rem;border-radius:.5rem .5rem 0 0;"
            "font-weight:600;cursor:pointer;border:1px solid #e2e8f0;border-bottom:none;color:#1e293b;'>"
            "Tool Response</summary>"
            "<div style='background-color:#f8fafc;padding:1rem;border:1px solid #e2e8f0;"
            "border-radius:0 0 .5rem .5rem;'><pre style='background-color:#f1f5f9;padding:.75rem;"
            f"border-radius:.25rem;overflow:auto;'><code>{pretty}</code></pre></div></details>"
        )
        box.markdown(html, unsafe_allow_html=True)
        return html

    if kind == "think":
        think = "\n".join(re.findall(r"<think>(.*?)</think>", txt, re.DOTALL))
        ans = re.sub(r"<think>.*?</think>", "", txt, flags=re.DOTALL).strip()
        html = (
            "<div style='background-color:#f8fafc;border-radius:.5rem;padding:1rem;"
            "border-left:4px solid #667eea;margin-top:.5rem;color:#334155;'>"
            "<div style='font-weight:600;margin-bottom:.5rem;color:#4f46e5;'>🧠 Reasoning Process</div>"
            f"{think}</div>"
            "<div style='background-color:#f8fafc;border-radius:.5rem;padding:1rem;"
            "border-left:4px solid #8B4513;margin-top:.5rem;color:#334155;'>"
            "<div style='font-weight:600;margin-bottom:.5rem;color:#8B4513;'>Final Answer</div>"
            f"{ans}</div>"
        )
        box.markdown(html, unsafe_allow_html=True)
        return html

    # chunk/answer
    html = (
        "<div style='background-color:#f0f7ff;border-radius:.5rem;padding:1rem;"
        "border-left:4px solid #0050e6;margin-top:.5rem;color:#1e293b;'>"
        f"{txt}</div>"
    )
    box.markdown(html, unsafe_allow_html=True)
    return html


# ───────────────────── chat input ─────────────────────
if st.session_state.get("model_status"):
    prompt = st.chat_input("Ask me anything about your Snowflake data with Gemini AI…")
else:
    prompt = None
    st.warning("Gemini AI unavailable – check API key & model.")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    start_stream_worker(prompt)
    st.rerun() # 1‑line universal rerun

if "stream_q" in st.session_state:       # we’re in streaming mode
    with st.chat_message("assistant"):
        outer = st.container()
        
        # ── load any HTML we already showed last refresh ──
        prev_html = ""
        if (
            st.session_state.messages
            and st.session_state.messages[-1]["role"] == "assistant"
        ):
            prev_html = st.session_state.messages[-1]["content"]

        live = ""                                   # will rebuild the answer text
        htmls = prev_html.split("\n") if prev_html else []  # ← reuse earlier html
        thinking_shown = any("🧠 Reasoning Process" in h for h in htmls)

        while not st.session_state.stream_q.empty():
            kind, txt = st.session_state.stream_q.get_nowait()

            if kind == "__END__":         # worker finished
                st.session_state.stream_done = True
                break

            if kind == "chunk":
                live += txt
                rendered = render("chunk", live, outer.container())

                # if the last html we stored is *also* a chunk, overwrite it;
                # otherwise (first chunk this cycle) append a new one
                if htmls and "border-left:4px solid #0050e6" in htmls[-1]:
                    htmls[-1] = rendered
                else:
                    htmls.append(rendered)
            elif kind == "think" and not thinking_shown:
                thinking_shown = True
                htmls.append(render(kind, txt, outer))
            elif kind in ("tool", "function"):
                htmls.append(render(kind, txt, outer))

        # overwrite or append assistant turn in history
        if htmls:
            if st.session_state.messages and st.session_state.messages[-1]["role"] == "assistant":
                st.session_state.messages[-1]["content"] = "\n".join(htmls)
            else:
                st.session_state.messages.append(
                    {"role": "assistant", "content": "\n".join(htmls), "is_html": True}
                )

    # keep page alive every 300 ms until done
    if not st.session_state.stream_done:
        st_autorefresh(interval=300, key="stream_refresh")
    else:
        # cleanup
        st.session_state.pop("stream_q")
        st.session_state.pop("stream_done")













# if prompt:
#     # ── user turn ──
#     st.session_state.messages.append({"role": "user", "content": prompt})
#     with st.chat_message("user"):
#         st.markdown(prompt)

#     # ── assistant turn buffer ──
#     st.session_state.assistant_buffer = []

#     with st.chat_message("assistant"):
#         outer = st.container()
#         live, final_html, thinking_shown = "", "", False

#         for k, txt in stream_agent(prompt):
#             if k == "chunk":
#                 live += txt
#                 final_html = render("chunk", live, outer.container())
#             elif k == "think" and not thinking_shown:
#                 thinking_shown = True
#                 store_event(render(k, txt, outer))
#             elif k in ("tool", "function"):
#                 store_event(render(k, txt, outer))

#         if final_html:
#             store_event(final_html)  # last version of the answer

#     # ── commit assistant turn to history ──
#     st.session_state.messages.append(
#         {"role": "assistant", "content": "\n".join(st.session_state.assistant_buffer), "is_html": True}
#     )
#     del st.session_state.assistant_buffer
