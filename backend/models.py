from typing import List

from pydantic import BaseModel


class DocumentoRespuesta(BaseModel):
    doc_id: str
    filename: str
    num_chunks: int
    status: str


class DocumentoInfo(BaseModel):
    doc_id: str
    filename: str
    num_chunks: int
    fecha_carga: str
    status: str


class EliminarRespuesta(BaseModel):
    doc_id: str
    status: str


class PreguntaRequest(BaseModel):
    pregunta: str


class Fragmento(BaseModel):
    texto: str
    fuente: str
    score: float


class QueryRespuesta(BaseModel):
    respuesta_fragmentos: List[Fragmento]
    hay_evidencia: bool
