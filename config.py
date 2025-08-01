import os
from pathlib import Path

from dotenv import load_dotenv

# Load ../.env when running locally ---------------------------------
DOTENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(DOTENV_PATH, override=False)

# -------------------------------------------------------------------
PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID")
LOCATION = os.getenv("GOOGLE_LOCATION", "us-central1")
GCS_BUCKET = os.getenv("GCS_BUCKET")
VERTEX_MODEL = os.getenv("VERTEX_MODEL_NAME", "gemini-2.5-pro")
TEMPERATURE = float(os.getenv("VERTEX_TEMPERATURE", "0"))
GOOGLE_KEY_FILE = os.getenv("GOOGLE_CERT_FILE")
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
KAFKA_CLIENT_ID = os.getenv("KAFKA_CLIENT_ID", "underwriting-agent")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "underwriting-requests")
CENTRAL_KYC_MONGO_DB_URL = os.getenv(
    "CENTRAL_KYC_MONGO_URI", "mongodb://localhost:27017/"
)
ALL_MIGHT_BASE_URL = os.getenv("ALL_MIGHT_BASE_URL", "")
BIZCON_AUTH_KEY = os.getenv("BIZCON_AUTH_KEY", "")
SOURCE_NAME = os.getenv("SOURCE_NAME", "wall_e_gst_details_ai_summary")

# Derived constants --------------------------------------------------
GS_URI_PREFIX = f"gs://{GCS_BUCKET}"
BING_SEARCH = os.getenv("BING_SEARCH", "https://www.bing.com/search={query}")
