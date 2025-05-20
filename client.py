import asyncio
import mcp_use
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.runnables.schema import StreamEvent

from mcp_use import MCPAgent, MCPClient
import os
from constants import MCP_SERVER_HOST, MCP_SERVER_PORT
import re
import traceback
mcp_use.set_debug(1)


def safe_print(label, value):
    print(f"\n[DBG] {label}: {value}")

async def run_memory_chat():
    """Run a chat using MCPAgent's built-in conversation memory."""
    # Load environment variables for API keys
    load_dotenv()

    # Config file path - change this to your config file
    MCP_URL = f"http://{MCP_SERVER_HOST}:{MCP_SERVER_PORT}/sse"
    config = {"mcpServers": {"http": {"url": MCP_URL}}}
    client = MCPClient.from_dict(config)
    llm = ChatOllama(model="qwen3:32b")

    # Create agent with memory_enabled=True
    agent = MCPAgent(
        llm=llm,
        client=client,
        max_steps=15,
        memory_enabled=True,  # Enable built-in conversation memory
    )

    print("\n===== Interactive SQL Database Chat =====")
    print("Type 'exit' or 'quit' to end the conversation")
    print("Type 'clear' to clear conversation history")
    print("==========================================\n")

    try:
        # Main chat loop
        while True:
            # Get user input
            user_input = input("\nYou: ")

            # Check for exit command
            if user_input.lower() in ["exit", "quit"]:
                print("Ending conversation...")
                break

            # Check for clear history command
            if user_input.lower() == "clear":
                agent.clear_conversation_history()
                print("Conversation history cleared.")
                continue

            # Get response from agent
            print("\nAssistant: ", end="", flush=True)

            try:
                async for event in agent.astream(user_input):

                    # ───────── TOOL CALL ──────────────────────────────────────────────
                    if "actions" in event:      # AddableDict with tool invocation
                        for act in event["actions"]:
                            print(f"\n🔧 TOOL CALLED: {getattr(act, 'tool', '<unknown>')}")

                    # ───────── FUNCTION (tool response) ───────────────────────────────
                    if "steps" in event:        # AddableDict with AgentStep
                        for step in event["steps"]:
                            obs = getattr(step, "observation", "")
                            if obs:
                                print(f"\n📩 FUNCTION MESSAGE:\n{obs.strip()}")

                    # ───────── STREAMED LLM CHUNKS ────────────────────────────────────
                    if hasattr(event, "event") and hasattr(event, "data"):   # ← safe test
                        if event.event == "on_chat_model_stream":
                            print(event.data.content, end="", flush=True)

                    # ───────── FINAL LLM OUTPUT ───────────────────────────────────────
                    if "output" in event:       # AddableDict with assistant’s last msg
                        full = event["output"]

                        think_blocks = re.findall(r"<think>(.*?)</think>", full, re.DOTALL)
                        if think_blocks:
                            joined = "\n-----\n".join(tb.strip() for tb in think_blocks)
                            print(f"\n\n🧠 THOUGHT PROCESS:\n{joined}")

                        answer = re.sub(r"<think>.*?</think>", "", full, flags=re.DOTALL).strip()
                        if answer:
                            print(f"\n\n✅ FINAL ANSWER:\n{answer}\n")

            except Exception as e:
                print(f"\nError: {e}")

    finally:
        # Clean up
        if client and client.sessions:
            await client.close_all_sessions()


if __name__ == "__main__":
    asyncio.run(run_memory_chat())