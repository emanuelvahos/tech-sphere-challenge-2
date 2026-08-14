# Diagrama de Arquitectura — Agente de Voz Postoperatorio

```mermaid
flowchart TD
    %% ─────────────────────────────────────────
    %% SUPERFICIES DE USUARIO
    %% ─────────────────────────────────────────
    subgraph UI["🖥️ Superficies de usuario"]
        ADMIN["👨‍⚕️ Administrador\n(equipo médico)"]
        PACIENTE["🧑 Paciente\n(voz en español)"]
        CONSOLA["Consola de administración\nStreamlit · localhost:8501"]
        INTERFAZ["Interfaz de llamada\nGET /llamada · localhost:8000/llamada\n(HTML/JS servido por FastAPI)"]
    end

    %% ─────────────────────────────────────────
    %% PLATAFORMA ELEVENLABS (EXTERNA)
    %% ─────────────────────────────────────────
    subgraph EL["☁️ Plataforma ElevenLabs (externa)"]
        AGENT["Agente Conversacional\nElevenLabs Conversational AI\nSTT · LLM conversacional · TTS\n(system prompt + voz en español)"]
    end

    %% ─────────────────────────────────────────
    %% NUESTRO BACKEND EN RENDER
    %% ─────────────────────────────────────────
    subgraph BACKEND["🚀 Backend FastAPI · Render (Python 3.11)"]
        RAG["RAG\nPOST /documents\nGET /documents\nDELETE /documents · POST /query\nExtracción PDF · chunking · embeddings · ChromaDB"]
        WEBHOOK["Procesador post-llamada\nPOST /webhook/post-call\nVerificación HMAC-SHA256\nClasificación de severidad (regex)\nGeneración de resumen (LLM)"]
        HISTORIAL["GET /llamadas\nHistorial de llamadas"]
        CHROMA[("ChromaDB\nchroma_db/\nBase vectorial local")]
        SQLITE[("SQLite\nllamadas.db\nHistorial de llamadas")]
    end

    %% ─────────────────────────────────────────
    %% SERVICIOS EXTERNOS (NVIDIA NIM)
    %% ─────────────────────────────────────────
    subgraph NIM["🔌 NVIDIA NIM API (externa)"]
        EMBED["Embeddings\nnvidia/nv-embedqa-e5-v5"]
        LLM["LLM de resumen clínico\nmeta/llama-3.1-8b-instruct\n(mismo endpoint · misma API key)"]
    end

    %% ─────────────────────────────────────────
    %% FLUJOS
    %% ─────────────────────────────────────────

    %% Administrador usa consola
    ADMIN -->|"sube / elimina PDFs"| CONSOLA
    CONSOLA -->|"POST /documents\nDELETE /documents/{id}\nGET /documents\nPOST /query"| RAG
    CONSOLA -->|"GET /llamadas"| HISTORIAL

    %% RAG ↔ ChromaDB ↔ NVIDIA embeddings
    RAG -->|"genera embeddings"| EMBED
    EMBED -->|"vectores float"| RAG
    RAG <-->|"indexa / busca"| CHROMA

    %% Paciente → Interfaz → ElevenLabs
    PACIENTE -->|"voz"| INTERFAZ
    INTERFAZ -->|"SDK @elevenlabs/client\nWebRTC"| AGENT

    %% ElevenLabs Tool RAG — EN VIVO durante la llamada
    AGENT -->|"🔴 EN VIVO durante la llamada\nTool webhook: POST /query\n(pregunta del paciente)"| RAG
    RAG -->|"fragmentos + fuente + score"| AGENT

    %% ElevenLabs → Paciente (TTS)
    AGENT -->|"voz sintetizada"| INTERFAZ
    INTERFAZ -->|"audio"| PACIENTE

    %% Webhook post-llamada — DESPUÉS de terminar
    AGENT -->|"⬛ DESPUÉS de colgar\nPOST /webhook/post-call\n(transcripción completa + firma HMAC)"| WEBHOOK

    %% Procesamiento post-llamada
    WEBHOOK -->|"genera resumen clínico JSON"| LLM
    LLM -->|"resumen estructurado"| WEBHOOK
    WEBHOOK -->|"persiste resumen + clasificación"| SQLITE

    %% Historial
    HISTORIAL -->|"lee"| SQLITE
    HISTORIAL -->|"JSON historial"| CONSOLA

    %% ─────────────────────────────────────────
    %% ESTILOS
    %% ─────────────────────────────────────────
    classDef external fill:#dbeafe,stroke:#3b82f6,color:#1e3a5f
    classDef backend fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef db fill:#fef9c3,stroke:#ca8a04,color:#713f12
    classDef ui fill:#f3e8ff,stroke:#9333ea,color:#3b0764
    classDef patient fill:#ffedd5,stroke:#ea580c,color:#7c2d12

    class AGENT,EMBED,LLM external
    class RAG,WEBHOOK,HISTORIAL backend
    class CHROMA,SQLITE db
    class CONSOLA,INTERFAZ ui
    class ADMIN,PACIENTE patient
```

> **Nota de despliegue:** `chroma_db/` y `llamadas.db` son locales al contenedor de Render.
> En el free tier **no persisten entre reinicios** — hay que re-subir los documentos tras cada arranque en frío.
> El agente ElevenLabs (system prompt, voz, Tool RAG, webhook) vive en el dashboard de ElevenLabs y no está en este repositorio como código.
