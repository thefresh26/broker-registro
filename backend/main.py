import os
from typing import Optional

import requests as http
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from routes.sagrilaft import router as sagrilaft_router

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BUCKET = "documentos-brokers"

app = FastAPI(title="Broker Registro API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sagrilaft_router)


def headers(prefer: str = None) -> dict:
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return h


async def subir_archivo(file: UploadFile, path: str) -> str:
    content = await file.read()
    resp = http.post(
        f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{path}",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": file.content_type or "application/octet-stream",
        },
        data=content,
    )
    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=500, detail=f"Error subiendo {path}: {resp.text}")
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{path}"


@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/brokers")
async def crear_broker(
    tipo_persona: str = Form(...),
    email: str = Form(...),
    telefono: str = Form(...),
    ciudad: str = Form(...),
    experiencia: str = Form(...),
    formacion: str = Form(...),
    nombres: Optional[str] = Form(None),
    apellidos: Optional[str] = Form(None),
    tipo_identificacion: Optional[str] = Form(None),
    numero_identificacion: Optional[str] = Form(None),
    razon_social: Optional[str] = Form(None),
    nit: Optional[str] = Form(None),
    representante_legal: Optional[str] = Form(None),
    doc_identidad: Optional[UploadFile] = File(None),
    doc_rut: Optional[UploadFile] = File(None),
    doc_financiero: Optional[UploadFile] = File(None),
    doc_hoja_vida: Optional[UploadFile] = File(None),
    doc_adicional: Optional[UploadFile] = File(None),
):
    id_ref = numero_identificacion or nit or email

    archivos = {
        "doc_identidad": doc_identidad,
        "doc_rut": doc_rut,
        "doc_financiero": doc_financiero,
        "doc_hoja_vida": doc_hoja_vida,
        "doc_adicional": doc_adicional,
    }

    urls = {}
    for campo, archivo in archivos.items():
        if archivo and archivo.filename:
            ext = archivo.filename.rsplit(".", 1)[-1] if "." in archivo.filename else "bin"
            urls[campo] = await subir_archivo(archivo, f"{id_ref}/{campo}.{ext}")

    broker = {
        "tipo_persona": tipo_persona,
        "nombres": nombres,
        "apellidos": apellidos,
        "tipo_identificacion": tipo_identificacion,
        "numero_identificacion": numero_identificacion,
        "email": email,
        "telefono": telefono,
        "ciudad": ciudad,
        "experiencia": experiencia,
        "formacion": formacion,
        "razon_social": razon_social,
        "nit": nit,
        "representante_legal": representante_legal,
        **urls,
    }

    resp = http.post(
        f"{SUPABASE_URL}/rest/v1/brokers",
        headers=headers(prefer="return=representation"),
        json=broker,
    )
    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=500, detail=f"Error creando broker: {resp.text}")
    return resp.json()


@app.get("/brokers")
def listar_brokers():
    resp = http.get(
        f"{SUPABASE_URL}/rest/v1/brokers",
        headers=headers(),
        params={"order": "created_at.desc"},
    )
    resp.raise_for_status()
    return resp.json()


@app.get("/brokers/{broker_id}")
def obtener_broker(broker_id: str):
    resp = http.get(
        f"{SUPABASE_URL}/rest/v1/brokers",
        headers=headers(),
        params={"id": f"eq.{broker_id}"},
    )
    resp.raise_for_status()
    data = resp.json()
    if not data:
        raise HTTPException(status_code=404, detail="Broker no encontrado")
    return data[0]


@app.put("/brokers/{broker_id}/evaluacion")
def evaluar_broker(
    broker_id: str,
    req_identidad: bool = Form(...),
    req_rut: bool = Form(...),
    req_experiencia: bool = Form(...),
    req_sagrilaft: bool = Form(...),
    puntaje_formacion: float = Form(...),
    puntaje_experiencia: float = Form(...),
    puntaje_digital: float = Form(...),
    puntaje_desempeno: float = Form(...),
    evaluado_por: str = Form(...),
    observaciones: Optional[str] = Form(None),
):
    puntaje_total = puntaje_formacion + puntaje_experiencia + puntaje_digital + puntaje_desempeno
    requisitos_ok = all([req_identidad, req_rut, req_experiencia, req_sagrilaft])
    resultado = "aprobado" if requisitos_ok and puntaje_total >= 60 else "no_aprobado"

    evaluacion = {
        "req_identidad": req_identidad,
        "req_rut": req_rut,
        "req_experiencia": req_experiencia,
        "req_sagrilaft": req_sagrilaft,
        "puntaje_formacion": puntaje_formacion,
        "puntaje_experiencia": puntaje_experiencia,
        "puntaje_digital": puntaje_digital,
        "puntaje_desempeno": puntaje_desempeno,
        "puntaje_total": puntaje_total,
        "resultado": resultado,
        "observaciones": observaciones,
        "evaluado_por": evaluado_por,
    }

    resp = http.patch(
        f"{SUPABASE_URL}/rest/v1/brokers",
        headers=headers(prefer="return=representation"),
        params={"id": f"eq.{broker_id}"},
        json=evaluacion,
    )
    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=500, detail=f"Error actualizando evaluación: {resp.text}")
    data = resp.json()
    if not data:
        raise HTTPException(status_code=404, detail="Broker no encontrado")
    return data[0]
