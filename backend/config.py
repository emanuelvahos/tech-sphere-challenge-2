import os
import sys

from dotenv import load_dotenv

load_dotenv()

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "").strip()

if not NVIDIA_API_KEY:
    print(
        "ERROR: falta NVIDIA_API_KEY. Copia .env.example a .env y coloca tu API key de NVIDIA NIM.",
        file=sys.stderr,
    )
    raise SystemExit(1)

NVIDIA_EMBEDDINGS_BASE_URL = os.getenv("NVIDIA_EMBEDDINGS_BASE_URL", "https://integrate.api.nvidia.com/v1")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nvidia/nv-embedqa-e5-v5")
CHROMA_DIR = os.getenv("CHROMA_DIR", "./chroma_db")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "documentos_postoperatorio")

CHUNK_SIZE_CHARS = int(os.getenv("CHUNK_SIZE_CHARS", "2800"))
CHUNK_OVERLAP_CHARS = int(os.getenv("CHUNK_OVERLAP_CHARS", "400"))

TOP_K = int(os.getenv("TOP_K", "5"))
EVIDENCIA_MIN_SCORE = float(os.getenv("EVIDENCIA_MIN_SCORE", "0.5"))

# No se exige al arrancar: se necesitan para el bloque del webhook post-llamada
# (verificar firma) y para la interfaz de llamada (agent-id del widget), pero
# el backend RAG debe poder correr sin ellas todavia.
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()
ELEVENLABS_AGENT_ID = os.getenv("ELEVENLABS_AGENT_ID", "").strip()
