-- Tabla sagrilaft_documentos
-- Ejecutar en: Supabase → SQL Editor
--
-- Resuelve el problema de schema cache de PostgREST:
-- en lugar de agregar columnas url_* a sagrilaft (que requiere reload de cache),
-- los documentos se guardan en esta tabla separada.

create table if not exists public.sagrilaft_documentos (
  id             uuid primary key default gen_random_uuid(),
  sagrilaft_id   uuid not null references public.sagrilaft(id) on delete cascade,
  tipo_documento text not null check (
    tipo_documento in ('rut', 'cedula', 'declaracion_renta', 'camara_comercio', 'composicion_accionaria', 'tusdatos_report')
  ),
  url            text not null,
  created_at     timestamptz not null default now(),

  -- Un solo documento por tipo por registro
  unique (sagrilaft_id, tipo_documento)
);

create index if not exists sagrilaft_docs_sid_idx on public.sagrilaft_documentos (sagrilaft_id);

alter table public.sagrilaft_documentos enable row level security;

create policy "service_role_all" on public.sagrilaft_documentos
  for all
  to service_role
  using (true)
  with check (true);

-- ─── Si la tabla ya existe, actualizar el CHECK constraint ────────────────────
-- (ejecutar solo si la tabla ya fue creada sin tusdatos_report)
alter table public.sagrilaft_documentos
  drop constraint if exists sagrilaft_documentos_tipo_documento_check;

alter table public.sagrilaft_documentos
  add constraint sagrilaft_documentos_tipo_documento_check
  check (tipo_documento in ('rut', 'cedula', 'declaracion_renta', 'camara_comercio', 'composicion_accionaria', 'tusdatos_report'));
