import json
import logging
import asyncio
from contextlib import closing
from decimal import Decimal
from json import JSONEncoder
from datetime import date, datetime

# Assuming your constants are in a constants.py file and the base SnowflakeDatabase
# class is in mcp_server.py. We will override the class here for efficiency.
from constants import (
    SNOWFLAKE_USER,
    SNOWFLAKE_PASSWORD,
    SNOWFLAKE_ACCOUNT,
    SNOWFLAKE_ROLE,
    SNOWFLAKE_WAREHOUSE,
    SNOWFLAKE_DATABASE,
    SNOWFLAKE_SCHEMA,
)
import snowflake.connector

# --- Configuration ---
CACHE_OUTPUT_FILE = "db_schema_cache.json"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("schema_builder")

# --- OPTIMIZATION: Refactored class to reuse a single connection ---
class EfficientSnowflakeDatabase:
    """
    Wrapper around Snowflake that uses a single, persistent connection
    for the duration of its life. Ideal for batch scripts.
    """
    def __init__(self):
        self._conn = self._get_connection()
        self._test_connection()

    def _get_connection(self):
        logger.info("Establishing a new persistent Snowflake connection...")
        return snowflake.connector.connect(
            user=SNOWFLAKE_USER,
            password=SNOWFLAKE_PASSWORD,
            account=SNOWFLAKE_ACCOUNT,
            role=SNOWFLAKE_ROLE,
            warehouse=SNOWFLAKE_WAREHOUSE,
        )

    def _test_connection(self):
        with closing(self._conn.cursor()) as cur:
            cur.execute("SELECT CURRENT_VERSION()")
            version = cur.fetchone()[0]
            logger.info(f"Connected to Snowflake {version}. Connection will be reused.")

    def close(self):
        if self._conn and not self._conn.is_closed():
            logger.info("Closing persistent Snowflake connection.")
            self._conn.close()

    async def execute_query(self, query: str):
        with closing(self._conn.cursor(snowflake.connector.DictCursor)) as cur:
            cur.execute(query)
            return cur.fetchall() if cur.description else []

    async def list_tables(self, database: str, schema: str):
        query = (
            f"SELECT table_name, comment FROM "
            f"{database}.information_schema.tables WHERE table_schema='{schema}'"
        )
        rows = await self.execute_query(query)
        return [{"name": r["TABLE_NAME"], "comment": r["COMMENT"]} for r in rows]

    async def describe_table(self, database: str, schema: str, table: str):
        query = (
            f"SELECT column_name, data_type, is_nullable, comment "
            f"FROM {database}.information_schema.columns "
            f"WHERE table_schema='{schema}' AND table_name='{table}' ORDER BY ordinal_position"
        )
        return await self.execute_query(query)


# --- FIX: Custom JSON encoder that handles Decimal and Datetime types ---
class CustomEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj) # Convert Decimal to float
        return super().default(obj)


async def build_full_schema_cache():
    """
    Connects to Snowflake and builds a complete cache of the schema,
    including a single sample row for each table.
    """
    db = EfficientSnowflakeDatabase()
    schema_cache = {"databases": {}}
    
    print("Starting schema cache build...")
    db_name = SNOWFLAKE_DATABASE.upper()
    schema_name = SNOWFLAKE_SCHEMA.upper()
    
    schema_cache["databases"][db_name] = {"schemas": {schema_name: {"tables": {}}}}
    
    try:
        print(f"Processing schema: {db_name}.{schema_name}")
        tables = await db.list_tables(db_name, schema_name)
        total_tables = len(tables)
        
        print(f"Found {total_tables} tables to process")
        
        for idx, table_meta in enumerate(tables, 1):
            table_name = table_meta['name']
            full_table_name = f"{db_name}.{schema_name}.{table_name}"
            print(f"Processing table ({idx}/{total_tables}): {full_table_name}")
            
            columns = await db.describe_table(db_name, schema_name, table_name)
            
            sample_row = None
            try:
                sample_data = await db.execute_query(f"SELECT * FROM {full_table_name} LIMIT 1")
                if sample_data:
                    sample_row = sample_data[0] 
            except Exception as e:
                print(f"Could not retrieve a sample row for {full_table_name}. Table might be empty. Error: {e}")

            schema_cache["databases"][db_name]["schemas"][schema_name]["tables"][table_name] = {
                "comment": table_meta.get("comment", ""),
                "columns": columns,
                "sample_row": sample_row
            }
            
    except Exception as e:
        print(f"A critical error occurred during cache build: {e}")
        raise
    finally:
        # Ensure the connection is closed no matter what
        db.close()

    # Write the completed cache to a file
    with open(CACHE_OUTPUT_FILE, "w") as f:
        json.dump(schema_cache, f, indent=4, cls=CustomEncoder)
        
    print(f"Successfully built and wrote schema cache to '{CACHE_OUTPUT_FILE}'")
    print("Cache refresh complete!")

if __name__ == "__main__":
    asyncio.run(build_full_schema_cache())