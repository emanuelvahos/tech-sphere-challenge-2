import hashlib
import hmac
import json
import re
import sqlite3
import time
import uuid
from datetime import datetime, timezone

import httpx

from backend import config

# ---------------------------------------------------------------------------
# Verificacion de firma (HMAC-SHA256, esquema tipo Svix/Stripe de ElevenLabs)
#
# Header: elevenlabs-signature: t=<unix_ts>,v0=<hex hmac>
# Mensaje firmado: f"{unix_ts}.{raw_body}"
# ---------------------------------------------------------------------------


def verificar_firma(raw_body: bytes, sig_header: str | None) -> bool:
    if not config.ELEVENLABS_WEBHOOK_SECRET:
        return False
    if not sig_header:
        return False

    partes = dict(p.split("=", 1) for p in sig_header.split(",") if "=" in p)
    timestamp = partes.get("t")
    firma_recibida = partes.get("v0")
    if not timestamp or not firma_recibida:
        return False

    try:
        antiguedad = abs(time.time() - int(timestamp))
    except ValueError:
        return False
    if antiguedad > config.WEBHOOK_SIGNATURE_TOLERANCE_SECONDS:
        return False

    mensaje = f"{timestamp}.{raw_body.decode('utf-8')}".encode("utf-8")
    firma_esperada = hmac.new(
        config.ELEVENLABS_WEBHOOK_SECRET.encode("utf-8"), mensaje, hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(firma_esperada, firma_recibida)


# ---------------------------------------------------------------------------
# Extraccion de datos relevantes del payload post_call_transcription
# ---------------------------------------------------------------------------


def extraer_datos_llamada(payload: dict) -> dict:
    data = payload.get("data", payload)

    transcript = data.get("transcript", []) or []
    turnos = [
        {
            "rol": t.get("role", "unknown"),
            "texto": t.get("message") or "",
            "segundos": t.get("time_in_call_secs"),
        }
        for t in transcript
        if t.get("message")
    ]

    metadata = data.get("metadata", {}) or {}
    duracion = (
        metadata.get("call_duration_secs")
        or (turnos[-1]["segundos"] if turnos and turnos[-1]["segundos"] else None)
        or 0
    )

    dynamic_vars = (
        data.get("conversation_initiation_client_data", {}).get("dynamic_variables", {})
        if isinstance(data.get("conversation_initiation_client_data"), dict)
        else {}
    )
    paciente_id = dynamic_vars.get("paciente_id") or metadata.get("paciente_id")

    return {
        "conversation_id": data.get("conversation_id"),
        "paciente_id": paciente_id,
        "turnos": turnos,
        "duracion_segundos": int(duracion) if duracion else 0,
        "texto_paciente": " ".join(
            t["texto"] for t in turnos if t["rol"] in ("user", "patient")
        ).lower(),
    }


# ---------------------------------------------------------------------------
# Clasificacion de severidad por reglas explicitas (no ML). Umbrales
# documentados en linea. Se evalua sobre el texto de los turnos del
# PACIENTE unicamente (no del agente), en minusculas y sin acentos-sensible
# (se listan variantes con y sin tilde donde es comun).
# ---------------------------------------------------------------------------

PATRONES_ROJO = [
    (r"sangr(ado|e|ando)\s+(abundante|mucho|much[ií]sim)", "sangrado abundante reportado"),
    (r"hemorragia", "hemorragia reportada"),
    (r"(no puedo|dificultad para|me cuesta)\s+respirar", "dificultad respiratoria reportada"),
    (r"falta de aire", "falta de aire reportada"),
    (r"dolor (en el|de) pecho", "dolor de pecho reportado"),
    (r"opresi[oó]n en el pecho", "opresión en el pecho reportada"),
    (r"(confus[oa]|desorientad[oa]|no reconoc)", "confusión / desorientación reportada"),
    (r"(se desmay|p[eé]rdida de conciencia|convulsi[oó]n)", "pérdida de conciencia o convulsión reportada"),
    (r"fiebre.*(39|40|41)\s*(grados|°)", "fiebre muy alta (≥39°C) reportada"),
]

PATRONES_AMARILLO = [
    (r"fiebre.*(3[78][.,]?[5-9]?)\s*(grados|°)", "fiebre moderada (37.5–38.9°C) reportada"),
    (r"(algo de|un poco de|febr[ií]cula)", "fiebre leve / febrícula reportada"),
    (r"(dolor|duele).*(cada vez peor|aumenta|empeorando|m[aá]s fuerte)", "dolor en aumento respecto a lo esperado"),
    (r"(dolor|duele).*(nueve|diez|9|10)\s*(de\s*10|sobre\s*10)?", "dolor de intensidad muy alta (9-10/10) reportado"),
    (r"(pus|secreci[oó]n|supuraci[oó]n)", "secreción/pus en la herida reportada"),
    (r"herida.*(rojo|enrojecid|caliente|mal olor)", "signos de posible infección en la herida"),
    (r"(v[oó]mito|n[aá]useas? persistente)", "vómitos o náuseas persistentes reportados"),
    (r"no (he podido|puedo) (levantarme|caminar|moverme)", "movilidad muy limitada reportada"),
]


def clasificar_severidad(texto_paciente: str) -> dict:
    for patron, razon in PATRONES_ROJO:
        if re.search(patron, texto_paciente):
            return {
                "clasificacion": "rojo",
                "razon_clasificacion": razon,
                "requiere_atencion_humana": True,
            }

    for patron, razon in PATRONES_AMARILLO:
        if re.search(patron, texto_paciente):
            return {
                "clasificacion": "amarillo",
                "razon_clasificacion": razon,
                "requiere_atencion_humana": True,
            }

    return {
        "clasificacion": "verde",
        "razon_clasificacion": "sin señales de alarma ni síntomas fuera de lo esperado en la transcripción",
        "requiere_atencion_humana": False,
    }


# ---------------------------------------------------------------------------
# Resumen clinico estructurado via LLM (NVIDIA NIM, mismo proveedor que
# embeddings). La clasificacion/razon/requiere_atencion_humana NO se le
# preguntan al LLM: ya las decidimos con reglas deterministas arriba y se
# sobrescriben despues de parsear la respuesta, para que la alerta nunca
# dependa de una alucinacion del modelo.
# ---------------------------------------------------------------------------

PROMPT_SISTEMA = (
    "Eres un asistente clinico que resume llamadas telefonicas de seguimiento "
    "postoperatorio para un equipo medico. Lee la transcripcion y devuelve "
    "SOLO un objeto JSON valido, sin texto adicional, sin explicaciones, sin "
    "bloques de codigo markdown. No inventes datos que no esten en la "
    "transcripcion; si algo no se menciono, dilo explicitamente (ej. 'no se "
    "menciono')."
)

JSON_SCHEMA_PROMPT = """Devuelve exactamente este JSON (sin markdown, sin texto extra):
{
  "sintomas_reportados": {
    "dolor": "descripcion breve",
    "fiebre": "descripcion breve",
    "herida": "descripcion breve",
    "movilidad": "descripcion breve",
    "apetito": "descripcion breve",
    "sueno": "descripcion breve"
  },
  "resumen_narrativo": "2-3 oraciones en lenguaje clinico para el equipo medico"
}"""


def _extraer_json(texto: str) -> dict:
    limpio = texto.strip()
    limpio = re.sub(r"^```(json)?", "", limpio.strip(), flags=re.IGNORECASE).strip()
    limpio = re.sub(r"```$", "", limpio.strip()).strip()
    inicio = limpio.find("{")
    fin = limpio.rfind("}")
    if inicio == -1 or fin == -1:
        raise ValueError("no se encontro un objeto JSON en la respuesta del LLM")
    return json.loads(limpio[inicio : fin + 1])


def _llamar_llm(transcript_texto: str) -> dict:
    respuesta = httpx.post(
        f"{config.NVIDIA_EMBEDDINGS_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {config.NVIDIA_API_KEY}"},
        json={
            "model": config.SUMMARY_LLM_MODEL,
            "temperature": 0.2,
            "max_tokens": 700,
            "messages": [
                {"role": "system", "content": PROMPT_SISTEMA},
                {
                    "role": "user",
                    "content": f"Transcripcion de la llamada:\n\n{transcript_texto}\n\n{JSON_SCHEMA_PROMPT}",
                },
            ],
        },
        timeout=30,
    )
    respuesta.raise_for_status()
    contenido = respuesta.json()["choices"][0]["message"]["content"]
    return _extraer_json(contenido)


