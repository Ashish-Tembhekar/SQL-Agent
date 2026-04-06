import os
import sys
import json
import time
import argparse
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain.agents import create_agent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage, SystemMessage
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL")
OLLAMA_MODEL_ID = os.getenv("OLLAMA_MODEL_ID")

for var, val in [
    ("SUPABASE_URL", SUPABASE_URL),
    ("SUPABASE_KEY", SUPABASE_KEY),
]:
    if not val or "YOUR_" in val:
        print(f"Error: {var} not configured in .env file")
        sys.exit(1)

class AgentCallbackHandler(BaseCallbackHandler):
    def on_llm_start(self, serialized, prompts, **kwargs):
        print("\n" + "=" * 60)
        print("LLM CALL START")
        print("=" * 60)
        for i, prompt in enumerate(prompts):
            if isinstance(prompt, str):
                print(f"\nPrompt {i+1}:\n{prompt[:500]}...")
            elif hasattr(prompt, 'content'):
                content = prompt.content if hasattr(prompt, 'content') else str(prompt)
                print(f"\nPrompt {i+1}:\n{content[:500]}...")

    def on_llm_end(self, response, **kwargs):
        print("\n" + "=" * 60)
        print("LLM RESPONSE")
        print("=" * 60)
        for gen_list in response.generations:
            for gen in gen_list:
                if hasattr(gen, 'message') and gen.message:
                    msg = gen.message
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        print(f"\nTool Calls:")
                        for tc in msg.tool_calls:
                            print(f"   Tool: {tc.get('name', 'unknown')}")
                            print(f"   Args: {json.dumps(tc.get('args', {}), indent=4)}")
                    if hasattr(msg, 'content') and msg.content:
                        print(f"\nContent:\n{msg.content}")
                elif hasattr(gen, 'text') and gen.text:
                    print(f"\n{gen.text}")

    def on_tool_start(self, serialized, input_str, **kwargs):
        print("\n" + "=" * 60)
        print(f"TOOL CALL: {serialized.get('name', 'unknown')}")
        print("=" * 60)
        print(f"\nInput:\n{input_str}")

    def on_tool_end(self, output, **kwargs):
        print("\n" + "=" * 60)
        print("TOOL RESULT")
        print("=" * 60)
        output_str = str(output)
        if len(output_str) > 1000:
            print(f"\nOutput (truncated):\n{output_str[:1000]}...")
        else:
            print(f"\nOutput:\n{output_str}")

    def on_llm_error(self, error, **kwargs):
        print(f"\nLLM Error: {error}")

    def on_tool_error(self, error, **kwargs):
        print(f"\nTool Error: {error}")

class SchemaCache:
    def __init__(self, ttl=60):
        self.ttl = ttl
        self.cache = {}
        self.timestamps = {}

    def get(self, key):
        if key in self.cache and (time.time() - self.timestamps[key]) < self.ttl:
            return self.cache[key]
        return None

    def set(self, key, value):
        self.cache[key] = value
        self.timestamps[key] = time.time()

    def invalidate(self, key=None):
        if key:
            self.cache.pop(key, None)
            self.timestamps.pop(key, None)
        else:
            self.cache.clear()
            self.timestamps.clear()

schema_cache = SchemaCache(ttl=60)

def _run_sql(sql: str):
    response = supabase.rpc("exec_sql", {"sql": sql}).execute()
    return response.data

