-- ================================================================
-- V011 — UBICACIÓN DE INSTITUCIONES EDUCATIVAS (universidades y escuelas)
-- Vincúlate SEDECO v2
--
-- Solo AGREGA columnas nuevas y opcionales (NULL) a public.catalogo_instituciones.
-- No modifica, borra ni renombra nada existente y NO rellena ningún dato: la
-- ubicación se captura a mano desde la app (Administración → Instituciones).
--
--   tipo                  Universidad | Escuela
--   municipio             municipio de Tlaxcala o «Fuera de Tlaxcala»
--   direccion / codigo_postal
--   latitud / longitud    SOLO si alguien las captura (las dos o ninguna)
--   ubicacion_fuente      manual | importada
--   ubicacion_actualizada cuándo se capturó
--
-- Los permisos (RLS) NO cambian: leer = usuario activo; insertar/editar =
-- administracion.edit; borrar = administracion.delete (V002).
-- Reversión: V011_rollback.sql
-- ================================================================
begin;

alter table public.catalogo_instituciones
  add column if not exists tipo                   text,
  add column if not exists municipio              text,
  add column if not exists direccion              text,
  add column if not exists codigo_postal          text,
  add column if not exists latitud                double precision,
  add column if not exists longitud               double precision,
  add column if not exists ubicacion_fuente       text,
  add column if not exists ubicacion_actualizada  timestamptz;

-- Las columnas nuevas están vacías, así que ninguna fila existente puede violar estas restricciones.
alter table public.catalogo_instituciones drop constraint if exists catalogo_instituciones_ubicacion_check;
alter table public.catalogo_instituciones add constraint catalogo_instituciones_ubicacion_check check (
      (tipo is null or tipo in ('Universidad','Escuela'))
  and (codigo_postal is null or codigo_postal ~ '^[0-9]{5}$')
  and ((latitud is null) = (longitud is null))
  and (latitud  is null or latitud  between 14.0 and 33.0)
  and (longitud is null or longitud between -119.0 and -86.0)
  and (ubicacion_fuente is null or ubicacion_fuente in ('manual','importada'))
);

comment on column public.catalogo_instituciones.tipo is 'Universidad o Escuela. NULL = sin clasificar.';
comment on column public.catalogo_instituciones.latitud is 'Opcional; solo si se capturó. Nada se estima ni se geocodifica.';

commit;

-- Verificación (debe devolver 8; no modifica nada):
--   select count(*) from information_schema.columns where table_schema='public' and table_name='catalogo_instituciones'
--     and column_name in ('tipo','municipio','direccion','codigo_postal','latitud','longitud','ubicacion_fuente','ubicacion_actualizada');
