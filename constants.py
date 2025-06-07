import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# LLM Server Constants
DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "gemini-2.0-flash")
LLM_SERVER_HOST = os.getenv("LLM_SERVER_HOST", "0.0.0.0")
LLM_SERVER_PORT = int(os.getenv("LLM_SERVER_PORT", "8080"))
AGENT_MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "15"))
AGENT_MEMORY_ENABLED = os.getenv("AGENT_MEMORY_ENABLED", "False").lower() == "False"


# UI Application Constants
LLM_SERVER_URL = os.getenv("LLM_SERVER_URL", f"http://localhost:{LLM_SERVER_PORT}")
DEFAULT_USER = os.getenv("DEFAULT_USER", "default_user")
FALLBACK_MODELS = os.getenv("FALLBACK_MODELS", "gemini-2.0-flash,gemini-1.5-pro,gemini-1.5-flash").split(",") 


# Snowflake Constants
SNOWFLAKE_USER = os.getenv("SNOWFLAKE_USER", "SAURABH55")
SNOWFLAKE_PASSWORD = os.getenv("SNOWFLAKE_PASSWORD", "Lol@6172021415")
SNOWFLAKE_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT", "RQB37169")
SNOWFLAKE_ROLE = os.getenv("SNOWFLAKE_ROLE", "ACCOUNTADMIN")
SNOWFLAKE_DATABASE = os.getenv("SNOWFLAKE_DATABASE", "RETAIL_POC")
SNOWFLAKE_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA", "SALES")
SNOWFLAKE_WAREHOUSE = os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH")
MCP_SERVER_HOST = os.getenv("MCP_SERVER_HOST", "127.0.0.1")
MCP_SERVER_PORT = int(os.getenv("MCP_SERVER_PORT", "8000"))
MCP_SERVER_NAME = os.getenv("MCP_SERVER_NAME", "Snowflake-Manager")
MCP_LOG_LEVEL = os.getenv("MCP_LOG_LEVEL", "info")


#gemini constants
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "...")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-preview-05-20")
GEMINI_TEMPERATURE = os.getenv("GEMINI_TEMPERATURE", "0")
GEMINI_MAX_TOKENS = os.getenv("GEMINI_MAX_TOKENS", "2000")
