import os

import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Consola RAG - Seguimiento Postoperatorio", layout="wide")
st.title("Consola de administración — Base de conocimiento RAG")
st.caption(f"Backend: {API_BASE_URL}")


def backend_get(path: str):
    try:
        r = requests.get(f"{API_BASE_URL}{path}", timeout=15)
        r.raise_for_status()
        return r.json(), None
    except requests.exceptions.ConnectionError:
        return None, f"No se pudo conectar al backend en {API_BASE_URL}. ¿Está corriendo `uvicorn backend.main:app`?"
    except requests.exceptions.HTTPError:
        return None, f"El backend respondió con error: {r.status_code} — {r.text}"
    except requests.exceptions.RequestException as e:
        return None, f"Error de red: {e}"


def backend_post(path: str, **kwargs):
    try:
        r = requests.post(f"{API_BASE_URL}{path}", timeout=60, **kwargs)
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail", r.text)
            except ValueError:
                detail = r.text
            return None, f"Error {r.status_code}: {detail}"
        return r.json(), None
    except requests.exceptions.ConnectionError:
        return None, f"No se pudo conectar al backend en {API_BASE_URL}. ¿Está corriendo `uvicorn backend.main:app`?"
    except requests.exceptions.RequestException as e:
        return None, f"Error de red: {e}"


def backend_delete(path: str):
    try:
        r = requests.delete(f"{API_BASE_URL}{path}", timeout=15)
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail", r.text)
            except ValueError:
                detail = r.text
            return None, f"Error {r.status_code}: {detail}"
        return r.json(), None
    except requests.exceptions.ConnectionError:
        return None, f"No se pudo conectar al backend en {API_BASE_URL}. ¿Está corriendo `uvicorn backend.main:app`?"
    except requests.exceptions.RequestException as e:
        return None, f"Error de red: {e}"


if "confirmar_borrado" not in st.session_state:
    st.session_state.confirmar_borrado = None


st.header("1. Subir documento")
archivo = st.file_uploader("Selecciona un PDF clínico", type=["pdf"])
if st.button("Subir y procesar", disabled=archivo is None):
    with st.spinner("Extrayendo texto, generando embeddings e indexando en ChromaDB..."):
        files = {"file": (archivo.name, archivo.getvalue(), "application/pdf")}
        resultado, error = backend_post("/documents", files=files)

    if error:
        st.error(error)
    else:
        st.success(
            f"✅ {resultado['status'].capitalize()} — **{resultado['filename']}** "
            f"({resultado['num_chunks']} chunks generados, doc_id `{resultado['doc_id']}`)"
        )

st.divider()

st.header("2. Documentos cargados")
col_a, col_b = st.columns([1, 5])
with col_a:
    refrescar = st.button("🔄 Refrescar")

if st.session_state.get("mensaje_flash"):
    st.success(st.session_state.mensaje_flash)
    st.session_state.mensaje_flash = None

documentos, error = backend_get("/documents")

if error:
    st.error(error)
elif not documentos:
    st.info("Aún no hay documentos cargados.")
else:
    for doc in documentos:
        c1, c2, c3, c4, c5 = st.columns([3, 2, 1, 2, 1])
        c1.write(doc["filename"])
        c2.write(doc["fecha_carga"])
        c3.write(doc["num_chunks"])
        c4.write(f"✅ {doc['status']}")

        if st.session_state.confirmar_borrado == doc["doc_id"]:
            if c5.button("Confirmar", key=f"confirmar_{doc['doc_id']}"):
                _, del_error = backend_delete(f"/documents/{doc['doc_id']}")
                st.session_state.confirmar_borrado = None
                if del_error:
                    st.session_state.mensaje_flash = None
                    st.error(del_error)
                else:
                    st.session_state.mensaje_flash = "🗑️ Eliminado — el agente ya no tiene acceso a este documento"
                st.rerun()
        else:
            if c5.button("🗑️ Eliminar", key=f"borrar_{doc['doc_id']}"):
                st.session_state.confirmar_borrado = doc["doc_id"]
                st.rerun()

st.divider()

st.header("3. Prueba rápida de consulta (trazabilidad)")
pregunta = st.text_input("Pregunta del paciente")
if st.button("Consultar", disabled=not pregunta.strip()):
    with st.spinner("Buscando fragmentos relevantes..."):
        resultado, error = backend_post("/query", json={"pregunta": pregunta})

    if error:
        st.error(error)
    elif not resultado["hay_evidencia"]:
        st.warning("No se encontró evidencia suficiente en la base de conocimiento para esta pregunta.")
    else:
        st.success(f"{len(resultado['respuesta_fragmentos'])} fragmentos encontrados")
        for i, frag in enumerate(resultado["respuesta_fragmentos"], start=1):
            with st.expander(f"Fragmento {i} — fuente: {frag['fuente']} (score {frag['score']})"):
                st.write(frag["texto"])

st.divider()

st.header("4. Historial de llamadas")

COLOR_CLASIFICACION = {
    "verde": "🟢",
    "amarillo": "🟡",
    "rojo": "🔴",
}

if st.button("🔄 Refrescar historial"):
    st.rerun()

llamadas, error = backend_get("/llamadas")

if error:
    st.error(error)
elif not llamadas:
    st.info("Aún no hay llamadas registradas.")
else:
    for llamada in llamadas:
        emoji = COLOR_CLASIFICACION.get(llamada.get("clasificacion"), "⚪")
        fecha = llamada.get("fecha_llamada", "sin fecha")
        resumen = llamada.get("resumen_narrativo") or "(sin resumen)"
        titulo = f"{emoji} {llamada.get('clasificacion', 'desconocida').upper()} — {fecha}"

        with st.expander(titulo):
            st.markdown(f"**Resumen narrativo:** {resumen}")
            st.markdown(f"**Razón de clasificación:** {llamada.get('razon_clasificacion', '—')}")
            st.markdown(f"**Requiere atención humana:** {'Sí' if llamada.get('requiere_atencion_humana') else 'No'}")
            st.markdown(f"**Duración de la llamada:** {llamada.get('duracion_llamada_segundos', '—')} s")
            st.markdown(f"**Paciente:** {llamada.get('paciente_id') or 'no identificado'}")
            st.markdown(f"**Conversation ID:** `{llamada.get('conversation_id', '—')}`")

            sintomas = llamada.get("sintomas_reportados")
            if isinstance(sintomas, dict):
                st.markdown("**Síntomas reportados:**")
                for campo, valor in sintomas.items():
                    st.markdown(f"- **{campo.capitalize()}:** {valor}")
            else:
                st.warning(f"Síntomas: {sintomas}")
