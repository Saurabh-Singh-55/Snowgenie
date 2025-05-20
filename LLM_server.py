"""
llm_server.py – FastAPI wrapper around MCP‑Agent + Ollama LLM
─────────────────────────────────────────────────────────────
Copy‑paste this file as‑is, then run:

    uvicorn llm_server:app --reload

Endpoints
  GET  /health
  GET  /models
  POST /create_session      { mcp_server, model_name? }
  POST /query               { session_id, prompt, stream?, mcp_server?, model_name? }

If "stream": true, responses are Server‑Sent Events (SSE) where each `data:`
chunk already carries pretty‑formatted text (tool calls, function messages,
chain‑of‑thought, final answer).
"""

from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import Dict, Optional
import requests, asyncio, uvicorn, uuid, json, re

from mcp_use import MCPAgent, MCPClient
from langchain_ollama import ChatOllama
from langchain_core.runnables.schema import StreamEvent

from constants import (
    OLLAMA_API,
    DEFAULT_LLM_MODEL,
    LLM_SERVER_HOST,
    LLM_SERVER_PORT,
    AGENT_MAX_STEPS,
    AGENT_MEMORY_ENABLED,
)

# ───────────────────────── FastAPI app + session state ─────────────────────────
app = FastAPI(title="LLM Server")

agents: Dict[str, MCPAgent] = {}
mcp_servers: Dict[str, str] = {}
model_names: Dict[str, str] = {}

# ──────────────────────────────── Pydantic models ──────────────────────────────
class QueryRequest(BaseModel):
    session_id: str
    prompt: str
    mcp_server: Optional[str] = None
    model_name: Optional[str] = None
    stream: bool = False

class SessionRequest(BaseModel):
    mcp_server: str
    model_name: str = DEFAULT_LLM_MODEL

class SessionResponse(BaseModel):
    session_id: str
    message: str
    model_status: bool = True

# ───────────────────────────── health / models endpoints ───────────────────────
@app.get("/health", status_code=200)
async def health_check():
    return {"status": "ok"}

@app.get("/models", status_code=200)
async def list_models():
    try:
        r = requests.get(f"{OLLAMA_API}/api/tags", timeout=5)
        r.raise_for_status()
        return {"models": [m["name"] for m in r.json().get("models", [])]}
    except Exception as e:
        return {"error": str(e), "models": []}

# ─────────────────────────── helper: formatter function ────────────────────────
def format_agent_event(event) -> Optional[dict]:
    """
    Return {"kind": <label>, "content": <text>}  or None.
    """
    # TOOL CALL
    if "actions" in event:
        for act in event["actions"]:
            return {"kind": "tool", "content": getattr(act, "tool", "<unknown>")}

    # FUNCTION MESSAGE (tool response)
    if "steps" in event:
        texts = []
        for step in event["steps"]:
            obs = getattr(step, "observation", "")
            if obs:
                texts.append(obs.strip())
        if texts:
            return {"kind": "function", "content": "\n\n".join(texts)}

    # STREAMED LLM CHUNK
    if hasattr(event, "event") and hasattr(event, "data"):
        if event.event == "on_chat_model_stream":
            return {"kind": "chunk", "content": event.data.content}

    # FINAL LLM OUTPUT
    if "output" in event:
        full = event["output"]
        return {"kind": "think", "content": full }
        think = re.findall(r"<think>(.*?)</think>", full, re.DOTALL)
        answer = re.sub(r"<think>.*?</think>", "", full, flags=re.DOTALL).strip()
        return {"kind": "think", "content": "\n-----\n".join(t.strip() for t in think)+ "\n\n" + answer }

    return None

# ------- SSE generator now streams JSON with kind + content ---------------
async def sse_stream(session_id: str, prompt: str):
    agent = agents[session_id]
    async for event in agent.astream(prompt):
        payload = format_agent_event(event)
        if payload:
            yield f"data: {json.dumps(payload)}\n\n"
    yield "data: {\"done\": true}\n\n"

# ───────────────────────────── query main endpoint ─────────────────────────────
@app.post("/query", status_code=200)
async def query_agent(request: QueryRequest):
    sid = request.session_id

    # Handle MCP / model updates
    if request.mcp_server:
        mcp_servers[sid] = request.mcp_server
    elif sid not in mcp_servers:
        raise HTTPException(400, "MCP server address required for new session")

    if request.model_name:
        if model_names.get(sid) != request.model_name:
            model_names[sid] = request.model_name
            agents.pop(sid, None)
    elif sid not in model_names:
        model_names[sid] = DEFAULT_LLM_MODEL

    # Create agent if absent
    if sid not in agents:
        try:
            agents[sid] = create_agent(mcp_servers[sid], model_names[sid])
        except Exception as e:
            raise HTTPException(500, f"Failed to load model {model_names[sid]}: {e}")

    agent = agents[sid]

    # STREAMING MODE
    if request.stream:
        return StreamingResponse(
            sse_stream(sid, request.prompt),
            media_type="text/event-stream",
        )

    # NON‑STREAMING MODE – collect formatted chunks then return once
    chunks = []
    async for event in agent.astream(request.prompt):
        text = format_agent_event(event)
        if text:
            chunks.append(text)
    return {"session_id": sid, "response": "".join(chunks)}

# ─────────────────────────────── session endpoint ─────────────────────────────
@app.post("/create_session", status_code=201, response_model=SessionResponse)
async def create_session(req: SessionRequest):
    sid = str(uuid.uuid4())
    mcp_servers[sid] = req.mcp_server
    model_names[sid] = req.model_name
    model_ok = check_model_exists(req.model_name)
    return SessionResponse(
        session_id=sid,
        message="Session created successfully",
        model_status=model_ok,
    )

# ─────────────────────────────── helper utilities ─────────────────────────────
def check_model_exists(model_name: str) -> bool:
    try:
        r = requests.get(f"{OLLAMA_API}/api/tags", timeout=5)
        r.raise_for_status()
        names = [m["name"] for m in r.json().get("models", [])]
        return model_name in names
    except Exception:
        return False

def create_agent(mcp_url: str, model_name: str = DEFAULT_LLM_MODEL) -> MCPAgent:
    load_dotenv()
    if not check_model_exists(model_name):
        raise ValueError(f"Model {model_name} not found in Ollama")

    client_cfg = {"mcpServers": {"http": {"url": mcp_url}}}
    client = MCPClient.from_dict(client_cfg)
    llm = ChatOllama(model=model_name)

    return MCPAgent(
        llm=llm,
        client=client,
        max_steps=AGENT_MAX_STEPS,
        memory_enabled=AGENT_MEMORY_ENABLED,
        verbose=True,
    )

# ───────────────────────────────────── main ────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(app, host=LLM_SERVER_HOST, port=LLM_SERVER_PORT)
