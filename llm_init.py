import config
from google.oauth2 import service_account
from langchain_google_vertexai import ChatVertexAI

_creds = None
if config.GOOGLE_KEY_FILE:
    _creds = service_account.Credentials.from_service_account_file(
        config.GOOGLE_KEY_FILE,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )

chat_vertex_ai_llm = ChatVertexAI(
    model_name=config.VERTEX_MODEL,
    temperature=config.TEMPERATURE,
    project=config.PROJECT_ID,
    location=config.LOCATION,
    credentials=_creds,
)

__all__ = ["chat_vertex_ai_llm"]
