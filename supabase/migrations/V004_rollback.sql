-- ================================================================
-- V004_rollback — Quita las columnas de ubicación agregadas por V004.
-- ATENCIÓN: se pierden las ubicaciones que se hayan capturado después de V004.
-- Antes de ejecutarlo, respalda lo capturado:
--   select nombre, municipio, direccion, codigo_postal, latitud, longitud from public.catalogo_empresas where municipio is not null;
--   select id_vacante, municipio_excepcion from public.vacantes where municipio_excepcion is not null;
-- ================================================================
begin;
alter table public.catalogo_empresas drop constraint if exists catalogo_empresas_ubicacion_check;
alter table public.catalogo_municipios_tlaxcala drop constraint if exists catalogo_municipios_cve_mun_check;
alter table public.catalogo_empresas
  drop column if exists municipio, drop column if exists cve_mun, drop column if exists direccion,
  drop column if exists codigo_postal, drop column if exists latitud, drop column if exists longitud,
  drop column if exists ubicacion_fuente, drop column if exists ubicacion_actualizada;
alter table public.catalogo_municipios_tlaxcala drop column if exists cve_mun;
alter table public.vacantes drop column if exists municipio_excepcion;
commit;
