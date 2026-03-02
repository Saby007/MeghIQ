"""
MCP Server - SQL Chatbot
HTTP Streamable MCP server that uses GPT-4.1 to generate SQL queries
and executes them against Azure SQL using managed identity (Entra ID).
"""

import os
import json
import struct
import pyodbc
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from openai import AzureOpenAI
from mcp.server.fastmcp import FastMCP

load_dotenv()

# ── Azure OpenAI config ──────────────────────────────────────────────
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

# ── Azure SQL config ─────────────────────────────────────────────────
SQL_SERVER = os.getenv("SQL_SERVER")
SQL_DATABASE = os.getenv("SQL_DATABASE")

# ── Credential (DefaultAzureCredential → works with az login locally) ─
credential = DefaultAzureCredential()

# ── Azure OpenAI client (token-based auth via Entra ID) ──────────────
openai_client = AzureOpenAI(
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    azure_ad_token_provider=lambda: credential.get_token(
        "https://cognitiveservices.azure.com/.default"
    ).token,
    api_version=AZURE_OPENAI_API_VERSION,
)

# ── MCP Server ────────────────────────────────────────────────────────
port = int(os.getenv("MCP_SERVER_PORT", "8001"))
mcp = FastMCP(
    "SQL Chatbot MCP Server",
    instructions="MCP server that generates and executes SQL queries against Azure SQL",
    host="0.0.0.0",
    port=port,
)


def _get_sql_connection():
    """Get a pyodbc connection to Azure SQL using Entra ID token."""
    token = credential.get_token("https://database.windows.net/.default").token
    token_bytes = token.encode("utf-16-le")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
    conn_str = (
        f"Driver={{ODBC Driver 17 for SQL Server}};"
        f"Server=tcp:{SQL_SERVER},1433;"
        f"Database={SQL_DATABASE};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no;"
    )
    conn = pyodbc.connect(conn_str, attrs_before={1256: token_struct})
    return conn


def _get_schema_info() -> str:
    """Retrieve database schema information for the LLM context."""
    conn = _get_sql_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            t.TABLE_SCHEMA,
            t.TABLE_NAME,
            c.COLUMN_NAME,
            c.DATA_TYPE,
            c.IS_NULLABLE,
            CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 'YES' ELSE 'NO' END AS IS_PRIMARY_KEY
        FROM INFORMATION_SCHEMA.TABLES t
        JOIN INFORMATION_SCHEMA.COLUMNS c 
            ON t.TABLE_SCHEMA = c.TABLE_SCHEMA AND t.TABLE_NAME = c.TABLE_NAME
        LEFT JOIN (
            SELECT ku.TABLE_SCHEMA, ku.TABLE_NAME, ku.COLUMN_NAME
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
                ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
            WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
        ) pk ON c.TABLE_SCHEMA = pk.TABLE_SCHEMA 
            AND c.TABLE_NAME = pk.TABLE_NAME 
            AND c.COLUMN_NAME = pk.COLUMN_NAME
        WHERE t.TABLE_TYPE = 'BASE TABLE'
        ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME, c.ORDINAL_POSITION
    """)
    rows = cursor.fetchall()
    conn.close()

    schema_text = "DATABASE SCHEMA:\n"
    current_table = ""
    for row in rows:
        table_full = f"{row.TABLE_SCHEMA}.{row.TABLE_NAME}"
        if table_full != current_table:
            current_table = table_full
            schema_text += f"\nTable: {current_table}\n"
            schema_text += f"  {'Column':<30} {'Type':<15} {'Nullable':<10} {'PK':<5}\n"
            schema_text += f"  {'-'*30} {'-'*15} {'-'*10} {'-'*5}\n"
        schema_text += f"  {row.COLUMN_NAME:<30} {row.DATA_TYPE:<15} {row.IS_NULLABLE:<10} {row.IS_PRIMARY_KEY:<5}\n"

    return schema_text


def _generate_sql(user_question: str, schema_info: str) -> str:
    """Use GPT-4.1 to generate a SQL query from the user's natural language question."""
    response = openai_client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert SQL Server query generator. "
                    "Given a database schema and a user question, generate a valid T-SQL query. "
                    "Return ONLY the SQL query, no explanation, no markdown formatting, no backticks. "
                    "Use TOP 50 to limit results unless the user asks for a specific count. "
                    "Always use schema-qualified table names (e.g., SalesLT.Product). "
                    "For aggregation questions, include meaningful column aliases."
                ),
            },
            {
                "role": "user",
                "content": f"Database Schema:\n{schema_info}\n\nUser Question: {user_question}",
            },
        ],
        temperature=0,
        max_tokens=1000,
    )
    return response.choices[0].message.content.strip()


def _execute_sql(sql_query: str) -> dict:
    """Execute a SQL query and return results as a dict with columns and rows."""
    conn = _get_sql_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql_query)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = []
        for row in cursor.fetchall():
            rows.append([str(v) if v is not None else "NULL" for v in row])
        conn.close()
        return {"columns": columns, "rows": rows, "row_count": len(rows)}
    except Exception as e:
        conn.close()
        raise e


# ── MCP Tools ─────────────────────────────────────────────────────────


@mcp.tool()
def query_database(question: str) -> str:
    """
    Takes a natural language question about the database, generates SQL using GPT-4.1,
    executes it against Azure SQL, and returns the results as structured JSON.

    Args:
        question: A natural language question about data in the database.
                  Examples: "How many products are there?",
                           "Show me the top 5 customers by total sales",
                           "What product categories exist?"
    Returns:
        JSON string with the SQL query used, column names, rows of data, and row count.
    """
    try:
        # 1. Get schema
        schema_info = _get_schema_info()

        # 2. Generate SQL from natural language
        sql_query = _generate_sql(question, schema_info)

        # 3. Execute
        results = _execute_sql(sql_query)

        return json.dumps(
            {
                "status": "success",
                "sql_query": sql_query,
                "columns": results["columns"],
                "rows": results["rows"],
                "row_count": results["row_count"],
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "question": question}
        )


@mcp.tool()
def get_database_schema() -> str:
    """
    Returns the full schema of the database including all tables, columns,
    data types, nullability, and primary key information.

    Returns:
        A formatted text representation of the database schema.
    """
    try:
        schema = _get_schema_info()
        return schema
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})


@mcp.tool()
def execute_raw_sql(sql_query: str) -> str:
    """
    Executes a raw SQL query against the database and returns results.
    Use this for follow-up queries or when you already have the exact SQL.

    Args:
        sql_query: A valid T-SQL query to execute against the database.
    Returns:
        JSON string with column names, rows of data, and row count.
    """
    try:
        results = _execute_sql(sql_query)
        return json.dumps(
            {
                "status": "success",
                "sql_query": sql_query,
                "columns": results["columns"],
                "rows": results["rows"],
                "row_count": results["row_count"],
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "sql_query": sql_query}
        )


# ── Entry point ───────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"Starting MCP Server on http://0.0.0.0:{port}/mcp")
    mcp.run(transport="streamable-http")
