import logging
import json #-NEW-
import os   #-NEW-
from contextlib import closing
from typing import List, Dict, Any
from write_detector import SQLWriteDetector
import snowflake.connector
from fastmcp import FastMCP

# ------------------------------------------------------------------#
# Constants (use env‑vars or a secrets manager in production)         #
# ------------------------------------------------------------------#
from constants import (
    SNOWFLAKE_USER,
    SNOWFLAKE_PASSWORD,
    SNOWFLAKE_ACCOUNT,
    SNOWFLAKE_ROLE,
    SNOWFLAKE_WAREHOUSE,
    SNOWFLAKE_DATABASE,
    SNOWFLAKE_SCHEMA,
    MCP_SERVER_HOST,
    MCP_SERVER_PORT,
    MCP_SERVER_NAME,
    MCP_LOG_LEVEL,
)

logger = logging.getLogger("mcp_snowflake_server")
logger.info("Starting MCP Snowflake Server")

# --- NEW: Load the schema from the cache file on startup ---
SCHEMA_CACHE = {}
CACHE_FILE_PATH = "db_schema_cache.json"
try:
    with open(CACHE_FILE_PATH, "r") as f:
        SCHEMA_CACHE = json.load(f)
    logger.info(f"Successfully loaded schema cache from '{CACHE_FILE_PATH}'")
except FileNotFoundError:
    logger.error(f"FATAL: Cache file not found at '{CACHE_FILE_PATH}'.")
    logger.error("The 'list_tables' and 'describe_table' tools will fail.")
    logger.error("Please run the initialization script to build the cache.")
except json.JSONDecodeError:
    logger.error(f"FATAL: Could not decode JSON from cache file '{CACHE_FILE_PATH}'. It may be corrupt.")
    SCHEMA_CACHE = {}
# --- END NEW ---


# ------------------------------------------------------------------#
# FastMCP instance – name shows up in clients                       #
# ------------------------------------------------------------------#
mcp = FastMCP(MCP_SERVER_NAME)

# ----------  DATABASE WRAPPER (Kept for 'read_query') -------------#
class SnowflakeDatabase:
    """Thin wrapper around Snowflake with helper queries. Used for live data queries."""

    def __init__(self):
        self._test_connection()

    def _get_connection(self):
        return snowflake.connector.connect(
            user=SNOWFLAKE_USER,
            password=SNOWFLAKE_PASSWORD,
            account=SNOWFLAKE_ACCOUNT,
            role=SNOWFLAKE_ROLE,
            warehouse=SNOWFLAKE_WAREHOUSE,
        )

    def _test_connection(self):
        with closing(self._get_connection()) as conn, closing(conn.cursor()) as cur:
            cur.execute("SELECT CURRENT_VERSION()")
            version = cur.fetchone()[0]
            logger.info(f"Connected to Snowflake {version} for live queries.")

    async def execute_query(self, query: str) -> List[Dict[str, Any]]:
        with closing(self._get_connection()) as conn, closing(
            conn.cursor(snowflake.connector.DictCursor)
        ) as cur:
            cur.execute(query)
            return cur.fetchall() if cur.description else []

# ------------------------------------------------------------------#
# This object is now only used by the 'read_query' tool.
db = SnowflakeDatabase()

# ------------------  MCP TOOLS (Modified to use cache) ----------------#
@mcp.tool()
async def list_databases() -> List[str]:
    """Return current accesable database containing the relevant information.
    """
    return [SNOWFLAKE_DATABASE]

@mcp.tool()
async def list_schemas() -> List[str]:
    """Name of the schema of the current database containing the relevant information.
    """
    return [SNOWFLAKE_SCHEMA]

@mcp.tool()
async def list_tables() -> List[Dict[str, Any]]:
    """List tables in the current database.schema containing the relevant information.
    """
    if not SCHEMA_CACHE:
        return [{"error": "Schema cache is not loaded. Please run the initialization script."}]
    try:
        db_name = SNOWFLAKE_DATABASE.upper()
        schema_name = SNOWFLAKE_SCHEMA.upper()
        tables_dict = SCHEMA_CACHE["databases"][db_name]["schemas"][schema_name]["tables"]
        
        return [
            {
                "database": db_name,
                "schema": schema_name,
                "name": table_name,
                "comment": table_info.get("comment", "")
            }
            for table_name, table_info in tables_dict.items()
        ]
    except KeyError:
        return [{"error": f"Database '{SNOWFLAKE_DATABASE}' or Schema '{SNOWFLAKE_SCHEMA}' not found in cache."}]


@mcp.tool()
async def describe_table(table_name: str) -> List[Dict[str, Any]]:
    """Describe columns for a table in the current database and schema.
    Carefully understand the comment for each column to interpret business logic.
    Also includes a sample row of data to provide context on the actual data stored.
    
    Args:
        table_name: The name of the table to describe (without database and schema).
    """
    if not SCHEMA_CACHE:
        return [{"error": "Schema cache is not loaded. Please run the initialization script."}]
        
    try:
        db_name = SNOWFLAKE_DATABASE.upper()
        schema_name = SNOWFLAKE_SCHEMA.upper()
        table_upper = table_name.upper()
        
        table_info = SCHEMA_CACHE["databases"][db_name]["schemas"][schema_name]["tables"][table_upper]
        
        columns = table_info.get("columns", [])
        sample_row = table_info.get("sample_row")
        
        result = list(columns)
        if sample_row:
            result.append({
                "SAMPLE_DATA": sample_row
            })
        return result
    except KeyError:
        return [{"error": f"Table '{table_name}' not found in the SNOWFLAKE DB cached for {SNOWFLAKE_DATABASE}.{SNOWFLAKE_SCHEMA}."}]


@mcp.tool()
async def read_query(query: str) -> List[Dict[str, Any]]:
    """Query the database with only read operations and should not contain write operations
    like INSERT, UPDATE, DELETE, MERGE, UPSERT, REPLACE, CREATE, ALTER, DROP, TRUNCATE, RENAME, GRANT, REVOKE.
    Must ensure that table names in a SQL query are fully qualified (like database.schema.table).
    Example: `FROM sales.return` becomes `FROM retail_poc.sales.return`.
    Must run only one SQL statement per call.
    supports only Snowflake‑compatible SQL (ANSI‑99 core + SQL:2003 analytics). 
    Avoid features Snowflake ignores or blocks—indexes, triggers, enforced PK/FK, stored routines/cursors,
    recursive CTEs, UPDATE…FROM, MySQL/T‑SQL syntax, or vendor‑specific functions.
    Args:
        query: A single read SQL query to execute with the database and schema always written before the table name.
    """
    if SQLWriteDetector().analyze_query(query)["contains_write"]:
            raise ValueError("Calls to read_query should not contain write operations")
    return await db.execute_query(query)

# ------------------  MAIN  ----------------------------------------#
if __name__ == "__main__":
    mcp.run(transport="sse", host=MCP_SERVER_HOST, port=MCP_SERVER_PORT, log_level=MCP_LOG_LEVEL)