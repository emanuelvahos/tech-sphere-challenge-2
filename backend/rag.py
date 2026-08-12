import uuid
from datetime import datetime, timezone
from typing import List

import chromadb
import httpx
from pypdf import PdfReader

from backend import config

_http_client = httpx.Client(
    base_url=config.NVIDIA_EMBEDDINGS_BASE_URL,
    headers={
        "Authorization": f"Bearer {config.NVIDIA_API_KEY}",
        "Accept": "application/json",
    },
    timeout=60.0,
)

_chroma_client = chromadb.PersistentClient(path=config.CHROMA_DIR)
_collection = _chroma_client.get_or_create_collection(
    name=config.CHROMA_COLLECTION,
    metadata={"hnsw:space": "cosine"},
)


def extraer_texto_pdf(contenido: bytes) -> str:
    reader = PdfReader(__import__("io").BytesIO(contenido))
    paginas = [pagina.extract_text() or "" for pagina in reader.pages]
    return "\n\n".join(paginas)


def trocear_texto(
    texto: str,
    chunk_size: int = config.CHUNK_SIZE_CHARS,
    overlap: int = config.CHUNK_OVERLAP_CHARS,
) -> List[str]:
    parrafos = [p.strip() for p in texto.split("\n\n") if p.strip()]
    if not parrafos:
        return []

    chunks: List[str] = []
    actual = ""
    for parrafo in parrafos:
        candidato = f"{actual}\n\n{parrafo}".strip() if actual else parrafo
        if len(candidato) <= chunk_size:
            actual = candidato
            continue

        if actual:
            chunks.append(actual)
            cola = actual[-overlap:] if overlap > 0 else ""
            actual = f"{cola}\n\n{parrafo}".strip()
        else:
            actual = parrafo

        while len(actual) > chunk_size:
            chunks.append(actual[:chunk_size])
            actual = actual[chunk_size - overlap:]

    if actual:
        chunks.append(actual)

    return chunks


def generar_embeddings(textos: List[str], input_type: str) -> List[List[float]]:
    """input_type: "passage" al indexar documentos, "query" al buscar (requerido por bge-m3 en NIM)."""
    if not textos:
        return []

    respuesta = _http_client.post(
        "/embeddings",
        json={
            "input": textos,
            "model": config.EMBEDDING_MODEL,
            "input_type": input_type,
            "encoding_format": "float",
            "truncate": "END",
        },
    )
    respuesta.raise_for_status()
    datos = respuesta.json()["data"]
    datos.sort(key=lambda d: d["index"])
    return [d["embedding"] for d in datos]


def procesar_documento(filename: str, contenido: bytes) -> dict:
    texto = extraer_texto_pdf(contenido)
    chunks = trocear_texto(texto)

    if not chunks:
        return {"doc_id": None, "filename": filename, "num_chunks": 0, "status": "sin_texto_extraible"}

    doc_id = str(uuid.uuid4())
    fecha_carga = datetime.now(timezone.utc).isoformat()

    embeddings = generar_embeddings(chunks, input_type="passage")

    ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "source_filename": filename,
            "doc_id": doc_id,
            "chunk_index": i,
            "fecha_carga": fecha_carga,
        }
        for i in range(len(chunks))
    ]

    _collection.add(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)

    return {
        "doc_id": doc_id,
        "filename": filename,
        "num_chunks": len(chunks),
        "status": "procesado y disponible",
    }


def listar_documentos() -> List[dict]:
    resultado = _collection.get(include=["metadatas"])
    metadatas = resultado.get("metadatas") or []

    docs: dict = {}
    for meta in metadatas:
        doc_id = meta["doc_id"]
        if doc_id not in docs:
            docs[doc_id] = {
                "doc_id": doc_id,
                "filename": meta["source_filename"],
                "num_chunks": 0,
                "fecha_carga": meta["fecha_carga"],
                "status": "procesado y disponible",
            }
        docs[doc_id]["num_chunks"] += 1

    return list(docs.values())


def eliminar_documento(doc_id: str) -> bool:
    existentes = _collection.get(where={"doc_id": doc_id}, include=[])
    ids = existentes.get("ids") or []
    if not ids:
        return False
    _collection.delete(ids=ids)
    return True


def buscar(pregunta: str, top_k: int = config.TOP_K) -> dict:
    embedding_pregunta = generar_embeddings([pregunta], input_type="query")[0]

    resultado = _collection.query(
        query_embeddings=[embedding_pregunta],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    documentos = resultado.get("documents", [[]])[0]
    metadatas = resultado.get("metadatas", [[]])[0]
    distancias = resultado.get("distances", [[]])[0]

    fragmentos = []
    for texto, meta, distancia in zip(documentos, metadatas, distancias):
        score = 1 - distancia
        fragmentos.append(
            {
                "texto": texto,
                "fuente": meta["source_filename"],
                "score": round(max(score, 0.0), 4),
            }
        )

    max_score = max((f["score"] for f in fragmentos), default=0.0)
    hay_evidencia = max_score >= config.EVIDENCIA_MIN_SCORE

    if not hay_evidencia:
        fragmentos = []

    return {"respuesta_fragmentos": fragmentos, "hay_evidencia": hay_evidencia}
