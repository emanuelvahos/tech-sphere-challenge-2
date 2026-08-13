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

# Secret HMAC configurado en el dashboard de ElevenLabs para el webhook
# post-llamada (Settings > Webhooks). Debe coincidir exacto con lo que se
# pega ahi. Sin ella, el webhook rechaza toda peticion con 401.
ELEVENLABS_WEBHOOK_SECRET = os.getenv("ELEVENLABS_WEBHOOK_SECRET", "").strip()

# Tolerancia de antiguedad del timestamp de la firma, para evitar ataques de
# replay con una firma valida pero vieja.
WEBHOOK_SIGNATURE_TOLERANCE_SECONDS = int(os.getenv("WEBHOOK_SIGNATURE_TOLERANCE_SECONDS", "1800"))

# LLM para el resumen clinico post-llamada. Reutiliza NVIDIA NIM (mismo
# NVIDIA_API_KEY que ya usamos para embeddings) en vez de pedir una key
# nueva: NIM tambien sirve modelos de chat via /chat/completions con el
# mismo formato OpenAI-compatible.
SUMMARY_LLM_MODEL = os.getenv("SUMMARY_LLM_MODEL", "meta/llama-3.1-8b-instruct")

LLAMADAS_DB_PATH = os.getenv("LLAMADAS_DB_PATH", "./llamadas.db")
