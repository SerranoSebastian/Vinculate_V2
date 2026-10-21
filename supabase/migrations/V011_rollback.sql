-- ================================================================
-- V011_rollback — Quita las columnas de ubicación agregadas por V011.
-- ATENCIÓN: se pierden las ubicaciones de instituciones capturadas después de V011.
-- Antes de ejecutarlo, respalda lo capturado:
--   select nombre, tipo, municipio, direccion, codigo_postal, latitud, longitud from public.catalogo_instituciones where latitud is not null or tipo is not null or municipio is not null;
-- ================================================================
begin;
alter table public.catalogo_instituciones drop constraint if exists catalogo_instituciones_ubicacion_check;
alter table public.catalogo_instituciones
  drop column if exists tipo, drop column if exists municipio, drop column if exists direccion,
  drop column if exists codigo_postal, drop column if exists latitud, drop column if exists longitud,
  drop column if exists ubicacion_fuente, drop column if exists ubicacion_actualizada;
commit;