def _fetch_all_schema():
    try:
        columns_query = """
        SELECT
            c.table_name,
            c.column_name,
            c.data_type,
            c.is_nullable,
            c.column_default,
            c.ordinal_position
        FROM information_schema.columns c
        WHERE c.table_schema = 'public'
          AND c.table_name IN (SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE')
        ORDER BY c.table_name, c.ordinal_position
        """
        columns = _run_sql(columns_query)
        if not columns or columns == [None]:
            return "No tables found in the public schema."

        pk_query = """
        SELECT
            tc.table_name,
            kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY'
          AND tc.table_schema = 'public'
        ORDER BY tc.table_name
        """
        pks = {}
        try:
            pk_rows = _run_sql(pk_query)
            if pk_rows and pk_rows != [None]:
                for row in pk_rows:
                    t = row.get("table_name")
                    c = row.get("column_name")
                    pks.setdefault(t, []).append(c)
        except:
            pass

        fk_query = """
        SELECT
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
            ON tc.constraint_name = ccu.constraint_name
            AND tc.table_schema = ccu.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'public'
        """
        fks = {}
        try:
            fk_rows = _run_sql(fk_query)
            if fk_rows and fk_rows != [None]:
                for row in fk_rows:
                    t = row.get("table_name")
                    fks.setdefault(t, []).append(row)
        except:
            pass

        count_query = """
        SELECT relname as table_name, n_live_tup as row_count
        FROM pg_stat_user_tables
        WHERE schemaname = 'public'
        ORDER BY relname
        """
        row_counts = {}
        try:
            count_rows = _run_sql(count_query)
            if count_rows and count_rows != [None]:
                for row in count_rows:
                    if row:
                        row_counts[row.get("table_name")] = row.get("row_count", "unknown")
        except:
            pass

        schema_text = ""
        current_table = None

        for col in columns:
            if col is None:
                continue
            table_name = col.get("table_name")
            column_name = col.get("column_name")
            data_type = col.get("data_type")
            is_nullable = col.get("is_nullable", "YES")
            column_default = col.get("column_default")

            if table_name != current_table:
                if current_table is not None:
                    schema_text += "\n"
                schema_text += f"Table: {table_name}"
                if table_name in row_counts:
                    schema_text += f" ({row_counts[table_name]} rows)"
                schema_text += "\nColumns:\n"
                current_table = table_name

            nullable_str = "NULLABLE" if is_nullable == "YES" else "NOT NULL"
            default_str = f" DEFAULT {column_default}" if column_default else ""
            pk_marker = " [PRIMARY KEY]" if table_name in pks and column_name in pks[table_name] else ""
            schema_text += f"  - {column_name} ({data_type.upper()}, {nullable_str}{default_str}{pk_marker})\n"

        if fks:
            schema_text += "\nForeign Keys:\n"
            for table, fk_list in fks.items():
                for fk in fk_list:
                    schema_text += f"  - {table}.{fk['column_name']} -> {fk['foreign_table_name']}.{fk['foreign_column_name']}\n"

        return schema_text

    except Exception as e:
        return f"Error fetching schema: {str(e)}"

def _fetch_table_schema(table_name: str):
    try:
        columns_query = f"""
        SELECT
            c.column_name,
            c.data_type,
            c.is_nullable,
            c.column_default
        FROM information_schema.columns c
        WHERE c.table_schema = 'public'
          AND c.table_name = '{table_name}'
        ORDER BY c.ordinal_position
        """
        columns = _run_sql(columns_query)
        if not columns or columns == [None]:
            return f"Error: Table '{table_name}' not found in the public schema."

        pk_query = f"""
        SELECT kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY'
          AND tc.table_schema = 'public'
          AND tc.table_name = '{table_name}'
        """
        pk_cols = []
        try:
            pk_rows = _run_sql(pk_query)
            if pk_rows and pk_rows != [None]:
                pk_cols = [r.get("column_name") for r in pk_rows if r]
        except:
            pass

        fk_query = f"""
        SELECT
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
            ON tc.constraint_name = ccu.constraint_name
            AND tc.table_schema = ccu.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'public'
          AND tc.table_name = '{table_name}'
        """
        fk_rows = []
        try:
            fk_rows = _run_sql(fk_query) or []
            if fk_rows == [None]:
                fk_rows = []
        except:
            pass

        count_query = f"""
        SELECT n_live_tup as row_count
        FROM pg_stat_user_tables
        WHERE schemaname = 'public' AND relname = '{table_name}'
        """
        row_count = "unknown"
        try:
            count_rows = _run_sql(count_query)
            if count_rows and count_rows != [None] and count_rows[0]:
                row_count = count_rows[0].get("row_count", "unknown")
        except:
            pass

        schema_text = f"Table: {table_name} ({row_count} rows)\nColumns:\n"
        for col in columns:
            if col is None:
                continue
            column_name = col.get("column_name")
            data_type = col.get("data_type")
            is_nullable = col.get("is_nullable", "YES")
            column_default = col.get("column_default")
            nullable_str = "NULLABLE" if is_nullable == "YES" else "NOT NULL"
            default_str = f" DEFAULT {column_default}" if column_default else ""
            pk_marker = " [PRIMARY KEY]" if column_name in pk_cols else ""
            schema_text += f"  - {column_name} ({data_type.upper()}, {nullable_str}{default_str}{pk_marker})\n"

        if fk_rows:
            schema_text += "\nForeign Keys:\n"
            for fk in fk_rows:
                if fk:
                    schema_text += f"  - {table_name}.{fk['column_name']} -> {fk['foreign_table_name']}.{fk['foreign_column_name']}\n"

        return schema_text

    except Exception as e:
        return f"Error fetching schema for '{table_name}': {str(e)}"

parser = argparse.ArgumentParser(description="SQL Querying AI Agent")
parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed agent thinking steps and tool calls")
parser.add_argument("-o", "--ollama", action="store_true", help="Use local Ollama instead of OpenAI-compatible endpoints")
args = parser.parse_args()

