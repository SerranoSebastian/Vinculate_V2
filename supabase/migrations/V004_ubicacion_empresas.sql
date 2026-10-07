-- ================================================================
-- V004 — UBICACIÓN DE EMPRESAS Y EXCEPCIÓN DE MUNICIPIO POR VACANTE
-- Vincúlate SEDECO v2  (decisión D6)
--
-- Agrega columnas NUEVAS, todas opcionales (NULL). No modifica, borra ni
-- renombra nada existente y NO rellena ningún dato: la ubicación de cada
-- empresa se captura a mano desde la app (Vacantes → Empresas) o se carga
-- desde una fuente revisada. Nunca se geocodifica de forma masiva.
--
--   catalogo_municipios_tlaxcala.cve_mun        clave INEGI de 3 dígitos (se llena con geo/…sql)
--   catalogo_empresas.municipio                  municipio de Tlaxcala o «Fuera de Tlaxcala»
--   catalogo_empresas.cve_mun                    clave INEGI (opcional)
--   catalogo_empresas.direccion / codigo_postal  texto libre / 5 dígitos
--   catalogo_empresas.latitud / longitud         SOLO si alguien las captura; el mapa por
--                                                municipio NO las necesita
--   catalogo_empresas.ubicacion_fuente           manual | ridet | importada | geocodificada
--   catalogo_empresas.ubicacion_actualizada      cuándo se capturó
--   vacantes.municipio_excepcion                 la vacante se ubica en otro municipio distinto
--                                                al de la empresa (p. ej. otra planta)
--
-- Los permisos (RLS) de las tablas NO cambian. Reversión: V004_rollback.sql
-- ================================================================
begin;

alter table public.catalogo_municipios_tlaxcala add column if not exists cve_mun text;

alter table public.catalogo_empresas
  add column if not exists municipio              text,
  add column if not exists cve_mun                text,
  add column if not exists direccion              text,
  add column if not exists codigo_postal          text,
  add column if not exists latitud                double precision,
  add column if not exists longitud               double precision,
  add column if not exists ubicacion_fuente       text,
  add column if not exists ubicacion_actualizada  timestamptz;

alter table public.vacantes add column if not exists municipio_excepcion text;

-- Restricciones (las columnas nuevas están vacías, así que no puede haber filas que las violen)
alter table public.catalogo_municipios_tlaxcala drop constraint if exists catalogo_municipios_cve_mun_check;
alter table public.catalogo_municipios_tlaxcala
  add constraint catalogo_municipios_cve_mun_check check (cve_mun is null or cve_mun ~ '^[0-9]{3}$');

alter table public.catalogo_empresas drop constraint if exists catalogo_empresas_ubicacion_check;
alter table public.catalogo_empresas add constraint catalogo_empresas_ubicacion_check check (
      (cve_mun is null or cve_mun ~ '^[0-9]{3}$')
  and (codigo_postal is null or codigo_postal ~ '^[0-9]{5}$')
  and ((latitud is null) = (longitud is null))                       -- las dos o ninguna
  and (latitud  is null or latitud  between 14.0 and 33.0)           -- México (con margen)
  and (longitud is null or longitud between -119.0 and -86.0)
  and (ubicacion_fuente is null or ubicacion_fuente in ('manual','ridet','importada','geocodificada'))
);

comment on column public.catalogo_empresas.municipio is 'Municipio de Tlaxcala (nombre del catálogo) o «Fuera de Tlaxcala». Captura manual; NULL = sin dato.';
comment on column public.catalogo_empresas.latitud is 'Opcional. El mapa por municipio no depende de este dato.';
comment on column public.vacantes.municipio_excepcion is 'Solo si la vacante está en un municipio distinto al de la empresa.';

commit;

-- Verificación (debe devolver 8 y 1; no modifica nada):
--   select count(*) from information_schema.columns where table_schema='public' and table_name='catalogo_empresas'
--     and column_name in ('municipio','cve_mun','direccion','codigo_postal','latitud','longitud','ubicacion_fuente','ubicacion_actualizada');
--   select count(*) from information_schema.columns where table_schema='public' and table_name='vacantes' and column_name='municipio_excepcion';
