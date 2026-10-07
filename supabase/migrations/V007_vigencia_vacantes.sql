-- ================================================================
-- V007 — VIGENCIA DE VACANTES (fecha de cierre)   (decisión D4)
-- Vincúlate SEDECO v2
--
-- Agrega vacantes.fecha_cierre (DATE, opcional). Una vacante se considera
-- VIGENTE cuando su estado es «Activa» y NO tiene una fecha de cierre ya
-- vencida (el dashboard lo calcula así; ver core/vacantes.py).
--
-- NO se rellena nada: de las 167 vacantes actuales, las que dicen «Activa» pero
-- son de 2024 se revisan una por una en la app (Vacantes → Revisión de vigencia).
-- No se cambia ningún estado de forma automática.
--
-- La restricción de coherencia se crea NOT VALID: se exige solo a las filas que se
-- inserten o modifiquen desde ahora, y nunca rechaza filas históricas.
-- Reversión: V007_rollback.sql
-- ================================================================
begin;
alter table public.vacantes add column if not exists fecha_cierre date;
alter table public.vacantes drop constraint if exists vacantes_fecha_cierre_check;
alter table public.vacantes add constraint vacantes_fecha_cierre_check
  check (fecha_cierre is null or fecha is null or fecha_cierre >= fecha) not valid;
comment on column public.vacantes.fecha_cierre is 'Fecha límite o de cierre de la vacante. NULL = no registrada (vigencia no verificable).';
commit;