print("Connecting to Supabase...")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
print("Connected successfully!")
print()

if args.ollama:
    if not OLLAMA_MODEL_ID or "YOUR_" in OLLAMA_MODEL_ID:
        print("Error: OLLAMA_MODEL_ID not configured in .env file")
        sys.exit(1)
    llm = ChatOpenAI(
        model=OLLAMA_MODEL_ID,
        openai_api_key="ollama",
        base_url="http://localhost:11434/v1",
        temperature=0,
    )
else:
    for var, val in [
        ("OPENAI_BASE_URL", OPENAI_BASE_URL),
        ("OPENAI_API_KEY", OPENAI_API_KEY),
        ("OPENAI_MODEL", OPENAI_MODEL),
    ]:
        if not val or "YOUR_" in val:
            print(f"Error: {var} not configured in .env file")
            sys.exit(1)
    llm = ChatOpenAI(
        model=OPENAI_MODEL,
        openai_api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        temperature=0,
    )

retry_state = {"count": 0}

@tool
def execute_sql_query(query: str) -> str:
    """Execute a SQL SELECT query against the Supabase PostgreSQL database and return results."""
    if not query.upper().strip().startswith("SELECT"):
        return "Error: Only SELECT queries are allowed"
    
    retry_state["count"] += 1
    
    try:
        response = supabase.rpc("exec_sql", {"sql": query}).execute()
        if response.data is None or response.data == [None]:
            return "Query executed successfully. No rows returned."
        retry_state["count"] = 0
        return str(response.data)
    except Exception as e:
        error_msg = str(e)
        if retry_state["count"] >= 3:
            return f"Error: Maximum retry attempts (3) reached. Review the schema with get_table_schema() and try a different approach. Last error: {error_msg}"
        return f"SQL Error: {error_msg}"

@tool
def get_table_schema(table_name: str = "") -> str:
    """Get the schema information for tables in the database. Optionally provide a table_name to get schema for a specific table."""
    if table_name:
        cached = schema_cache.get(table_name)
        if cached:
            return cached
        result = _fetch_table_schema(table_name)
        schema_cache.set(table_name, result)
        return result
    else:
        cached = schema_cache.get("__all__")
        if cached:
            return cached
        result = _fetch_all_schema()
        schema_cache.set("__all__", result)
        return result

tools = [execute_sql_query, get_table_schema]

system_prompt = """You are a SQL Querying AI Agent connected to a Supabase PostgreSQL database.

Your task is to:
1. Call get_table_schema() to discover available tables, columns, types, primary keys, and foreign keys
2. Generate the appropriate SQL query based on the schema
3. Execute it using execute_sql_query()
4. Analyze the results and provide a clear natural language answer

Rules:
- Only use SELECT queries (no INSERT, UPDATE, DELETE, DROP, etc.)
- ALWAYS call get_table_schema() before writing queries to ensure you have the latest schema
- If execute_sql_query() returns an error starting with "SQL Error:", analyze the error message carefully, fix the SQL, and retry
- You have a maximum of 3 retry attempts per query — use them wisely
- Common error fixes: table/column name typos, wrong data type comparisons, missing JOIN conditions, incorrect column references
- Present results in a clear, readable format
- If the question cannot be answered with the available data, explain why"""

agent_executor = create_agent(
    llm,
    tools,
    system_prompt=system_prompt,
)

callback_handler = AgentCallbackHandler() if args.verbose else None

print("=" * 60)
mode_label = " (Ollama Mode)" if args.ollama else ""
mode_label += " (Verbose Mode)" if args.verbose else ""
print("SQL Querying AI Agent Ready!" + mode_label)
print("Type your question or /bye to exit")
print("=" * 60)

while True:
    try:
        user_input = input("\nYou: ").strip()
        
        if not user_input:
            continue
            
        if user_input.lower() == "/bye":
            print("Agent: Goodbye!")
            break
        
        retry_state["count"] = 0
        
        config = {"callbacks": [callback_handler]} if callback_handler else {}
        result = agent_executor.invoke({"messages": [("human", user_input)]}, config=config)
        
        if "messages" in result:
            last_message = result["messages"][-1]
            if hasattr(last_message, 'content'):
                print(f"\nAgent: {last_message.content}")
            else:
                print(f"\nAgent: {str(last_message)}")
        else:
            print(f"\nAgent: {str(result)}")
        
    except KeyboardInterrupt:
        print("\n\nAgent: Goodbye!")
        break
    except Exception as e:
        print(f"\nError: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        print("Please try again.")
