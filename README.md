# Agente de Voz para Seguimiento Postoperatorio

Agente conversacional de voz en español que llama a pacientes colombianos post-cirugía, recoge síntomas usando lenguaje coloquial, consulta una base de conocimiento clínica (RAG con evidencia real) y clasifica cada llamada en 🟢 verde / 🟡 amarillo / 🔴 rojo. El equipo médico revisa los resúmenes estructurados en una consola web.

**Tech Sphere Challenge 2026 — Emanuel Vahos**

---

## Arquitectura

```
ElevenLabs Conversational AI   (agente de voz, vive en el dashboard de ElevenLabs)
        │  llama al Tool RAG          │  webhook post-llamada
        ▼                             ▼
┌─────────────────────────────────────────────┐
│              FastAPI  (backend/)            │
│  POST /documents  · GET /documents          │  ← gestión RAG
│  DELETE /documents/{id}  · POST /query      │
│  POST /webhook/post-call                    │  ← clasificación + resumen LLM
│  GET /llamadas  · GET /llamada (HTML)       │
└───────────┬──────────────────┬──────────────┘
            │                  │
     ChromaDB (chroma_db/)   SQLite (llamadas.db)
            │
   NVIDIA NIM API  ──  embeddings (nvidia/nv-embedqa-e5-v5)
                    ──  resumen LLM (meta/llama-3.1-8b-instruct)

Streamlit (console/app.py)  →  consume la API REST del backend
```

La interfaz de llamada (`/llamada`) es HTML estático servido por el propio FastAPI; no es una app separada.

📐 **Diagramas detallados (se renderizan en GitHub):**
- [Diagrama de arquitectura completo](./docs/diagrama-arquitectura.md)
- [Flujo de decisión verde/amarillo/rojo](./docs/diagrama-flujo-decision.md)

---

## Requisitos previos

