-- ================================================================
-- V005_rollback — Quita las columnas de origen del dato (anio_fuente, institucion_fuente).
-- Los años e instituciones NO cambian: solo desaparece la etiqueta de dónde venían.
-- Si después de V005 se editaron años/instituciones a mano, esas filas ya eran 'registrado'
-- y no se pierde nada más que la etiqueta.
-- ================================================================
begin;
alter table public.personas drop constraint if exists personas_anio_fuente_check;
alter table public.personas drop constraint if exists personas_institucion_fuente_check;
alter table public.personas drop column if exists anio_fuente;
alter table public.personas drop column if exists institucion_fuente;
commit;
