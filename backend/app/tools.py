import json
from langchain_core.tools import tool
from backend.app.schemas import (
    schema_cache,
    get_transaction_state,
    run_sql,
    run_sql_write,
    extract_table_name,
    extract_where_clause,
    build_preview_select,
    get_change_number,
    log_change_to_file,
    fetch_all_schema,
    fetch_table_schema,
)
from datetime import datetime

retry_states = {}
_current_session_id = "default"


def set_current_session(session_id: str):
    global _current_session_id
    _current_session_id = session_id


def get_current_session() -> str:
    return _current_session_id


def get_retry_state(session_id: str) -> dict:
    if session_id not in retry_states:
        retry_states[session_id] = {"count": 0}
    return retry_states[session_id]


def reset_retry(session_id: str):
    retry_states[session_id] = {"count": 0}


@tool
def execute_sql_query(query: str) -> str:
    """Execute a SQL query against the Supabase PostgreSQL database. For SELECT queries, returns results immediately. For INSERT/UPDATE/DELETE, adds to pending transaction queue for preview before commit."""
    session_id = get_current_session()
    query_stripped = query.strip()
    query_type = query_stripped.upper().split()[0] if query_stripped else ""

    if query_type == "SELECT":
        rs = get_retry_state(session_id)
        rs["count"] += 1
        try:
            response = run_sql(query_stripped)
            if response is None or response == [None]:
                return "Query executed successfully. No rows returned."
            rs["count"] = 0
            return str(response)
        except Exception as e:
            error_msg = str(e)
            if rs["count"] >= 3:
                return f"Error: Maximum retry attempts (3) reached. Review the schema with get_table_schema() and try a different approach. Last error: {error_msg}"
            return f"SQL Error: {error_msg}"

    elif query_type in ("INSERT", "UPDATE", "DELETE"):
        preview_select = build_preview_select(query_stripped)
        preview_data = None
        if preview_select:
            try:
                preview_resp = run_sql(preview_select)
                if preview_resp and preview_resp != [None]:
                    preview_data = preview_resp
            except Exception:
                pass

        table_name = extract_table_name(query_stripped)
        stmt_entry = {
            "query": query_stripped,
            "query_type": query_type,
            "table": table_name,
            "preview_data": preview_data,
        }
        tx_state = get_transaction_state(session_id)
        tx_state["pending_statements"].append(stmt_entry)
        tx_state["is_active"] = True

        preview_text = ""
        if preview_data and len(preview_data) > 0:
            rows_preview = preview_data[:5]
            preview_text = f"\n\nPreview of affected rows ({len(preview_data)} total):\n"
            for i, row in enumerate(rows_preview, 1):
                preview_text += f"  Row {i}: {json.dumps(row, indent=4)}\n"
            if len(preview_data) > 5:
                preview_text += f"  ... and {len(preview_data) - 5} more rows\n"
        else:
            preview_text = "\n\nNo existing rows to preview (this may be a new insert or no matching rows).\n"

        return (
            f"PENDING {query_type} on table '{table_name}'\n"
            f"SQL: {query_stripped}\n"
            f"{preview_text}"
            f"\nThis change is queued. Use commit_transaction() to apply all pending changes "
            f"or rollback_transaction() to discard them."
        )

    else:
        return f"Error: Unsupported query type '{query_type}'. Only SELECT, INSERT, UPDATE, and DELETE are supported."


@tool
def get_table_schema(table_name: str = "") -> str:
    """Get the schema information for tables in the database. Optionally provide a table_name to get schema for a specific table."""
    if table_name:
        cached = schema_cache.get(table_name)
        if cached:
            return cached
        result = fetch_table_schema(table_name)
        schema_cache.set(table_name, result)
        return result
    else:
        cached = schema_cache.get("__all__")
        if cached:
            return cached
        result = fetch_all_schema()
        schema_cache.set("__all__", result)
        return result


@tool
def commit_transaction() -> str:
    """Commit all pending SQL changes in the transaction queue. This will execute all queued INSERT/UPDATE/DELETE statements and log them to Changes.md."""
    session_id = get_current_session()
    tx_state = get_transaction_state(session_id)
    if not tx_state["is_active"] or not tx_state["pending_statements"]:
        return "No pending changes to commit. The transaction queue is empty."

    results = []
    total_affected = 0
    change_num = get_change_number()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entries = []

    for i, stmt in enumerate(tx_state["pending_statements"], 1):
        try:
            response = run_sql_write(stmt["query"])
            rows_affected = 0
            if response and isinstance(response, dict):
                rows_affected = response.get("rows_affected", 0)
                if response.get("error"):
                    results.append(f"Statement {i} error: {response['error']}")
                    continue
            total_affected += rows_affected

            preview_before = ""
            if stmt.get("preview_data"):
                preview_before = json.dumps(stmt["preview_data"], indent=2)

            log_entry = (
                f"## Change #{change_num + i - 1} — {timestamp}\n"
                f"- **Type:** {stmt['query_type']}\n"
                f"- **Table:** {stmt['table']}\n"
                f"- **Rows Affected:** {rows_affected}\n"
                f"- **SQL:** `{stmt['query']}`\n"
            )
            if preview_before:
                log_entry += f"- **Before:** `{preview_before}`\n"
            log_entry += "\n---\n\n"
            log_entries.append(log_entry)

            results.append(
                f"Statement {i}: {stmt['query_type']} on '{stmt['table']}' — {rows_affected} rows affected"
            )
        except Exception as e:
            results.append(f"Statement {i} FAILED: {str(e)}")

    for entry in log_entries:
        log_change_to_file(entry)

    tx_state["pending_statements"].clear()
    tx_state["is_active"] = False

    summary = "\n".join(results)
    return (
        f"Transaction committed successfully.\n"
        f"Total rows affected: {total_affected}\n"
        f"Details:\n{summary}\n"
        f"\nChanges logged to Changes.md."
    )


@tool
def rollback_transaction() -> str:
    """Discard all pending SQL changes in the transaction queue without executing them."""
    session_id = get_current_session()
    tx_state = get_transaction_state(session_id)
    count = len(tx_state["pending_statements"])
    tx_state["pending_statements"].clear()
    tx_state["is_active"] = False

    if count == 0:
        return "No pending changes to rollback. The transaction queue is already empty."

    return f"Transaction rolled back. {count} pending change(s) discarded."
