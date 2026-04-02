import os
import sys
import json
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

parser = argparse.ArgumentParser(description="SQL Querying AI Agent")
parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed agent thinking steps and tool calls")
parser.add_argument("-o", "--ollama", action="store_true", help="Use local Ollama instead of OpenAI-compatible endpoints")
args = parser.parse_args()

print("Connecting to Supabase...")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
print("Connected successfully!")

schema_info = """
Table: employees
Columns:
- id (INTEGER, PRIMARY KEY)
- first_name (VARCHAR)
- last_name (VARCHAR)
- email (VARCHAR)
- gender (VARCHAR)
- role (VARCHAR)

Total records: 500 employees
Roles include: Engineering, Marketing, Sales, Legal, Accounting, Human Resources, Business Development, Product Management, Services, Support, Training, Research and Development
Genders include: Male, Female, Agender, Genderfluid, Genderqueer, Bigender, Polygender, Non-binary
"""

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

@tool
def execute_sql_query(query: str) -> str:
    """Execute a SQL SELECT query against the Supabase PostgreSQL database and return results."""
    if not query.upper().strip().startswith("SELECT"):
        return "Error: Only SELECT queries are allowed"
    
    try:
        response = supabase.rpc("exec_sql", {"sql": query}).execute()
        return str(response.data)
    except Exception as e:
        return f"Error executing query: {str(e)}"

@tool
def get_table_schema() -> str:
    """Get the schema information for all tables in the database."""
    return schema_info

tools = [execute_sql_query, get_table_schema]

system_prompt = f"""You are a SQL Querying AI Agent connected to a Supabase PostgreSQL database.

DATABASE SCHEMA:
{schema_info}

Your task is to:
1. Understand the user's question
2. Generate the appropriate SQL query to fetch the data
3. Execute the query using the execute_sql_query tool
4. Analyze the results
5. Provide a clear, natural language answer based on the fetched data

Rules:
- Only use SELECT queries (no INSERT, UPDATE, DELETE, DROP, etc.)
- Always check the schema before writing queries
- If a query fails, try to fix it and retry
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