def generar_resumen_llm(turnos: list[dict]) -> dict:
    transcript_texto = "\n".join(f"{t['rol']}: {t['texto']}" for t in turnos) or "(sin turnos)"

    for intento in range(2):
        try:
            return _llamar_llm(transcript_texto)
        except Exception:
            if intento == 1:
                return {"error_procesamiento": True}
    return {"error_procesamiento": True}


# ---------------------------------------------------------------------------
# Persistencia: SQLite (stdlib, sin dependencia nueva). Se prefiere sobre un
# JSON append-only porque varios webhooks pueden llegar casi al mismo tiempo
# (o el background task de uno todavia no termino cuando llega el otro) y
# SQLite maneja esa escritura concurrente de forma segura sin que tengamos
# que implementar locking a mano.
# ---------------------------------------------------------------------------


def _conectar():
    conn = sqlite3.connect(config.LLAMADAS_DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS llamadas (
            id TEXT PRIMARY KEY,
            fecha_llamada TEXT NOT NULL,
            conversation_id TEXT,
            resumen_json TEXT NOT NULL
        )
        """
    )
    return conn


def persistir_resumen(resumen: dict) -> None:
    conn = _conectar()
    try:
        conn.execute(
            "INSERT INTO llamadas (id, fecha_llamada, conversation_id, resumen_json) VALUES (?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                resumen.get("fecha_llamada", datetime.now(timezone.utc).isoformat()),
                resumen.get("conversation_id"),
                json.dumps(resumen, ensure_ascii=False),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def listar_resumenes() -> list[dict]:
    conn = _conectar()
    try:
        filas = conn.execute(
            "SELECT resumen_json FROM llamadas ORDER BY fecha_llamada DESC"
        ).fetchall()
    finally:
        conn.close()
    return [json.loads(fila[0]) for fila in filas]


# ---------------------------------------------------------------------------
# Orquestacion completa: se llama desde un BackgroundTask del endpoint.
# ---------------------------------------------------------------------------


def procesar_llamada(payload: dict) -> None:
    datos = extraer_datos_llamada(payload)
    severidad = clasificar_severidad(datos["texto_paciente"])
    resumen_llm = generar_resumen_llm(datos["turnos"])

    base = {
        "paciente_id": datos["paciente_id"],
        "conversation_id": datos["conversation_id"],
        "fecha_llamada": datetime.now(timezone.utc).isoformat(),
        "clasificacion": severidad["clasificacion"],
        "razon_clasificacion": severidad["razon_clasificacion"],
        "requiere_atencion_humana": severidad["requiere_atencion_humana"],
        "duracion_llamada_segundos": datos["duracion_segundos"],
    }

    if resumen_llm.get("error_procesamiento"):
        base["sintomas_reportados"] = "error_procesamiento"
        base["resumen_narrativo"] = "error_procesamiento"
    else:
        base["sintomas_reportados"] = resumen_llm.get("sintomas_reportados", "error_procesamiento")
        base["resumen_narrativo"] = resumen_llm.get("resumen_narrativo", "error_procesamiento")

    persistir_resumen(base)
