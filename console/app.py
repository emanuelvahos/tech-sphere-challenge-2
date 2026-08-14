import os
from collections import Counter

import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# Misma familia tipografica que call-interface/static/style.css, para que la
# consola se sienta la misma aplicacion que la interfaz de llamada.
FONT_STACK = "-apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"

# Colores tomados directo de call-interface/static/style.css (:root). El
# resto de la paleta (fondo, texto, radios) vive en .streamlit/config.toml
# via el theming nativo de Streamlit.
DANGER = "#B33F32"
DANGER_SOFT = "#F5DCD6"
TEXT_MUTED = "#6E6459"

st.set_page_config(page_title="Consola RAG - Seguimiento Postoperatorio", layout="wide", page_icon="🩺")

st.markdown(
    f"""
    <style>
    html, body, [class*="css"], [data-testid="stAppViewContainer"] {{
        font-family: {FONT_STACK} !important;
    }}
    .doc-card-title {{
        font-size: 1.05rem;
        font-weight: 700;
        margin-bottom: 2px;
    }}
    .doc-card-meta {{
        font-size: 0.85rem;
        color: {TEXT_MUTED};
        margin-bottom: 10px;
    }}
    .section-lead {{
        color: {TEXT_MUTED};
        font-size: 0.95rem;
        margin-top: -10px;
    }}
    .confirm-danger {{
        background: {DANGER_SOFT};
        border: 1px solid {DANGER};
        border-radius: 1rem;
        padding: 14px 16px;
        margin-bottom: 10px;
    }}
    .confirm-danger p {{
        margin: 0;
        color: {DANGER};
        font-weight: 600;
    }}
    .sintoma-label {{
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: {TEXT_MUTED};
        margin-bottom: 2px;
    }}
    .sintoma-valor {{
        margin-bottom: 14px;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🩺 Consola de administración")
st.caption(f"Base de conocimiento y seguimiento postoperatorio · Backend: {API_BASE_URL}")


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
if "mensaje_flash" not in st.session_state:
    st.session_state.mensaje_flash = None


CLASIFICACION_UI = {
    "verde": {"color": "green", "icon": "🟢", "label": "VERDE — dentro de lo esperado"},
    "amarillo": {"color": "orange", "icon": "🟡", "label": "AMARILLO — requiere seguimiento"},
    "rojo": {"color": "red", "icon": "🔴", "label": "ROJO — requiere atención humana"},
}

SINTOMA_LABELS = {
    "dolor": "💊 Dolor",
    "fiebre": "🌡️ Fiebre",
    "herida": "🩹 Herida",
    "movilidad": "🚶 Movilidad",
    "apetito": "🍽️ Apetito",
    "sueno": "😴 Sueño",
}


tab_subir, tab_docs, tab_consulta, tab_historial = st.tabs(
    ["⬆️ Subir documento", "📚 Documentos", "🔍 Consulta rápida", "🩺 Historial de llamadas"]
)

# ---------------------------------------------------------------------------
# Tab 1: subir documento
# ---------------------------------------------------------------------------
with tab_subir:
    st.subheader("Subir documento clínico")
    st.markdown(
        '<p class="section-lead">PDFs de guías, protocolos o material de referencia que el agente usará como fuente.</p>',
        unsafe_allow_html=True,
    )
    archivo = st.file_uploader("Selecciona un PDF", type=["pdf"], label_visibility="collapsed")

    if st.button("Subir y procesar", type="primary", disabled=archivo is None):
        with st.spinner("Extrayendo texto, generando embeddings e indexando en ChromaDB…"):
            files = {"file": (archivo.name, archivo.getvalue(), "application/pdf")}
            resultado, error = backend_post("/documents", files=files)

        if error:
            st.error(error)
        else:
            st.badge("Procesado y disponible", icon="✅", color="green")
            st.markdown(f"**{resultado['filename']}** — {resultado['num_chunks']} chunks generados")
            st.caption(f"doc_id `{resultado['doc_id']}`")

# ---------------------------------------------------------------------------
# Tab 2: documentos cargados (listado + eliminar)
# ---------------------------------------------------------------------------
with tab_docs:
    col_titulo, col_refrescar = st.columns([5, 1])
    with col_titulo:
        st.subheader("Documentos cargados")
    with col_refrescar:
        if st.button("🔄 Refrescar", use_container_width=True):
            st.rerun()

    if st.session_state.mensaje_flash:
        st.success(st.session_state.mensaje_flash)
        st.session_state.mensaje_flash = None

    documentos, error = backend_get("/documents")

    if error:
        st.error(error)
    elif not documentos:
        st.info("Aún no hay documentos cargados. Sube uno en la pestaña anterior.")
    else:
        for doc in documentos:
            with st.container(border=True):
                col_info, col_accion = st.columns([5, 1])

                with col_info:
                    st.markdown(f'<div class="doc-card-title">{doc["filename"]}</div>', unsafe_allow_html=True)
                    st.markdown(
                        f'<div class="doc-card-meta">{doc["num_chunks"]} chunks · cargado {doc["fecha_carga"]}</div>',
                        unsafe_allow_html=True,
                    )
                    st.badge("Procesado y disponible", icon="✅", color="green")

                with col_accion:
                    if st.session_state.confirmar_borrado != doc["doc_id"]:
                        if st.button("🗑️ Eliminar", key=f"borrar_{doc['doc_id']}", use_container_width=True):
                            st.session_state.confirmar_borrado = doc["doc_id"]
                            st.rerun()

                if st.session_state.confirmar_borrado == doc["doc_id"]:
                    st.markdown(
                        f'<div class="confirm-danger"><p>⚠️ ¿Eliminar «{doc["filename"]}»? '
                        "El agente perderá acceso a este documento de inmediato.</p></div>",
                        unsafe_allow_html=True,
                    )
                    col_cancelar, col_confirmar = st.columns(2)
                    with col_cancelar:
                        if st.button("Cancelar", key=f"cancelar_{doc['doc_id']}", use_container_width=True):
                            st.session_state.confirmar_borrado = None
                            st.rerun()
                    with col_confirmar:
                        if st.button(
                            "Sí, eliminar",
                            key=f"confirmar_{doc['doc_id']}",
                            type="primary",
                            use_container_width=True,
                        ):
                            _, del_error = backend_delete(f"/documents/{doc['doc_id']}")
                            st.session_state.confirmar_borrado = None
                            if del_error:
                                st.session_state.mensaje_flash = None
                                st.error(del_error)
                            else:
                                st.session_state.mensaje_flash = (
                                    "🗑️ Eliminado — el agente ya no tiene acceso a este documento"
                                )
                            st.rerun()

# ---------------------------------------------------------------------------
# Tab 3: consulta rápida (trazabilidad)
# ---------------------------------------------------------------------------
with tab_consulta:
    st.subheader("Prueba rápida de consulta")
    st.markdown(
        '<p class="section-lead">Verifica qué fragmentos y fuentes devuelve el RAG para una pregunta, sin pasar por voz.</p>',
        unsafe_allow_html=True,
    )
    pregunta = st.text_input("Pregunta del paciente", label_visibility="collapsed", placeholder="Escribe una pregunta…")

    if st.button("Consultar", type="primary", disabled=not pregunta.strip()):
        with st.spinner("Buscando fragmentos relevantes…"):
            resultado, error = backend_post("/query", json={"pregunta": pregunta})

        if error:
            st.error(error)
        elif not resultado["hay_evidencia"]:
            st.badge("Sin evidencia suficiente", icon="⚠️", color="orange")
        else:
            st.badge(f"{len(resultado['respuesta_fragmentos'])} fragmentos encontrados", icon="✅", color="green")
            for i, frag in enumerate(resultado["respuesta_fragmentos"], start=1):
                with st.expander(f"Fragmento {i} — fuente: {frag['fuente']} (score {frag['score']})"):
                    st.write(frag["texto"])

# ---------------------------------------------------------------------------
# Tab 4: historial de llamadas
# ---------------------------------------------------------------------------
with tab_historial:
    col_titulo, col_refrescar = st.columns([5, 1])
    with col_titulo:
        st.subheader("Historial de llamadas")
    with col_refrescar:
        if st.button("🔄 Refrescar historial", use_container_width=True):
            st.rerun()

    llamadas, error = backend_get("/llamadas")

    if error:
        st.error(error)
    elif not llamadas:
        st.info("Aún no hay llamadas registradas.")
    else:
        conteo_clasificaciones = Counter(l.get("clasificacion") for l in llamadas)
        col_verde, col_amarillo, col_rojo = st.columns(3)
        col_verde.metric("🟢 Verde", conteo_clasificaciones.get("verde", 0))
        col_amarillo.metric("🟡 Amarillo", conteo_clasificaciones.get("amarillo", 0))
        col_rojo.metric("🔴 Rojo", conteo_clasificaciones.get("rojo", 0))

        opciones_filtro = [f"{v['icon']} {k.capitalize()}" for k, v in CLASIFICACION_UI.items()]
        seleccion = st.pills(
            "Filtrar por clasificación",
            options=opciones_filtro,
            selection_mode="multi",
            default=opciones_filtro,
        )
        clasificaciones_activas = {
            k for k in CLASIFICACION_UI if f"{CLASIFICACION_UI[k]['icon']} {k.capitalize()}" in seleccion
        }

        llamadas_filtradas = [l for l in llamadas if l.get("clasificacion") in clasificaciones_activas]

        if not llamadas_filtradas:
            st.info("Ninguna llamada coincide con el filtro seleccionado.")

        for llamada in llamadas_filtradas:
            clasificacion = llamada.get("clasificacion", "desconocida")
            ui = CLASIFICACION_UI.get(clasificacion, {"color": "gray", "icon": "⚪", "label": "DESCONOCIDA"})

            with st.container(border=True):
                col_badge, col_fecha = st.columns([3, 2])
                with col_badge:
                    st.badge(ui["label"], icon=ui["icon"], color=ui["color"])
                with col_fecha:
                    st.caption(llamada.get("fecha_llamada", "sin fecha"))

                st.markdown(llamada.get("resumen_narrativo") or "_(sin resumen)_")

                with st.expander("Ver detalle completo"):
                    st.markdown(f"**Razón de clasificación:** {llamada.get('razon_clasificacion', '—')}")
                    st.markdown(
                        f"**Requiere atención humana:** {'Sí' if llamada.get('requiere_atencion_humana') else 'No'}"
                        f" · **Duración:** {llamada.get('duracion_llamada_segundos', '—')} s"
                    )
                    st.markdown(
                        f"**Paciente:** {llamada.get('paciente_id') or 'no identificado'} · "
                        f"**Conversation ID:** `{llamada.get('conversation_id', '—')}`"
                    )

                    st.divider()

                    sintomas = llamada.get("sintomas_reportados")
                    if isinstance(sintomas, dict):
                        campos = list(sintomas.items())
                        col_izq, col_der = st.columns(2)
                        for i, (campo, valor) in enumerate(campos):
                            destino = col_izq if i % 2 == 0 else col_der
                            etiqueta = SINTOMA_LABELS.get(campo, campo.capitalize())
                            destino.markdown(f'<div class="sintoma-label">{etiqueta}</div>', unsafe_allow_html=True)
                            destino.markdown(f'<div class="sintoma-valor">{valor}</div>', unsafe_allow_html=True)
                    else:
                        st.badge("Error al procesar los síntomas de esta llamada", icon="⚠️", color="orange")
