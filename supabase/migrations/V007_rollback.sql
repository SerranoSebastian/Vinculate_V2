-- ================================================================
-- V007_rollback — Quita vacantes.fecha_cierre. Se pierden las fechas capturadas después de V007.
-- Respaldo previo sugerido:  select id_vacante, fecha_cierre from public.vacantes where fecha_cierre is not null;
-- ================================================================
begin;
alter table public.vacantes drop constraint if exists vacantes_fecha_cierre_check;
alter table public.vacantes drop column if exists fecha_cierre;
commit;
