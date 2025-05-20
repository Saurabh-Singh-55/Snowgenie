import logging
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

# ------------------------------------------------------------------#
# FastMCP instance – name shows up in clients                       #
# ------------------------------------------------------------------#
mcp = FastMCP(MCP_SERVER_NAME)

# ----------  DATABASE WRAPPER  ------------------------------------#
class SnowflakeDatabase:
    """Thin wrapper around Snowflake with helper queries."""

    def __init__(self):
        self._test_connection()

    # ---------------- Private helpers -----------------------------#
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
            logger.info(f"Connected to Snowflake {version}")

    # ---------------- Public helper queries -----------------------#
    async def execute_query(self, query: str) -> List[Dict[str, Any]]:
        with closing(self._get_connection()) as conn, closing(
            conn.cursor(snowflake.connector.DictCursor)
        ) as cur:
            cur.execute(query)
            return cur.fetchall() if cur.description else []

    async def list_databases(self) -> List[str]:
        rows = await self.execute_query("SHOW DATABASES")
        return [r["name"] for r in rows]

    async def list_schemas(self, database: str) -> List[str]:
        rows = await self.execute_query(f"SHOW SCHEMAS IN {database}")
        return [r["name"] for r in rows]

    async def list_tables(self, database: str, schema: str) -> List[Dict[str, Any]]:
        query = (
            "SELECT table_name, comment FROM "
            f"{database}.information_schema.tables WHERE table_schema='{schema}'"
        )
        rows = await self.execute_query(query)
        return [
            {"database": database, "schema": schema, "name": r["TABLE_NAME"], "comment": r["COMMENT"]}
            for r in rows
        ]

    async def describe_table(self, database: str, schema: str, table: str) -> List[Dict[str, Any]]:
        query = (
            "SELECT column_name, data_type, is_nullable, comment "
            f"FROM {database}.information_schema.columns "
            f"WHERE table_schema='{schema}' AND table_name='{table}' ORDER BY ordinal_position"
        )
        return await self.execute_query(query)

# ------------------------------------------------------------------#
db = SnowflakeDatabase()

# ------------------  MCP TOOLS  -----------------------------------#
@mcp.tool()
async def list_databases() -> List[str]:
    """Return current accesable database the current role can see.
    """
    # return await db.list_databases()
    return SNOWFLAKE_DATABASE

@mcp.tool()
async def list_schemas() -> List[str]:
    """Name of the schema of the current database the current role can see.
    """
    return SNOWFLAKE_SCHEMA;

@mcp.tool()
async def list_tables() -> List[Dict[str, Any]]:
    """List tables in the current database.schema and the current role can see.
    
    """
    return await db.list_tables(SNOWFLAKE_DATABASE.upper(), SNOWFLAKE_SCHEMA.upper())

@mcp.tool()
async def describe_table(table_name: str) -> List[Dict[str, Any]]:
    """Describe columns for a table in the current database and schema.
    Carefully understand the comment for each column to interpret business logic.
    Also includes a sample row of data to provide context on the actual data stored.
    
    Args:
        table_name: The name of the table to describe (without database and schema).
    """
    database = SNOWFLAKE_DATABASE.upper()
    schema = SNOWFLAKE_SCHEMA.upper()
    table = table_name.upper()
    
    columns = await db.describe_table(database, schema, table)
    
    # Get a sample row to provide context
    sample_query = f"SELECT * FROM {database}.{schema}.{table} LIMIT 1"
    sample_data = await db.execute_query(sample_query)
    
    # Add the sample data to the result
    if sample_data:
        columns.append({
            "sample_data": sample_data[0]
        })
    
    return columns

@mcp.tool()
async def read_query(query: str) -> List[Dict[str, Any]]:
    """Query database with only read operations and should not contain write operations
    like INSERT, UPDATE, DELETE, MERGE, UPSERT, REPLACE, CREATE, ALTER, DROP, TRUNCATE, RENAME, GRANT, REVOKE.
    
    Query should only run on available databases and schemas.
    it can run exactly one SQL statement per call.
    Args:
        query: A single read SQL query to execute with the database and schema always written before the table name.
    """
    if SQLWriteDetector().analyze_query(query)["contains_write"]:
            raise ValueError("Calls to read_query should not contain write operations")
    return await db.execute_query(query)

# ------------------  MAIN  ----------------------------------------#
if __name__ == "__main__":
    mcp.run(transport="sse", host=MCP_SERVER_HOST, port=MCP_SERVER_PORT, log_level=MCP_LOG_LEVEL)
