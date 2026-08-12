# Agente de Voz Postoperatorio — Tech Sphere Challenge 2026

Agente de voz en español para seguimiento postoperatorio de pacientes colombianos.

> En desarrollo — se completa el informe final en la última fase del proyecto.

## Estado actual

- **Backend RAG** (FastAPI + ChromaDB + embeddings NVIDIA NIM): sube PDFs clínicos, los trocea, indexa y expone `/query` para recuperar fragmentos con su fuente. Ver `backend/`.
- **Consola de administración** (Streamlit): subir/listar/eliminar documentos y probar `/query` visualmente. Ver `console/`.
- **Interfaz de llamada** (HTML/CSS/JS servido por FastAPI en `/llamada`): embebe el SDK de ElevenLabs Conversational AI para que el paciente hable con el agente de voz. Ver `call-interface/`.
- Pendiente: webhook post-llamada (resumen + alerta) y conexión del Tool de ElevenLabs al RAG (se configura en el dashboard de ElevenLabs, no en este repo).

## Cómo levantar todo localmente

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows
pip install -r requirements.txt
cp .env.example .env          # completa NVIDIA_API_KEY (y ELEVENLABS_* cuando los tengas)

# Backend RAG + interfaz de llamada (sirve /health, /documents, /query, /llamada)
uvicorn backend.main:app --reload

# Consola de administración (en otra terminal)
streamlit run console/app.py
```

- API: http://localhost:8000
- Interfaz de llamada: http://localhost:8000/llamada
- Consola de administración: http://localhost:8501

## Variables de entorno

Ver `.env.example`. `NVIDIA_API_KEY` es obligatoria para arrancar el backend (falla rápido si falta). `ELEVENLABS_API_KEY` y `ELEVENLABS_AGENT_ID` se usan en bloques posteriores (webhook y widget de llamada) y son opcionales para correr el RAG.
