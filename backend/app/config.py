import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL")
OLLAMA_MODEL_ID = os.getenv("OLLAMA_MODEL_ID")

CHANGES_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "Changes.md")


def validate_config(use_ollama: bool = False):
    errors = []
    if not SUPABASE_URL or "YOUR_" in SUPABASE_URL:
        errors.append("SUPABASE_URL not configured")
    if not SUPABASE_KEY or "YOUR_" in SUPABASE_KEY:
        errors.append("SUPABASE_KEY not configured")
    if not use_ollama:
        if not OPENAI_BASE_URL or "YOUR_" in OPENAI_BASE_URL:
            errors.append("OPENAI_BASE_URL not configured")
        if not OPENAI_API_KEY or "YOUR_" in OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY not configured")
        if not OPENAI_MODEL or "YOUR_" in OPENAI_MODEL:
            errors.append("OPENAI_MODEL not configured")
    else:
        if not OLLAMA_MODEL_ID or "YOUR_" in OLLAMA_MODEL_ID:
            errors.append("OLLAMA_MODEL_ID not configured")
    if errors:
        raise ValueError("; ".join(errors))
