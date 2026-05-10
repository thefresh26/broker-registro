import os
from typing import Optional

import requests as http
from dotenv import load_dotenv
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from models import SagrilaftRevision  # usado en models.py; revision endpoint ahora usa Form

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BUCKET = "documentos-brokers"

router = APIRouter(prefix="/sagrilaft", tags=["sagrilaft"])

TABLE = "sagrilaft"
TABLA_DOCS = "sagrilaft_documentos"

TIPOS_DOC = ["rut", "cedula", "declaracion_renta", "camara_comercio", "composicion_accionaria", "tusdatos_report"]

FORMACION_MAP = {
    "primaria": 20,
    "secundaria": 30,
    "tecnico": 50,
    "tecnologo": 55,
    "profesional": 70,
    "especializacion": 80,
    "maestria": 90,
    "doctorado": 100,
}


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _headers(prefer: str = None) -> dict:
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return h


async def _subir_archivo(file: UploadFile, path: str) -> str:
    """Sube el archivo y devuelve el path en Storage (no la URL pública)."""
    content = await file.read()
    resp = http.post(
        f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{path}",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": file.content_type or "application/pdf",
            "x-upsert": "true",
        },
        data=content,
    )
    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=500, detail=f"Error subiendo {path}: {resp.text}")
    return path  # guardamos el path, no la URL pública


def _sign_urls(paths: list) -> dict:
    """Genera signed URLs válidas por 1 hora para una lista de paths en Storage.
    Retorna {path: signed_url_completa}."""
    if not paths:
        return {}
    endpoint = f"{SUPABASE_URL}/storage/v1/object/sign/{BUCKET}"
    print(f"[_sign_urls] bucket  : {BUCKET}")
    print(f"[_sign_urls] endpoint: {endpoint}")
    print(f"[_sign_urls] paths   : {paths}")
    resp = http.post(
        endpoint,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        },
        json={"paths": paths, "expiresIn": 3600},
    )
    print(f"[_sign_urls] status  : {resp.status_code}")
    print(f"[_sign_urls] response: {resp.text[:500]}")
    if not resp.ok:
        return {}
    result = {}
    for item in resp.json():
        if not item.get("signedURL") or not item.get("path"):
            continue
        signed = item["signedURL"]
        # Supabase batch-sign devuelve paths relativos sin el prefijo /storage/v1
        if signed.startswith("/object/"):
            signed = "/storage/v1" + signed
        result[item["path"]] = f"{SUPABASE_URL}{signed}"
    return result


def _attach_docs(records: list) -> list:
    """Consulta sagrilaft_documentos, genera signed URLs y fusiona url_* en cada registro."""
    if not records:
        return records
    ids = ",".join(r["id"] for r in records)
    resp = http.get(
        f"{SUPABASE_URL}/rest/v1/{TABLA_DOCS}",
        headers=_headers(),
        params={"sagrilaft_id": f"in.({ids})"},
    )
    docs = resp.json() if resp.ok else []

    # Generar todas las signed URLs en una sola llamada batch
    paths = [d["url"] for d in docs if d.get("url")]
    signed_map = _sign_urls(paths)  # {path: signed_url}

    # Índice: {sagrilaft_id: {tipo_documento: signed_url}}
    idx: dict = {}
    for d in docs:
        path = d.get("url", "")
        idx.setdefault(d["sagrilaft_id"], {})[d["tipo_documento"]] = signed_map.get(path, path)

    # Fusionar en cada registro
    for r in records:
        doc_map = idx.get(r["id"], {})
        for tipo in TIPOS_DOC:
            r[f"url_{tipo}"] = doc_map.get(tipo)
    return records


def _guardar_docs(sagrilaft_id: str, urls: dict) -> None:
    """Inserta o actualiza filas en sagrilaft_documentos."""
    if not urls:
        return
    rows = [
        {"sagrilaft_id": sagrilaft_id, "tipo_documento": col.replace("url_", ""), "url": url}
        for col, url in urls.items()
    ]
    resp = http.post(
        f"{SUPABASE_URL}/rest/v1/{TABLA_DOCS}",
        headers=_headers(prefer="resolution=merge-duplicates,return=minimal"),
        json=rows,
    )
    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=500, detail=f"Error guardando documentos: {resp.text}")


