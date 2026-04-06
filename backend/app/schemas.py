import os
import re
import time
import json
from datetime import datetime
from supabase import create_client
from backend.app.config import SUPABASE_URL, SUPABASE_KEY, CHANGES_FILE


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

transaction_states = {}


def get_transaction_state(session_id: str) -> dict:
    if session_id not in transaction_states:
        transaction_states[session_id] = {
            "pending_statements": [],
            "is_active": False,
        }
    return transaction_states[session_id]


def clear_transaction_state(session_id: str):
    transaction_states.pop(session_id, None)


supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def run_sql(sql: str):
    response = supabase.rpc("exec_sql", {"sql": sql}).execute()
    return response.data


def run_sql_write(sql: str):
    response = supabase.rpc("exec_sql_write", {"sql": sql}).execute()
    return response.data


def extract_table_name(query: str) -> str:
    query_upper = query.strip().upper()
    parts = query.strip().split()
    if query_upper.startswith("UPDATE") and len(parts) >= 2:
        return parts[1]
    elif query_upper.startswith("DELETE") and len(parts) >= 4:
        idx = next((i for i, p in enumerate(parts) if p.upper() == "FROM"), -1)
        if idx >= 0 and idx + 1 < len(parts):
            return parts[idx + 1]
    elif query_upper.startswith("INSERT") and len(parts) >= 3:
        idx = next((i for i, p in enumerate(parts) if p.upper() == "INTO"), -1)
        if idx >= 0 and idx + 1 < len(parts):
            return parts[idx + 1].split("(")[0]
    return "unknown"


def extract_where_clause(query: str) -> str:
    idx = query.upper().find("WHERE")
    if idx >= 0:
        return query[idx:]
    return ""


def build_preview_select(query: str) -> str:
    query_upper = query.strip().upper()
    if query_upper.startswith("UPDATE"):
        table = extract_table_name(query)
        where = extract_where_clause(query)
        return f"SELECT * FROM {table} {where}" if where else f"SELECT * FROM {table} LIMIT 100"
    elif query_upper.startswith("DELETE"):
        table = extract_table_name(query)
        where = extract_where_clause(query)
        return f"SELECT * FROM {table} {where}" if where else f"SELECT * FROM {table} LIMIT 100"
    return ""


def get_change_number() -> int:
    if not os.path.exists(CHANGES_FILE):
        return 1
    with open(CHANGES_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    matches = re.findall(r"## Change #(\d+)", content)
    if matches:
        return max(int(m) for m in matches) + 1
    return 1


def log_change_to_file(change_entry: str):
    if not os.path.exists(CHANGES_FILE):
        with open(CHANGES_FILE, "w", encoding="utf-8") as f:
            f.write("# Database Change Log\n\n")
    with open(CHANGES_FILE, "a", encoding="utf-8") as f:
        f.write(change_entry)


def fetch_all_schema() -> str:
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
        columns = run_sql(columns_query)
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
            pk_rows = run_sql(pk_query)
            if pk_rows and pk_rows != [None]:
                for row in pk_rows:
                    t = row.get("table_name")
                    c = row.get("column_name")
                    pks.setdefault(t, []).append(c)
        except Exception:
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
            fk_rows = run_sql(fk_query)
            if fk_rows and fk_rows != [None]:
                for row in fk_rows:
                    t = row.get("table_name")
                    fks.setdefault(t, []).append(row)
        except Exception:
            pass

        count_query = """
        SELECT relname as table_name, n_live_tup as row_count
        FROM pg_stat_user_tables
        WHERE schemaname = 'public'
        ORDER BY relname
        """
        row_counts = {}
        try:
            count_rows = run_sql(count_query)
            if count_rows and count_rows != [None]:
                for row in count_rows:
                    if row:
                        row_counts[row.get("table_name")] = row.get("row_count", "unknown")
        except Exception:
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


def fetch_table_schema(table_name: str) -> str:
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
        columns = run_sql(columns_query)
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
            pk_rows = run_sql(pk_query)
            if pk_rows and pk_rows != [None]:
                pk_cols = [r.get("column_name") for r in pk_rows if r]
        except Exception:
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
            fk_rows = run_sql(fk_query) or []
            if fk_rows == [None]:
                fk_rows = []
        except Exception:
            pass

        count_query = f"""
        SELECT n_live_tup as row_count
        FROM pg_stat_user_tables
        WHERE schemaname = 'public' AND relname = '{table_name}'
        """
        row_count = "unknown"
        try:
            count_rows = run_sql(count_query)
            if count_rows and count_rows != [None] and count_rows[0]:
                row_count = count_rows[0].get("row_count", "unknown")
        except Exception:
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
