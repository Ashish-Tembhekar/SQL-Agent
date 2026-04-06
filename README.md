# SQL AI Agent

A CLI-based and web-enabled AI Agent built with Langchain that translates natural language questions into SQL queries, executes them against a Supabase PostgreSQL database, and returns answers in plain English. The agent is database-agnostic — it dynamically fetches the schema of whatever Supabase PostgreSQL database you connect it to.

## Features

- **Natural Language to SQL**: Ask questions in plain English, get data-driven answers
- **Dual LLM Support**: Use OpenAI-compatible endpoints (NVIDIA, OpenRouter, etc.) or local Ollama
- **Verbose Debugging Mode**: Inspect every step of the agent's reasoning process
- **Supabase Integration**: Connected to a PostgreSQL database via Supabase REST API
- **Safe Write Operations**: INSERT/UPDATE/DELETE are queued as pending changes with preview before commit
- **Dynamic Schema Discovery**: Automatically fetches database schema — works with any PostgreSQL database
- **Database-Agnostic**: Point it at any Supabase project and it adapts to whatever tables exist
- **Three Interfaces**: CLI, REST API, and WebSocket-powered React chat UI

## Project Structure

```
SQL-Agent/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── agent.py             # Core agent logic
│   │   ├── tools.py             # Agent tools (execute_sql, get_schema, commit, rollback)
│   │   ├── models.py            # Pydantic models for API
│   │   ├── schemas.py           # Schema cache, transaction state, helpers
│   │   ├── config.py            # Environment config
│   │   └── callbacks.py         # Streaming callback handler
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Main app component
│   │   ├── main.jsx             # React entry point
│   │   ├── components/
│   │   │   ├── ChatWindow.jsx   # Chat message display
│   │   │   ├── InputBar.jsx     # User input with send button
│   │   │   ├── MessageBubble.jsx # Individual message component
│   │   │   └── PendingChanges.jsx # Preview pending write operations
│   │   ├── hooks/
│   │   │   └── useChat.js       # WebSocket/chat state management
│   │   └── styles/
│   │       └── App.css          # Chat UI styling
│   ├── package.json
│   ├── vite.config.js
│   └── index.html
├── cli.py                       # CLI entry point (imports from backend)
├── requirements.txt             # Root-level Python dependencies
├── Changes.md                   # Database change log
└── README.md                    # This file
```

## Prerequisites

