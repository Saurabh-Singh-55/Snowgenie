import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# LLM Server Constants
OLLAMA_API = os.getenv("OLLAMA_API", "http://localhost:11434")
DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "qwen3:32b")
LLM_SERVER_HOST = os.getenv("LLM_SERVER_HOST", "0.0.0.0")
LLM_SERVER_PORT = int(os.getenv("LLM_SERVER_PORT", "8080"))
AGENT_MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "15"))
AGENT_MEMORY_ENABLED = os.getenv("AGENT_MEMORY_ENABLED", "True").lower() == "true"


# UI Application Constants
LLM_SERVER_URL = os.getenv("LLM_SERVER_URL", f"http://localhost:{LLM_SERVER_PORT}")
DEFAULT_USER = os.getenv("DEFAULT_USER", "default_user")
FALLBACK_MODELS = os.getenv("FALLBACK_MODELS", "qwen3:32b").split(",") 


# Snowflake Constants
SNOWFLAKE_USER = os.getenv("SNOWFLAKE_USER", "...")
SNOWFLAKE_PASSWORD = os.getenv("SNOWFLAKE_PASSWORD", "...")
SNOWFLAKE_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT", "...")
SNOWFLAKE_ROLE = os.getenv("SNOWFLAKE_ROLE", "ACCOUNTADMIN")
SNOWFLAKE_DATABASE = os.getenv("SNOWFLAKE_DATABASE", "RETAIL_POC")
SNOWFLAKE_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA", "SALES")
SNOWFLAKE_WAREHOUSE = os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH")
MCP_SERVER_HOST = os.getenv("MCP_SERVER_HOST", "127.0.0.1")
MCP_SERVER_PORT = int(os.getenv("MCP_SERVER_PORT", "8000"))
MCP_SERVER_NAME = os.getenv("MCP_SERVER_NAME", "Snowflake-Manager")
MCP_LOG_LEVEL = os.getenv("MCP_LOG_LEVEL", "info")
