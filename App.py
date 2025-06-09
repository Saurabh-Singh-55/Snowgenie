# app.py – SnowGenie Streamlit thin client (rich history, throttled streaming)

import streamlit as st
import requests, socket, json, datetime, time, re
from typing import List
import threading, queue
from streamlit_autorefresh import st_autorefresh
import sqlparse
from constants import (
    LLM_SERVER_URL,
    DEFAULT_LLM_MODEL,
    MCP_SERVER_HOST,
    MCP_SERVER_PORT,
    DEFAULT_USER,
    FALLBACK_MODELS,
)


APPROVAL_API = "http://localhost:8001"       #  ← FastAPI base URL

@st.fragment
def review_sql():
    """
    Sidebar fragment:
    • 🔄 Fetch SQL → shows the first pending query *below the chat stream*
    • ✅ Approve / ❌ Reject → updates FastAPI and appends an "Authorization"
      block that looks like the existing “Tool Response” section.
    """
    # ── helpers ──────────────────────────────────────────────────────────
    def _pretty_sql(q: str) -> str:
        """
        Return nicely formatted SQL.
        Falls back to simple line‑break heuristics if sqlparse isn’t available.
        """
        if sqlparse:
            return sqlparse.format(q, keyword_case="upper", reindent=True, wrap_after=60)

        # very lightweight fallback – insert breaks before main clauses/joins
        pattern = re.compile(
            r"\b(SELECT|FROM|WHERE|GROUP BY|ORDER BY|HAVING|LIMIT|JOIN|"
            r"LEFT JOIN|RIGHT JOIN|INNER JOIN|OUTER JOIN|UNION|EXCEPT|INTERSECT)\b",
            flags=re.I,
        )
        return pattern.sub(r"\n\1", q).strip()


    def _push_auth_html(query: str, label: str, color: str) -> None:
        """Add an <Authorization …> collapsible block to chat history."""
        formatted = _pretty_sql(query)
        html = (
            "<details style='margin-bottom:1rem;'>"
            f"<summary style='background-color:#f7f9fc;padding:.5rem;border-radius:.5rem .5rem 0 0;"
            "font-weight:600;cursor:pointer;border:1px solid #e2e8f0;border-bottom:none;"
            f"color:{color};'>Authorization – {label}</summary>"
            "<div style='background-color:#f8fafc;padding:1rem;border:1px solid #e2e8f0;"
            "border-radius:0 0 .5rem .5rem;'>"
            "<pre style='background-color:#f1f5f9;padding:.75rem;border-radius:.25rem;overflow:auto;'>"
            f"<code>{formatted}</code></pre></div></details>"
        )
        st.session_state.setdefault("messages", [])
        st.session_state.messages.append({"role": "assistant", "content": html, "is_html": True})

    # keep the currently selected queue item in session state
    st.session_state.setdefault("queue_item", None)

    col1, col2, col3 = st.columns(3)

    # ── Fetch ────────────────────────────────────────────────────────────
    with col1:
        if st.button("🔄 Fetch SQL", key="fetch_sql_btn"):
            try:
                resp = requests.get(f"{APPROVAL_API}/pending", timeout=5)
                resp.raise_for_status()
                pending = [q for q in resp.json() if q["status"] == "pending"]
                st.session_state.queue_item = pending[0] if pending else None

                if st.session_state.queue_item:
                    _push_auth_html(
                        st.session_state.queue_item["query"],
                        "Pending",
                        "#475569",            # slate‑gray
                    )
                    st.rerun()
                else:
                    st.warning("No pending SQL to review.")
            except Exception as e:
                st.error(f"Fetch error: {e}")

    # ── Approve ──────────────────────────────────────────────────────────
    with col2:
        if st.button("✅ Approve", key="approve_btn",
                     disabled=st.session_state.queue_item is None):
            try:
                sid = st.session_state.queue_item["session_id"]
                requests.post(f"{APPROVAL_API}/approve/{sid}",
                              json={"approved": True}, timeout=5)
                _push_auth_html(
                    st.session_state.queue_item["query"],
                    "Approved",
                    "#0a7b3e",             # green
                )
            except Exception as e:
                st.error(f"Approve error: {e}")
            finally:
                st.session_state.queue_item = None
                st.rerun()

    # ── Reject ───────────────────────────────────────────────────────────
    with col3:
        if st.button("❌ Reject", key="reject_btn",
                     disabled=st.session_state.queue_item is None):
            try:
                sid = st.session_state.queue_item["session_id"]
                requests.post(f"{APPROVAL_API}/approve/{sid}",
                              json={"approved": False}, timeout=5)
                _push_auth_html(
                    st.session_state.queue_item["query"],
                    "Rejected",
                    "#d32f2f",             # red
                )
            except Exception as e:
                st.error(f"Reject error: {e}")
            finally:
                st.session_state.queue_item = None
                st.rerun()


# Attach fragment to the sidebar
with st.sidebar:
    review_sql()


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
    
    # Display model description
    model_info = {
        'gemini-2.5-flash-preview-05-20': 'Adaptive thinking, cost efficiency',
        'gemini-2.5-flash-preview-native-audio-dialog': 'High quality audio outputs',
        'gemini-2.5-flash-exp-native-audio-thinking-dialog': 'Natural conversational audio',
        'gemini-2.5-flash-preview-tts': 'Text-to-speech generation',
        'gemini-2.5-pro-preview-06-05': 'Enhanced reasoning & multimodal',
        'gemini-2.5-pro-preview-tts': 'Advanced text-to-speech',
        'gemini-2.0-flash': 'Next-gen features & streaming',
        'gemini-2.0-flash-preview-image-generation': 'Image generation & editing',
        'gemini-2.0-flash-lite': 'Cost efficient & low latency',
        'gemini-1.5-flash': 'Fast & versatile performance',
        'gemini-1.5-flash-8b': 'High volume tasks',
        'gemini-1.5-pro': 'Complex reasoning tasks',
        'gemini-embedding-exp': 'Text embeddings',
        'imagen-3.0-generate-002': 'Advanced image generation',
        'veo-2.0-generate-001': 'Video generation',
        'gemini-2.0-flash-live-001': 'Bidirectional voice & video'
    }
    
    if choice in model_info:
        st.info(f"Model Description: {model_info[choice]}")
    
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
padding-bottom:.5rem;margin-bottom:1.5rem;"> ❄️ SnowGenie AI Assistant</h1>
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