def _calcular_evaluacion(data: dict) -> dict:
    anios = data.get("anios_experiencia") or 0
    neg = data.get("negocios_cerrados") or 0
    nivel = (data.get("nivel_estudios") or "").lower()

    req_documento = bool(data.get("documento"))
    req_rut = bool(data.get("url_rut"))   # viene de _attach_docs
    req_experiencia = anios >= 4
    todos_habilitantes = req_documento and req_rut and req_experiencia

    pts_form = FORMACION_MAP.get(nivel, 0)
    pts_exp = 100 if anios >= 25 else 75 if anios >= 15 else 50 if anios >= 4 else 0
    pts_dig = 50
    pts_des = 100 if neg >= 30 else 80 if neg >= 20 else 60 if neg >= 10 else 40 if neg >= 5 else 20 if neg >= 1 else 0

    total = round(pts_form * 0.20 + pts_exp * 0.30 + pts_dig * 0.20 + pts_des * 0.30, 1)
    resultado = "APROBADO" if todos_habilitantes and total >= 60 else "NO_APROBADO"

    return {
        "puntaje_formacion": round(pts_form * 0.20, 1),
        "puntaje_experiencia": round(pts_exp * 0.30, 1),
        "puntaje_digital": round(pts_dig * 0.20, 1),
        "puntaje_desempeno": round(pts_des * 0.30, 1),
        "puntaje_total": total,
        "resultado_evaluacion": resultado,
    }


# ──────────────────────────────────────────────────────────────
# POST /sagrilaft — el broker envía el formulario con archivos
# ──────────────────────────────────────────────────────────────
@router.post("")
async def crear_sagrilaft(
    tipo_persona: str = Form(...),
    broker_id: Optional[str] = Form(None),
    nombres: Optional[str] = Form(None),
    documento: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    telefono: Optional[str] = Form(None),
    ciudad: Optional[str] = Form(None),
    nivel_estudios: Optional[str] = Form(None),
    anios_experiencia: Optional[int] = Form(None),
    negocios_cerrados: Optional[int] = Form(None),
    es_pep: Optional[bool] = Form(None),
    origen_fondos: Optional[str] = Form(None),
    ingresos: Optional[float] = Form(None),
    egresos: Optional[float] = Form(None),
    activos: Optional[float] = Form(None),
    pasivos: Optional[float] = Form(None),
    file_rut: Optional[UploadFile] = File(None),
    file_cedula: Optional[UploadFile] = File(None),
    file_declaracion_renta: Optional[UploadFile] = File(None),
    file_camara_comercio: Optional[UploadFile] = File(None),
    file_composicion_accionaria: Optional[UploadFile] = File(None),
):
    # 1 — Subir archivos a Storage
    folder = (broker_id or documento or "sin_id").replace("/", "_")
    archivos_map = {
        "url_rut":                    file_rut,
        "url_cedula":                 file_cedula,
        "url_declaracion_renta":      file_declaracion_renta,
        "url_camara_comercio":        file_camara_comercio,
        "url_composicion_accionaria": file_composicion_accionaria,
    }
    urls = {}
    for col, archivo in archivos_map.items():
        if archivo and archivo.filename:
            nombre_archivo = col.replace("url_", "")
            urls[col] = await _subir_archivo(
                archivo, f"sagrilaft/{folder}/{nombre_archivo}.pdf"
            )

    # 2 — INSERT en sagrilaft (solo columnas conocidas por Supabase, sin URLs)
    record = {"estado_sagrilaft": "PENDIENTE", "tipo_persona": tipo_persona}
    for field, value in {
        "broker_id": broker_id,
        "nombres": nombres,
        "documento": documento,
        "email": email,
        "telefono": telefono,
        "ciudad": ciudad,
        "nivel_estudios": nivel_estudios,
        "anios_experiencia": anios_experiencia,
        "negocios_cerrados": negocios_cerrados,
        "es_pep": es_pep,
        "origen_fondos": origen_fondos,
        "ingresos": ingresos,
        "egresos": egresos,
        "activos": activos,
        "pasivos": pasivos,
    }.items():
        if value is not None:
            record[field] = value

    resp = http.post(
        f"{SUPABASE_URL}/rest/v1/{TABLE}",
        headers=_headers(prefer="return=representation"),
        json=record,
    )
    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=500, detail=f"Error creando registro SAGRILAFT: {resp.text}")
    data = resp.json()
    creado = data[0] if isinstance(data, list) else data

    # 3 — Guardar URLs en sagrilaft_documentos (tabla nueva, sin problema de schema cache)
    _guardar_docs(creado["id"], urls)

    return _attach_docs([creado])[0]


# ──────────────────────────────────────────────────────────────
# GET /sagrilaft — lista todos los registros
# ──────────────────────────────────────────────────────────────
@router.get("")
def listar_sagrilaft(estado: Optional[str] = None):
    params = {"order": "created_at.desc"}
    if estado:
        params["estado_sagrilaft"] = f"eq.{estado}"

    resp = http.get(
        f"{SUPABASE_URL}/rest/v1/{TABLE}",
        headers=_headers(),
        params=params,
    )
    resp.raise_for_status()
    return _attach_docs(resp.json())


