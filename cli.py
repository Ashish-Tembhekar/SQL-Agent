import sys
import argparse
from backend.app.config import validate_config
from backend.app.agent import invoke_agent
from backend.app.schemas import get_transaction_state, supabase
from backend.app.tools import set_current_session, reset_retry

print("Connecting to Supabase...")
print("Connected successfully!")
print()

parser = argparse.ArgumentParser(description="SQL Querying AI Agent")
parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed agent thinking steps and tool calls")
parser.add_argument("-o", "--ollama", action="store_true", help="Use local Ollama instead of OpenAI-compatible endpoints")
args = parser.parse_args()

validate_config(use_ollama=args.ollama)

session_id = "cli"

print("=" * 60)
mode_label = " (Ollama Mode)" if args.ollama else ""
mode_label += " (Verbose Mode)" if args.verbose else ""
print("SQL Querying AI Agent Ready!" + mode_label)
print("Type your question, use commit/rollback for changes, or /bye to exit")
print("=" * 60)

while True:
    try:
        user_input = input("\nYou: ").strip()

        if not user_input:
            continue

        if user_input.lower() in ("/bye", "exit", "quit"):
            tx_state = get_transaction_state(session_id)
            if tx_state["is_active"] and tx_state["pending_statements"]:
                pending_count = len(tx_state["pending_statements"])
                print(f"\nAgent: WARNING — You have {pending_count} pending change(s) that have not been committed or rolled back.")
                print("Agent: Please use commit_transaction() to save changes or rollback_transaction() to discard them before leaving.")
                follow_up = input("\nYou: ").strip().lower()
                if follow_up in ("/bye", "exit", "quit", "leave"):
                    print(f"\nAgent: Auto-rolling back {pending_count} pending change(s).")
                    tx_state["pending_statements"].clear()
                    tx_state["is_active"] = False
                    print("Agent: Goodbye!")
                    break
                else:
                    set_current_session(session_id)
                    result = invoke_agent(session_id, follow_up, use_ollama=args.ollama)
                    print(f"\nAgent: {result}")
                    if not tx_state["is_active"] or not tx_state["pending_statements"]:
                        print("\nAgent: Goodbye!")
                        break
            else:
                print("Agent: Goodbye!")
                break

        set_current_session(session_id)
        reset_retry(session_id)

        result = invoke_agent(session_id, user_input, use_ollama=args.ollama)
        print(f"\nAgent: {result}")

    except KeyboardInterrupt:
        tx_state = get_transaction_state(session_id)
        if tx_state["is_active"] and tx_state["pending_statements"]:
            print(f"\n\nAgent: Auto-rolling back {len(tx_state['pending_statements'])} pending change(s).")
            tx_state["pending_statements"].clear()
            tx_state["is_active"] = False
        print("\n\nAgent: Goodbye!")
        break
    except Exception as e:
        print(f"\nError: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        print("Please try again.")
