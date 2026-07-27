import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./packin.db")

# Backup providers, tried in this order if Claude fails/times out.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.6-27b")

HF_API_TOKEN = os.getenv("HF_API_TOKEN", "")
HF_VISION_MODEL = os.getenv("HF_VISION_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct")

EXTRACTION_PROVIDER_ORDER = os.getenv(
    "EXTRACTION_PROVIDER_ORDER", "gemini,groq,huggingface"
).split(",")

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*")

# Auth
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")  
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))  

BOOTSTRAP_ADMIN_USERNAME = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "admin")
BOOTSTRAP_ADMIN_PASSWORD = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Substitution/sanity guardrails
LARGE_DEDUCTION_PCT_THRESHOLD = 0.5  # flag if a single deduction removes >50% of current stock
