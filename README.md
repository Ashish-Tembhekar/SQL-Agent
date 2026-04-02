# SQL Querying AI Agent

A CLI-based AI Agent built with Langchain that translates natural language questions into SQL queries, executes them against a Supabase PostgreSQL database, and returns answers in plain English.

## Features

- **Natural Language to SQL**: Ask questions in plain English, get data-driven answers
- **Dual LLM Support**: Use OpenAI-compatible endpoints (NVIDIA, OpenRouter, etc.) or local Ollama
- **Verbose Debugging Mode**: Inspect every step of the agent's reasoning process
- **Supabase Integration**: Connected to a PostgreSQL database via Supabase REST API
- **Safe Execution**: Only SELECT queries are allowed; no data modification permitted
- **Schema-Aware**: Agent loads database schema at startup for accurate query generation

## Project Structure

```
D:\SQL Agent\
├── agent.py           # Main CLI application
├── requirements.txt   # Python dependencies
├── .env               # Environment variables (do not commit)
├── MOCK_DATA.csv      # Source data (500 employee records)
└── README.md          # This file
```

## Prerequisites

- Python 3.10 or higher
- A Supabase project with PostgreSQL database
- Either:
  - An OpenAI-compatible API endpoint (NVIDIA NIM, OpenRouter, etc.)
  - Or [Ollama](https://ollama.ai) installed locally

## Installation

1. **Clone or navigate to the project directory:**

   ```bash
   cd "D:\SQL Agent"
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**

   Edit the `.env` file with your credentials:

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

The project includes a Supabase MCP integration to set up the database automatically. The following has been configured:

### Table: `employees`

| Column     | Type     | Description              |
|------------|----------|--------------------------|
| id         | INTEGER  | Primary key              |
| first_name | VARCHAR  | Employee first name      |
| last_name  | VARCHAR  | Employee last name       |
| email      | VARCHAR  | Employee email address   |
| gender     | VARCHAR  | Gender identity          |
| role       | VARCHAR  | Department/role          |

### Sample Data

500 employee records loaded from `MOCK_DATA.csv` with diverse roles and gender identities.

### SQL Function

A helper function `exec_sql(sql text)` is created in Supabase to execute raw SQL queries via RPC calls.

## Usage

### Basic Mode (Clean Output)

```bash
python agent.py
```

The agent will start and display only the final answer to each question.

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

Once the agent is running, try asking:

```
You: How many employees are in the Engineering department?
Agent: There are 39 employees in the Engineering department.

You: Show me the gender distribution across all roles
Agent: [Detailed breakdown of gender by role...]

You: List all employees in Marketing with their email addresses
Agent: [List of Marketing employees with emails...]

You: What is the most common role in the company?
Agent: [Analysis of role frequencies...]

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

1. **User inputs** a natural language question
2. **LLM analyzes** the question and decides which tool to use
3. **Tool execution**: SQL query is generated and executed against Supabase
4. **Results returned** to the LLM for analysis
5. **Final answer** generated in natural language and displayed to the user

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

- **Read-Only Access**: The agent only executes SELECT queries; INSERT, UPDATE, DELETE, and DROP are blocked
- **API Key Safety**: Never commit the `.env` file to version control
- **Supabase Key**: Use the anon key for read-only operations; service role key provides full access

## Troubleshooting

### "Module not found" errors
Run `pip install -r requirements.txt` to install all dependencies.

### Ollama connection refused
Ensure Ollama is running: `ollama serve` or check if it's running on `localhost:11434`.

### Supabase connection errors
Verify your `SUPABASE_URL` and `SUPABASE_KEY` are correct in the `.env` file.

### LLM API errors
Check that your `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `OPENAI_MODEL` are correctly configured.

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
