import os
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from backend.app.config import OPENAI_BASE_URL, OPENAI_API_KEY, OPENAI_MODEL, OLLAMA_MODEL_ID
from backend.app.tools import execute_sql_query, get_table_schema, commit_transaction, rollback_transaction, reset_retry, set_current_session

SYSTEM_PROMPT = """You are a SQL Querying AI Agent connected to a Supabase PostgreSQL database.

Your task is to:
1. Call get_table_schema() to discover available tables, columns, types, primary keys, and foreign keys
2. Generate the appropriate SQL query based on the schema
3. Execute it using execute_sql_query()
4. Analyze the results and provide a clear natural language answer

Rules:
- Use SELECT queries for reading data — results are returned immediately
- Use INSERT, UPDATE, or DELETE queries for modifying data — these are queued as pending changes with a preview, NOT executed immediately
- When a user asks to modify data, always show them a preview of the affected rows before confirming
- After queuing write changes, inform the user about the pending changes and wait for their instruction
- Use commit_transaction() to execute all pending changes and log them to Changes.md
- Use rollback_transaction() to discard all pending changes without executing them
- NEVER commit changes without explicit user confirmation
- ALWAYS call get_table_schema() before writing queries to ensure you have the latest schema
- If execute_sql_query() returns an error starting with "SQL Error:", analyze the error message carefully, fix the SQL, and retry
- You have a maximum of 3 retry attempts per query — use them wisely
- Common error fixes: table/column name typos, wrong data type comparisons, missing JOIN conditions, incorrect column references
- Present results in a clear, readable format
- If the question cannot be answered with the available data, explain why"""

agents = {}


def create_llm(use_ollama: bool = False):
    if use_ollama:
        return ChatOpenAI(
            model=OLLAMA_MODEL_ID,
            openai_api_key="ollama",
            base_url="http://localhost:11434/v1",
            temperature=0,
        )
    else:
        return ChatOpenAI(
            model=OPENAI_MODEL,
            openai_api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            temperature=0,
        )


def get_agent(session_id: str, use_ollama: bool = False):
    if session_id not in agents:
        llm = create_llm(use_ollama)
        tools = [execute_sql_query, get_table_schema, commit_transaction, rollback_transaction]
        agent = create_agent(llm, tools, system_prompt=SYSTEM_PROMPT)
        agents[session_id] = agent
    return agents[session_id]


def invoke_agent(session_id: str, message: str, use_ollama: bool = False, callbacks=None):
    set_current_session(session_id)
    reset_retry(session_id)
    agent = get_agent(session_id, use_ollama)
    config = {"callbacks": callbacks} if callbacks else {}
    result = agent.invoke({"messages": [("human", message)]}, config=config)
    if "messages" in result:
        last_message = result["messages"][-1]
        if hasattr(last_message, 'content'):
            return last_message.content
        return str(last_message)
    return str(result)


def clear_agent(session_id: str):
    agents.pop(session_id, None)
