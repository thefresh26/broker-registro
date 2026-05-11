-- Agregar columna formacion_inmobiliaria a la tabla sagrilaft
-- Ejecutar en: Supabase → SQL Editor

alter table public.sagrilaft
  add column if not exists formacion_inmobiliaria text
  check (formacion_inmobiliaria in (
    'ninguna', 'curso_diplomado', 'tecnico_inmobiliario',
    'profesional_inmobiliario', 'posgrado_inmobiliario'
  ));

-- También en la tabla brokers si se quiere guardar del formulario de registro
alter table public.brokers
  add column if not exists formacion_inmobiliaria text;

-- Columnas de puntaje que agrega _calcular_evaluacion
alter table public.sagrilaft
  add column if not exists puntaje_formacion_inmobiliaria numeric(6,2);
