from typing import Optional
from pydantic import BaseModel


class SagrilaftCreate(BaseModel):
    broker_id: Optional[str] = None
    tipo_persona: str
    nombres: Optional[str] = None
    documento: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    ciudad: Optional[str] = None
    nivel_estudios: Optional[str] = None
    anios_experiencia: Optional[int] = None
    negocios_cerrados: Optional[int] = None
    es_pep: Optional[bool] = None
    origen_fondos: Optional[str] = None
    ingresos: Optional[float] = None
    egresos: Optional[float] = None
    activos: Optional[float] = None
    pasivos: Optional[float] = None


class SagrilaftRevision(BaseModel):
    estado_sagrilaft: str  # APROBADO | RECHAZADO
    observaciones_julio: Optional[str] = None