# ──────────────────────────────────────────────────────────────
# GET /sagrilaft/{id} — obtiene un registro por id
# ──────────────────────────────────────────────────────────────
@router.get("/{sagrilaft_id}")
def obtener_sagrilaft(sagrilaft_id: str):
    resp = http.get(
        f"{SUPABASE_URL}/rest/v1/{TABLE}",
        headers=_headers(),
        params={"id": f"eq.{sagrilaft_id}"},
    )
    resp.raise_for_status()
    data = resp.json()
    if not data:
        raise HTTPException(status_code=404, detail="Registro SAGRILAFT no encontrado")
    return _attach_docs(data)[0]


# ──────────────────────────────────────────────────────────────
# PUT /sagrilaft/{id}/revision
# Recibe el reporte tusdatos.co, lo sube y calcula la evaluación
# GCOM-FT009 en un solo acto. El estado lo determina la evaluación.
# ──────────────────────────────────────────────────────────────
@router.put("/{sagrilaft_id}/revision")
async def revisar_sagrilaft(
    sagrilaft_id: str,
    observaciones_julio: Optional[str] = Form(None),
    file_tusdatos: UploadFile = File(...),
):
    if not file_tusdatos.filename:
        raise HTTPException(status_code=400, detail="El reporte de tusdatos.co es obligatorio")

    # 1 — Subir reporte tusdatos.co a Storage
    path = await _subir_archivo(file_tusdatos, f"sagrilaft/{sagrilaft_id}/tusdatos.pdf")
    _guardar_docs(sagrilaft_id, {"url_tusdatos_report": path})

    # 2 — Obtener el registro con todos los documentos (incluye el tusdatos recién subido)
    get_resp = http.get(
        f"{SUPABASE_URL}/rest/v1/{TABLE}",
        headers=_headers(),
        params={"id": f"eq.{sagrilaft_id}"},
    )
    get_resp.raise_for_status()
    registros = get_resp.json()
    if not registros:
        raise HTTPException(status_code=404, detail="Registro SAGRILAFT no encontrado")
    registro_con_docs = _attach_docs(registros)[0]

    # 3 — Calcular evaluación GCOM-FT009
    evaluacion = _calcular_evaluacion(registro_con_docs)

    # 4 — El estado lo determina exclusivamente la evaluación automática
    estado = "APROBADO" if evaluacion["resultado_evaluacion"] == "APROBADO" else "RECHAZADO"

    update = {
        "estado_sagrilaft": estado,
        "observaciones_julio": observaciones_julio,
        **evaluacion,
    }

    resp = http.patch(
        f"{SUPABASE_URL}/rest/v1/{TABLE}",
        headers=_headers(prefer="return=representation"),
        params={"id": f"eq.{sagrilaft_id}"},
        json=update,
    )
    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=500, detail=f"Error guardando evaluación: {resp.text}")
    data = resp.json()
    if not data:
        raise HTTPException(status_code=404, detail="Registro SAGRILAFT no encontrado")
    return _attach_docs(data)[0]


# ──────────────────────────────────────────────────────────────
# PUT /sagrilaft/{id}/evaluacion — recalcula GCOM-FT009
# Solo ejecutable si estado_sagrilaft = APROBADO
# ──────────────────────────────────────────────────────────────
@router.put("/{sagrilaft_id}/evaluacion")
def evaluar_sagrilaft(sagrilaft_id: str):
    get_resp = http.get(
        f"{SUPABASE_URL}/rest/v1/{TABLE}",
        headers=_headers(),
        params={"id": f"eq.{sagrilaft_id}"},
    )
    get_resp.raise_for_status()
    registros = get_resp.json()
    if not registros:
        raise HTTPException(status_code=404, detail="Registro SAGRILAFT no encontrado")

    if registros[0].get("estado_sagrilaft") != "APROBADO":
        raise HTTPException(
            status_code=400,
            detail="La evaluación GCOM-FT009 solo puede calcularse cuando el estado es APROBADO",
        )

    # Fusionar URLs antes de calcular
    registro_con_docs = _attach_docs(registros)[0]

    resp = http.patch(
        f"{SUPABASE_URL}/rest/v1/{TABLE}",
        headers=_headers(prefer="return=representation"),
        params={"id": f"eq.{sagrilaft_id}"},
        json=_calcular_evaluacion(registro_con_docs),
    )
    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=500, detail=f"Error guardando evaluación: {resp.text}")
    data = resp.json()
    if not data:
        raise HTTPException(status_code=404, detail="Registro SAGRILAFT no encontrado")
    return _attach_docs(data)[0]
