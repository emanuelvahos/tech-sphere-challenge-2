from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend import config, rag, webhook
from backend.models import (
    DocumentoInfo,
    DocumentoRespuesta,
    EliminarRespuesta,
    PreguntaRequest,
    QueryRespuesta,
)

CALL_INTERFACE_DIR = Path(__file__).resolve().parent.parent / "call-interface"

app = FastAPI(
    title="Agente de Voz Postoperatorio - RAG API",
    description="Backend RAG para seguimiento postoperatorio (Tech Sphere Challenge 2026)",
    version="0.1.0",
)

app.mount(
    "/llamada/static",
    StaticFiles(directory=CALL_INTERFACE_DIR / "static"),
    name="llamada_static",
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/llamada", response_class=HTMLResponse)
def interfaz_llamada():
    """Interfaz pública de llamada (embebe el widget/SDK de ElevenLabs Conversational AI)."""
    html = (CALL_INTERFACE_DIR / "index.html").read_text(encoding="utf-8")
    html = html.replace("{{AGENT_ID}}", config.ELEVENLABS_AGENT_ID)
    return HTMLResponse(html)


@app.post("/documents", response_model=DocumentoRespuesta)
async def subir_documento(file: UploadFile = File(...)):
    if file.content_type != "application/pdf" and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se admiten archivos PDF.")

    contenido = await file.read()
    if not contenido:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")

    resultado = rag.procesar_documento(file.filename, contenido)

    if resultado["status"] == "sin_texto_extraible":
        raise HTTPException(
            status_code=400,
            detail="No se pudo extraer texto del PDF (¿es un escaneo sin OCR?).",
        )

    return resultado


@app.get("/documents", response_model=list[DocumentoInfo])
def listar_documentos():
    return rag.listar_documentos()


@app.delete("/documents/{doc_id}", response_model=EliminarRespuesta)
def eliminar_documento(doc_id: str):
    eliminado = rag.eliminar_documento(doc_id)
    if not eliminado:
        raise HTTPException(status_code=404, detail="doc_id no encontrado.")
    return {"doc_id": doc_id, "status": "eliminado"}


@app.post("/query", response_model=QueryRespuesta)
def query(body: PreguntaRequest):
    if not body.pregunta.strip():
        raise HTTPException(status_code=400, detail="La pregunta no puede estar vacía.")
    return rag.buscar(body.pregunta)


@app.post("/webhook/post-call")
async def webhook_post_call(
    request: Request,
    background_tasks: BackgroundTasks,
    elevenlabs_signature: str | None = Header(default=None, alias="elevenlabs-signature"),
):
    raw_body = await request.body()

    if not webhook.verificar_firma(raw_body, elevenlabs_signature):
        raise HTTPException(status_code=401, detail="Firma de webhook inválida.")

    payload = await request.json()
    background_tasks.add_task(webhook.procesar_llamada, payload)

    return JSONResponse({"status": "recibido"})


@app.get("/llamadas")
def listar_llamadas():
    return webhook.listar_resumenes()
