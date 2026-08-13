# Agente de Voz Postoperatorio — Tech Sphere Challenge 2026

Agente de voz en español para seguimiento postoperatorio de pacientes colombianos.

> En desarrollo — se completa el informe final en la última fase del proyecto.

## Estado actual

- **Backend RAG** (FastAPI + ChromaDB + embeddings NVIDIA NIM): sube PDFs clínicos, los trocea, indexa y expone `/query` para recuperar fragmentos con su fuente. Ver `backend/`.
- **Consola de administración** (Streamlit): subir/listar/eliminar documentos, probar `/query` y ver el historial de llamadas con su clasificación de alerta. Ver `console/`.
- **Interfaz de llamada** (HTML/CSS/JS servido por FastAPI en `/llamada`): embebe el SDK de ElevenLabs Conversational AI para que el paciente hable con el agente de voz. Ver `call-interface/`.
- **Webhook post-llamada** (`POST /webhook/post-call`): recibe la transcripción al terminar la llamada, clasifica severidad (verde/amarillo/rojo) por reglas explícitas, genera un resumen clínico vía LLM y lo persiste. Ver `backend/webhook.py`.
- Pendiente: conexión del Tool de ElevenLabs al RAG (se configura en el dashboard de ElevenLabs, no en este repo) e informe final.

## Cómo levantar todo localmente

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows
pip install -r requirements.txt
cp .env.example .env          # completa NVIDIA_API_KEY (y ELEVENLABS_* cuando los tengas)

# Backend RAG + interfaz de llamada + webhook (sirve /health, /documents, /query, /llamada, /webhook/post-call, /llamadas)
uvicorn backend.main:app --reload

# Consola de administración (en otra terminal)
streamlit run console/app.py
```

- API: http://localhost:8000
- Interfaz de llamada: http://localhost:8000/llamada
- Consola de administración: http://localhost:8501

**Nota Windows**: si ves acentos/ñ corruptos en las respuestas (`sinal` en vez de `señal`), es un problema conocido de codepage de consola en Windows, no del código. Arranca con `PYTHONUTF8=1` antes del comando, ej. `set PYTHONUTF8=1 && uvicorn backend.main:app --reload` (cmd) o `$env:PYTHONUTF8=1; uvicorn backend.main:app --reload` (PowerShell). En Linux/Render no ocurre.

## Variables de entorno

Ver `.env.example`.

- `NVIDIA_API_KEY`: obligatoria, el backend falla rápido al arrancar si falta. Se usa para embeddings (RAG) y para el LLM del resumen post-llamada (mismo proveedor, NVIDIA NIM).
- `ELEVENLABS_AGENT_ID`: agent-id público para la interfaz de llamada (`/llamada`). Opcional para correr el resto.
- `ELEVENLABS_WEBHOOK_SECRET`: signing secret del webhook post-llamada configurado en el dashboard de ElevenLabs. Debe coincidir exacto con el que configures ahí — si no, `/webhook/post-call` responde 401 a todo.
- `ELEVENLABS_API_KEY`: reservada, no se usa activamente todavía.

## Webhook post-llamada

`POST /webhook/post-call` — recibe el payload `post_call_transcription` de ElevenLabs, verifica su firma HMAC-SHA256 (header `elevenlabs-signature`, formato `t=<timestamp>,v0=<hmac>`), y si es válida procesa en background: clasifica severidad por reglas explícitas (ver `PATRONES_ROJO`/`PATRONES_AMARILLO` en `backend/webhook.py`), genera un resumen clínico estructurado vía LLM, y lo guarda en `llamadas.db` (SQLite local, en `.gitignore`).

`GET /llamadas` — lista los resúmenes guardados, más reciente primero.
