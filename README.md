# SQL Querying AI Agent

A CLI-based AI Agent built with Langchain that translates natural language questions into SQL queries, executes them against a Supabase PostgreSQL database, and returns answers in plain English. The agent is database-agnostic — it dynamically fetches the schema of whatever Supabase PostgreSQL database you connect it to.

## Features

- **Natural Language to SQL**: Ask questions in plain English, get data-driven answers
- **Dual LLM Support**: Use OpenAI-compatible endpoints (NVIDIA, OpenRouter, etc.) or local Ollama
- **Verbose Debugging Mode**: Inspect every step of the agent's reasoning process
- **Supabase Integration**: Connected to a PostgreSQL database via Supabase REST API
- **Safe Execution**: Only SELECT queries are allowed; no data modification permitted
- **Dynamic Schema Discovery**: Automatically fetches database schema at startup — works with any PostgreSQL database, not hardcoded to a specific schema
- **Database-Agnostic**: Point it at any Supabase project and it adapts to whatever tables exist

## Project Structure

```
SQL Agent/
├── agent.py           # Main CLI application
├── requirements.txt   # Python dependencies
├── .env               # Environment variables (do not commit)
├── .gitignore         # Git ignore rules
└── README.md          # This file
```

## Prerequisites

- Python 3.10 or higher
- A Supabase project with PostgreSQL database
- Either:
  - An OpenAI-compatible API endpoint (NVIDIA NIM, OpenRouter, etc.)
  - Or [Ollama](https://ollama.ai) installed locally

## Installation

1. **Navigate to the project directory:**

   ```bash
   cd "path/to/SQL Agent"
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**

   Create a `.env` file with your credentials:

   ```env
   # Supabase Configuration
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_KEY=your-supabase-anon-key

   # OpenAI Compatible LLM Configuration (for cloud providers)
   OPENAI_BASE_URL=https://your-api-endpoint/v1
   OPENAI_API_KEY=your-api-key
   OPENAI_MODEL=your-model-name

   # Ollama Configuration (for local inference)
   OLLAMA_MODEL_ID=llama3.2
   ```

## Database Setup

The agent works with **any** Supabase PostgreSQL database. It dynamically discovers the schema at startup by querying the `information_schema.columns` table.

### Required SQL Function

You need to create one helper function in your Supabase database to enable raw SQL execution via RPC:

```sql
CREATE OR REPLACE FUNCTION exec_sql(sql text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  result jsonb;
BEGIN
  EXECUTE format('SELECT jsonb_agg(t) FROM (%s) t', sql) INTO result;
  RETURN result;
END;
$$;
```

This function:
- Accepts a SQL query as text
- Executes it safely within the database
- Returns results as JSONB
- Uses `SECURITY DEFINER` to run with elevated privileges (required for `information_schema` access)

### How Schema Discovery Works

On startup, the agent:
1. Connects to your Supabase database
2. Queries `information_schema.columns` to get all tables, columns, data types, nullability, and defaults
3. Queries row counts for each table
4. Formats this into a readable schema summary
5. Injects it into the agent's system prompt

This means the agent **automatically adapts** to whatever database you point it at — no hardcoded table names or column definitions.

## Usage

### Basic Mode (Clean Output)

```bash
python agent.py
```

The agent will start, fetch the schema, and display only the final answer to each question.

### Verbose Mode (Show All Steps)

```bash
python agent.py -v
```

Displays the complete reasoning chain including:
- LLM call start and prompts
- LLM responses with tool calls
- Tool inputs and outputs
- Final answer

### Ollama Mode (Local Inference)

```bash
python agent.py -o
```

Uses your local Ollama instance instead of cloud APIs. Requires Ollama to be running on `localhost:11434`.

### Ollama + Verbose

```bash
python agent.py -o -v
```

### Combined Flags

| Command              | Description                           |
|----------------------|---------------------------------------|
| `python agent.py`    | Cloud API, clean output               |
| `python agent.py -v` | Cloud API, verbose output             |
| `python agent.py -o` | Local Ollama, clean output            |
| `python agent.py -o -v` | Local Ollama, verbose output     |

## CLI Arguments

| Flag           | Description                                      |
|----------------|--------------------------------------------------|
| `-v, --verbose`| Show detailed agent thinking steps and tool calls|
| `-o, --ollama` | Use local Ollama instead of OpenAI-compatible endpoints|
| `-h, --help`   | Show help message and exit                       |

## Example Queries

Once the agent is running, try asking questions relevant to your database:

```
You: How many records are in the users table?
Agent: There are 1,247 records in the users table.

You: Show me the top 5 products by revenue
Agent: [List of top 5 products with revenue figures...]

You: What is the average order value by customer segment?
Agent: [Breakdown of average order values...]

You: List all orders from the last 30 days
Agent: [List of recent orders...]

You: /bye
Agent: Goodbye!
```

## Architecture

```
User Input
    │
    ▼
┌─────────────────┐
│  Langchain Agent │
│  (ReAct Pattern) │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌─────────┐ ┌──────────────────┐
│  LLM    │ │  Tools            │
│ (OpenAI │ │  - execute_sql    │
│ /Ollama)│ │  - get_schema     │
└─────────┘ └────────┬─────────┘
                     │
                     ▼
              ┌──────────────┐
              │   Supabase   │
              │  PostgreSQL  │
              └──────────────┘
```

### Agent Flow

1. **Startup**: Agent connects to Supabase and fetches the full database schema from `information_schema`
2. **User inputs** a natural language question
3. **LLM analyzes** the question with schema context and decides which tool to use
4. **Tool execution**: SQL query is generated and executed against Supabase via RPC
5. **Results returned** to the LLM for analysis
6. **Final answer** generated in natural language and displayed to the user

### Schema Discovery Query

The agent runs this query at startup to discover your database structure:

```sql
SELECT 
    table_name,
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position;
```

This returns every table, column, data type, nullability constraint, and default value — giving the LLM complete context to write accurate SQL queries.

## Environment Variables

| Variable           | Required | Description                                    |
|--------------------|----------|------------------------------------------------|
| SUPABASE_URL       | Yes      | Your Supabase project URL                      |
| SUPABASE_KEY       | Yes      | Supabase anon/service role key                 |
| OPENAI_BASE_URL    | If not using Ollama | Base URL for OpenAI-compatible API    |
| OPENAI_API_KEY     | If not using Ollama | API key for the LLM provider            |
| OPENAI_MODEL       | If not using Ollama | Model identifier to use                 |
| OLLAMA_MODEL_ID    | If using Ollama     | Local Ollama model name (e.g., llama3.2) |

## Security Notes

- **Read-Only Access**: The agent only executes SELECT queries; INSERT, UPDATE, DELETE, and DROP are blocked at the tool level
- **API Key Safety**: Never commit the `.env` file to version control
- **Supabase Key**: Use the anon key for read-only operations; service role key provides full access
- **RPC Function**: The `exec_sql` function uses `SECURITY DEFINER` — ensure your Supabase RLS policies are configured appropriately

## Troubleshooting

### "Module not found" errors
Run `pip install -r requirements.txt` to install all dependencies.

### Ollama connection refused
Ensure Ollama is running: `ollama serve` or check if it's running on `localhost:11434`.

### Supabase connection errors
Verify your `SUPABASE_URL` and `SUPABASE_KEY` are correct in the `.env` file.

### LLM API errors
Check that your `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `OPENAI_MODEL` are correctly configured.

### "No tables found" error
Ensure your database has tables in the `public` schema. The agent only discovers tables in the public schema by default.

### RPC function not found
Make sure you've created the `exec_sql` function in your Supabase database (see Database Setup section).

## Dependencies

| Package              | Purpose                          |
|----------------------|----------------------------------|
| langchain            | Core agent framework             |
| langchain-openai     | OpenAI/Ollama LLM integration    |
| langchain-community  | Community tools and utilities    |
| python-dotenv        | Environment variable management  |
| supabase             | Supabase Python client           |
| psycopg2-binary      | PostgreSQL driver                |

## License

This project is provided as-is for educational and demonstration purposes.