- Python 3.10 or higher
- Node.js 18 or higher (for the web UI)
- A Supabase project with PostgreSQL database
- Either:
  - An OpenAI-compatible API endpoint (NVIDIA NIM, OpenRouter, etc.)
  - Or [Ollama](https://ollama.ai) installed locally

## Installation

1. **Navigate to the project directory:**

   ```bash
   cd "path/to/SQL-Agent"
   ```

2. **Install Python dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Install frontend dependencies:**

   ```bash
   cd frontend
   npm install
   cd ..
   ```

4. **Configure environment variables:**

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

### Required SQL Functions

You need to create two helper functions in your Supabase database:

```sql
-- For read queries
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

-- For write queries (INSERT/UPDATE/DELETE)
CREATE OR REPLACE FUNCTION exec_sql_write(sql text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  result jsonb;
BEGIN
  EXECUTE sql;
  GET DIAGNOSTICS result = ROW_COUNT;
  RETURN jsonb_build_object('rows_affected', result);
END;
$$;
```

## Usage

### Option 1: Web UI (Recommended)

Start the backend server:

```bash
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

In a separate terminal, start the frontend dev server:

```bash
cd frontend
npm run dev
```

Open `http://localhost:3000` in your browser.

### Option 2: CLI

```bash
python cli.py
```

#### CLI Flags

| Flag           | Description                                      |
|----------------|--------------------------------------------------|
| `-v, --verbose`| Show detailed agent thinking steps and tool calls|
| `-o, --ollama` | Use local Ollama instead of OpenAI-compatible endpoints|
| `-h, --help`   | Show help message and exit                       |

#### Examples

```bash
python cli.py              # Cloud API, clean output
python cli.py -v           # Cloud API, verbose output
python cli.py -o           # Local Ollama, clean output
python cli.py -o -v        # Local Ollama, verbose output
```

### Option 3: REST API

```bash
# Send a chat message
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "How many users are there?", "session_id": "default"}'

# Commit pending changes
curl -X POST http://localhost:8000/api/commit \
  -H "Content-Type: application/json" \
  -d '{"session_id": "default"}'

# Rollback pending changes
curl -X POST http://localhost:8000/api/rollback \
  -H "Content-Type: application/json" \
  -d '{"session_id": "default"}'

# Check session status
curl http://localhost:8000/api/session/default
```

### WebSocket API

Connect to `ws://localhost:8000/ws/chat/{session_id}` and send JSON messages:

```json
{"message": "How many users are there?", "use_ollama": false}
```

Responses are streamed back as JSON:

```json
{"type": "done", "content": "...", "session_id": "default", "has_pending_changes": false}
```

## Example Queries

```
You: How many records are in the users table?
Agent: There are 1,247 records in the users table.

You: Show me the top 5 products by revenue
Agent: [List of top 5 products with revenue figures...]

You: What is the average order value by customer segment?
Agent: [Breakdown of average order values...]

You: Update the email for user ID 1 to new@email.com
Agent: PENDING UPDATE on table 'users'
       SQL: UPDATE users SET email = 'new@email.com' WHERE id = 1
       Preview of affected rows (1 total):
         Row 1: {"id": 1, "email": "old@email.com", ...}
       This change is queued. Use commit_transaction() to apply all pending changes
       or rollback_transaction() to discard them.

You: commit
Agent: Transaction committed successfully.
       Total rows affected: 1
       ...

You: /bye
Agent: Goodbye!
```

## Architecture

```
User (Web UI / CLI / REST API)
    │
    ▼
┌─────────────────┐
│  FastAPI Server │
│  (Backend)      │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌─────────┐ ┌──────────────────┐
│  LLM    │ │  Tools            │
│ (OpenAI │ │  - execute_sql    │
│ /Ollama)│ │  - get_schema     │
└─────────┘ │  - commit/rollback│
            └────────┬─────────┘
                     │
                     ▼
              ┌──────────────┐
              │   Supabase   │
              │  PostgreSQL  │
              └──────────────┘
```

### Agent Flow

1. **Startup**: Agent connects to Supabase and fetches the full database schema from `information_schema`
2. **User inputs** a natural language question (via CLI, REST, or WebSocket)
3. **LLM analyzes** the question with schema context and decides which tool to use
4. **Tool execution**: SQL query is generated and executed against Supabase via RPC
5. **Results returned** to the LLM for analysis
6. **Final answer** generated in natural language and displayed to the user

### Write Safety

- SELECT queries execute immediately and return results
- INSERT/UPDATE/DELETE queries are queued as pending changes with a preview of affected rows
- Changes are only executed after explicit user confirmation (commit)
- Pending changes can be discarded at any time (rollback)
- All changes are logged to `Changes.md`

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

- **Read-Only by Default**: SELECT queries execute immediately; writes require explicit confirmation
- **API Key Safety**: Never commit the `.env` file to version control
- **Supabase Key**: Use the anon key for read-only operations; service role key provides full access
- **RPC Functions**: The `exec_sql` and `exec_sql_write` functions use `SECURITY DEFINER` — ensure your Supabase RLS policies are configured appropriately

## Troubleshooting

### "Module not found" errors
Run `pip install -r requirements.txt` to install all dependencies.

### "Cannot find module" in frontend
Run `cd frontend && npm install` to install frontend dependencies.

### Ollama connection refused
Ensure Ollama is running: `ollama serve` or check if it's running on `localhost:11434`.

### Supabase connection errors
Verify your `SUPABASE_URL` and `SUPABASE_KEY` are correct in the `.env` file.

### LLM API errors
Check that your `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `OPENAI_MODEL` are correctly configured.

### "No tables found" error
Ensure your database has tables in the `public` schema. The agent only discovers tables in the public schema by default.

### RPC function not found
Make sure you've created both `exec_sql` and `exec_sql_write` functions in your Supabase database (see Database Setup section).

## Dependencies

### Backend

| Package              | Purpose                          |
|----------------------|----------------------------------|
| langchain            | Core agent framework             |
| langchain-openai     | OpenAI/Ollama LLM integration    |
| langchain-community  | Community tools and utilities    |
| python-dotenv        | Environment variable management  |
| supabase             | Supabase Python client           |
| psycopg2-binary      | PostgreSQL driver                |
| fastapi              | Web framework                    |
| uvicorn              | ASGI server                      |
| websockets           | WebSocket support                |

### Frontend

| Package              | Purpose                          |
|----------------------|----------------------------------|
| react                | UI library                       |
| react-dom            | React DOM rendering              |
| vite                 | Build tool and dev server        |

## License

This project is provided as-is for educational and demonstration purposes.