| Requisito | Versión mínima |
|---|---|
| Python | **3.11.x** (ChromaDB no compila en 3.12+ sin Visual C++) |
| Cuenta NVIDIA NIM | gratuita — [build.nvidia.com](https://build.nvidia.com) |
| Cuenta ElevenLabs | gratuita — [elevenlabs.io](https://elevenlabs.io) |

> **Sobre Python 3.12/3.13 en Windows:** `chroma-hnswlib==0.7.6` no trae wheel precompilado para 3.12+. Si no tienes Python 3.11, instálalo desde [python.org](https://www.python.org/downloads/release/python-3119/) antes de continuar.

---

## Setup en 15 minutos

### 1. Clonar y entrar al directorio

```bash
git clone https://github.com/emanuelvahos/tech-sphere-challenge-2.git
cd tech-sphere-challenge-2
```

### 2. Crear entorno virtual e instalar dependencias

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

> El `requirements.txt` está anclado a versiones exactas; la instalación no tiene conflictos.

### 3. Configurar variables de entorno

```bash
cp .env.example .env
```

Abre `.env` y completa los valores (ver tabla más abajo):

```env
NVIDIA_API_KEY=nvapi-xxxxxxxxxxxxxxxxxxxxxxxxxxxx
ELEVENLABS_API_KEY=sk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ELEVENLABS_AGENT_ID=agent_xxxxxxxxxxxxxxxxxxxxxxxx
ELEVENLABS_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxxxxxxxxxxxxx
```

### 4. Levantar el backend

```bash
uvicorn backend.main:app --reload --port 8000
```

Verifica que responde:

```bash
curl http://localhost:8000/health
# → {"status":"ok"}
```

> **Windows (acentos/caracteres especiales):** si ves texto corrupto en la consola, agrega `PYTHONUTF8=1` antes del comando:
> ```powershell
> $env:PYTHONUTF8=1; uvicorn backend.main:app --reload
> ```

### 5. Levantar la consola de administración (en otra terminal)

```bash
# activa el mismo .venv si no está activo
streamlit run console/app.py
```

Se abre en `http://localhost:8501`.

---

## Cómo obtener cada API key

### NVIDIA NIM (`NVIDIA_API_KEY`)

1. Crea cuenta en [build.nvidia.com](https://build.nvidia.com).
2. Menú superior → **API Keys** → **Generate API Key**.
3. Copia el valor; empieza con `nvapi-`.

El mismo key sirve para embeddings (`nvidia/nv-embedqa-e5-v5`) **y** para el LLM de resumen (`meta/llama-3.1-8b-instruct`): ambos modelos se consumen vía el endpoint OpenAI-compatible de NIM (`https://integrate.api.nvidia.com/v1`).

### ElevenLabs (`ELEVENLABS_API_KEY`, `ELEVENLABS_AGENT_ID`, `ELEVENLABS_WEBHOOK_SECRET`)

1. Crea cuenta en [elevenlabs.io](https://elevenlabs.io).
2. **API Key** → perfil (esquina inferior izquierda) → **API Keys** → copia la key (`sk_…`).
3. **Agent ID** → en el dashboard, abre el agente postoperatorio; el ID aparece en la URL o en la sección **Overview** del agente (`agent_…`).
4. **Webhook Secret** → agente → pestaña **Analysis** → sección **Webhooks** → copia el signing secret (`whsec_…`).

> `ELEVENLABS_API_KEY` no es exigida al arrancar (no se usa activamente en el código actual), pero está reservada. Sin `ELEVENLABS_AGENT_ID` la interfaz de llamada muestra estado "no configurado". Sin `ELEVENLABS_WEBHOOK_SECRET` el endpoint `/webhook/post-call` rechaza toda petición con 401.

---

## Variables de entorno

| Variable | Obligatoria | Para qué sirve | Dónde conseguirla |
|---|---|---|---|
| `NVIDIA_API_KEY` | ✅ Sí | Embeddings RAG + LLM de resumen (NIM) | [build.nvidia.com](https://build.nvidia.com) → API Keys |
| `ELEVENLABS_AGENT_ID` | ✅ Sí | ID del agente inyectado en la interfaz `/llamada` | Dashboard ElevenLabs → agente → Overview |
| `ELEVENLABS_WEBHOOK_SECRET` | ✅ Sí | Verifica la firma HMAC-SHA256 del webhook post-llamada | Dashboard → agente → Analysis → Webhooks |
| `ELEVENLABS_API_KEY` | ⚠️ Recomendada | Reservada; no bloquea el arranque | Dashboard ElevenLabs → API Keys |

Variables opcionales con valor por defecto:

| Variable | Default | Descripción |
|---|---|---|
| `EMBEDDING_MODEL` | `nvidia/nv-embedqa-e5-v5` | Modelo de embeddings |
| `SUMMARY_LLM_MODEL` | `meta/llama-3.1-8b-instruct` | LLM de resumen clínico |
| `CHROMA_DIR` | `./chroma_db` | Directorio de persistencia de ChromaDB |
| `TOP_K` | `5` | Fragmentos recuperados por consulta RAG |
| `LLAMADAS_DB_PATH` | `./llamadas.db` | Base SQLite de llamadas |

---

## Superficies del sistema

### Interfaz de llamada (paciente)

```
http://localhost:8000/llamada
```

Página HTML servida por FastAPI. Embebe el SDK de ElevenLabs (`@elevenlabs/client@0.8.1` vía CDN `esm.sh`). El paciente toca el botón, el navegador pide permiso de micrófono y la llamada conecta directamente con el agente en ElevenLabs.

### Consola de administración (equipo médico)

```
http://localhost:8501
```

Interfaz Streamlit con cuatro secciones:

1. **Subir documento** — carga PDFs clínicos a ChromaDB (RAG en caliente).
2. **Documentos cargados** — lista con opción de eliminar (olvido en caliente).
3. **Prueba de consulta** — busca en el RAG y muestra fuente + score de relevancia (trazabilidad).
4. **Historial de llamadas** — todas las llamadas procesadas con clasificación 🟢/🟡/🔴, resumen narrativo, síntomas y duración.

### API REST (documentación interactiva)

```
http://localhost:8000/docs
```

---

## Modelos utilizados

| Modelo | Proveedor | Uso |
|---|---|---|
| `nvidia/nv-embedqa-e5-v5` | NVIDIA NIM | Genera embeddings de documentos (input_type `passage`) y de consultas (input_type `query`) para el sistema RAG |
| `meta/llama-3.1-8b-instruct` | NVIDIA NIM | Genera el resumen clínico estructurado JSON tras cada llamada. Mismo endpoint y API key que los embeddings |
| ElevenLabs Conversational AI | ElevenLabs | Agente de voz conversacional en español; gestiona turn-taking, STT, TTS y llama al Tool RAG configurado en el dashboard |

> La clasificación 🟢/🟡/🔴 **no depende del LLM**: se aplican reglas deterministas con regex sobre la transcripción del paciente (ver `backend/webhook.py` → `PATRONES_ROJO` / `PATRONES_AMARILLO`), de modo que ninguna alucinación del modelo puede modificar una alerta de severidad.

---

## Configuración del agente ElevenLabs

El agente ya está creado y funcionando. Si el jurado necesita verificar la configuración o recrearla desde cero:

1. **Crear agente** en [elevenlabs.io/app/conversational-ai](https://elevenlabs.io/app/conversational-ai) → **+ New Agent**.
2. **System Prompt** — instrucciones en español colombiano: saludo cálido, preguntar por dolor (escala 1-10), fiebre, herida, movilidad, apetito y sueño, lenguaje coloquial.
3. **Voz** — seleccionar voz en español latinoamericano.
4. **Tool RAG** — agregar un tool de tipo **Webhook / HTTP**:
   ```
   POST https://<tu-backend>/query
   Body: {"pregunta": "{{user_message}}"}
   ```
5. **Webhook post-llamada** → pestaña **Analysis** → **Webhooks** → URL:
   ```
   POST https://<tu-backend>/webhook/post-call
   ```
   Copiar el **signing secret** generado y pegarlo en `ELEVENLABS_WEBHOOK_SECRET`.
6. Copiar el **Agent ID** y pegarlo en `ELEVENLABS_AGENT_ID` del `.env`.

---

## Smoke test: verificar que todo funciona

Desde la **consola** (`http://localhost:8501`):

1. Sección **Subir documento** → sube un PDF clínico (hay PDFs de ejemplo en `dataset/`).
2. El sistema muestra: `✅ procesado y disponible — N chunks generados`.
3. Sección **Prueba de consulta** → escribe: `señales de alarma tras una cirugía`
4. Debes ver fragmentos con fuente y score > 0.5.

Desde la **terminal** (alternativa con curl):

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d "{\"pregunta\": \"señales de alarma postoperatorio\"}"
```

Respuesta esperada:

```json
{
  "respuesta_fragmentos": [
    {"texto": "...", "fuente": "nombre_documento.pdf", "score": 0.72}
  ],
  "hay_evidencia": true
}
```

---

## Deploy en Render (free tier)

> **Limitación crítica del free tier:** Render no persiste el sistema de archivos entre reinicios. `chroma_db/` y `llamadas.db` **se borran con cada deploy o reinicio del servicio**. Después de cada reinicio hay que re-subir los documentos clínicos desde la consola.

> **Cold start:** Los servicios gratuitos de Render se duermen tras 15 minutos de inactividad. La primera petición puede tardar 30-60 segundos en despertar. Para una demo, haz un ping de calentamiento antes:
> ```bash
> curl https://<tu-app>.onrender.com/health
> ```

El archivo `runtime.txt` en la raíz del repo fija `python-3.11.9` explícitamente porque Render usaba Python 3.14 por defecto, lo que rompía la compilación de `chroma-hnswlib` (no hay wheel precompilado para esa versión).

---

## Estructura del repositorio

```
.
├── backend/
│   ├── config.py        # Variables de entorno y configuración centralizada
│   ├── main.py          # App FastAPI: rutas, montaje de archivos estáticos
│   ├── rag.py           # Lógica RAG: extracción PDF, chunking, embeddings, ChromaDB
│   ├── webhook.py       # Clasificación de severidad, resumen LLM, persistencia SQLite
│   └── models.py        # Modelos Pydantic de request/response
├── call-interface/
│   ├── index.html       # Interfaz de llamada (AGENT_ID inyectado en servidor)
│   └── static/
│       ├── app.js       # SDK ElevenLabs, máquina de estados de la llamada
│       └── style.css    # Estilos de la interfaz de llamada
├── console/
│   └── app.py           # Consola Streamlit de administración
├── dataset/             # PDFs clínicos de ejemplo para cargar al RAG
├── .env.example         # Plantilla de variables de entorno
├── requirements.txt     # Dependencias exactas (pip freeze)
├── runtime.txt          # Fija Python 3.11.9 para Render
└── LICENSE              # MIT — Emanuel Vahos 2026
```

---

## Licencia

MIT — ver [LICENSE](./LICENSE).
