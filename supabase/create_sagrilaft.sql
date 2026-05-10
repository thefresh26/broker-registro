-- Tabla SAGRILAFT
-- Ejecutar en: Supabase → SQL Editor

create table if not exists public.sagrilaft (
  id                        uuid primary key default gen_random_uuid(),
  broker_id                 uuid references public.brokers(id) on delete set null,
  tipo_persona              text not null check (tipo_persona in ('natural', 'juridica')),
  estado_sagrilaft          text not null default 'PENDIENTE'
                              check (estado_sagrilaft in ('PENDIENTE', 'APROBADO', 'RECHAZADO')),

  -- Datos del interesado
  nombres                   text,
  documento                 text,
  email                     text,
  telefono                  text,
  ciudad                    text,
  nivel_estudios            text,
  anios_experiencia         integer,
  negocios_cerrados         integer,
  es_pep                    boolean,
  origen_fondos             text,

  -- Situación financiera
  ingresos                  numeric(18,2),
  egresos                   numeric(18,2),
  activos                   numeric(18,2),
  pasivos                   numeric(18,2),

  -- URLs de documentos subidos a Storage
  url_rut                   text,
  url_cedula                text,
  url_declaracion_renta     text,
  url_camara_comercio       text,
  url_composicion_accionaria text,

  -- Evaluación GCOM-FT009 (se llena automáticamente al aprobar)
  puntaje_formacion         numeric(6,2),
  puntaje_experiencia       numeric(6,2),
  puntaje_digital           numeric(6,2),
  puntaje_desempeno         numeric(6,2),
  puntaje_total             numeric(6,2),
  resultado_evaluacion      text check (resultado_evaluacion in ('APROBADO', 'NO_APROBADO')),

  -- Revisión de Julio
  observaciones_julio       text,

  created_at                timestamptz not null default now()
);

-- ─── Si la tabla ya existe, agregar las columnas de URLs ──────────────────────
alter table public.sagrilaft add column if not exists url_rut                    text;
alter table public.sagrilaft add column if not exists url_cedula                 text;
alter table public.sagrilaft add column if not exists url_declaracion_renta      text;
alter table public.sagrilaft add column if not exists url_camara_comercio        text;
alter table public.sagrilaft add column if not exists url_composicion_accionaria text;

-- ─── Índices ──────────────────────────────────────────────────────────────────
create index if not exists sagrilaft_estado_idx   on public.sagrilaft (estado_sagrilaft);
create index if not exists sagrilaft_broker_idx   on public.sagrilaft (broker_id);
create index if not exists sagrilaft_created_idx  on public.sagrilaft (created_at desc);

-- ─── RLS ──────────────────────────────────────────────────────────────────────
alter table public.sagrilaft enable row level security;

create policy "service_role_all" on public.sagrilaft
  for all
  to service_role
  using (true)
  with check (true);
