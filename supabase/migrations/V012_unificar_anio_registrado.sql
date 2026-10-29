-- ================================================================
-- V012 — UNIFICAR EL AÑO «ESTIMADO» CON EL «REGISTRADO»   (corrección de datos, opcional)
-- Vincúlate SEDECO v2
--
-- Hoy personas.anio_fuente distingue 'registrado' de 'imputado' (año estimado en la limpieza de septiembre de 2026, V005).
-- Esta migración deja UNA sola forma: todas pasan a 'registrado', para que los reportes cuenten simplemente «vinculaciones».
--
-- QUÉ MODIFICA (y nada más):
--   personas.anio_fuente: de 'imputado' a 'registrado'. NO cambia el año (personas.anio), ni ninguna otra columna,
--   ni institucion_fuente (las instituciones «balanceadas» se quedan como están). No borra filas.
--
-- SEGURIDAD
--   · Cada fila afectada se copia antes a public.respaldo_v012_anio_fuente (id_persona, año y etiqueta anterior; solo administradores).
--   · V012_rollback.sql vuelve a poner 'imputado' (solo si el año de esa persona sigue siendo el mismo).
--   · Re-ejecutable: la segunda vez no encuentra nada por cambiar.
--   · Pausa la auditoría fila por fila solo durante el UPDATE y deja UNA fila resumen (como V005/V009/V010).
--   · Requiere V005 (la columna anio_fuente). La app ya muestra los años unificados aunque NO ejecutes esta migración.
--
-- ANTES DE EJECUTARLA, mira cuántas filas cambiaría (no modifica nada):
--   select anio_fuente, count(*) from public.personas group by 1;     -- «imputado» es lo que se unificará
-- ================================================================
begin;

do $$
begin
  if not exists (select 1 from information_schema.columns where table_schema = 'public' and table_name = 'personas' and column_name = 'anio_fuente') then
    raise exception 'V012 necesita V005 (columna personas.anio_fuente). Aplica V005 primero.';
  end if;
end $$;

create table if not exists public.respaldo_v012_anio_fuente (
  id             bigserial primary key,
  id_persona     text not null,
  anio           integer,
  valor_anterior text not null,
  creado_en      timestamptz not null default now()
);
create index if not exists idx_respaldo_v012 on public.respaldo_v012_anio_fuente(id_persona);
alter table public.respaldo_v012_anio_fuente enable row level security;
drop policy if exists respaldo_v012_admin on public.respaldo_v012_anio_fuente;
create policy respaldo_v012_admin on public.respaldo_v012_anio_fuente for all to authenticated
  using (public.is_admin()) with check (public.is_admin());
revoke all on public.respaldo_v012_anio_fuente from anon;
comment on table public.respaldo_v012_anio_fuente is 'Etiqueta anio_fuente original antes de V012 (unificar año estimado y registrado), para V012_rollback.sql.';

do $$
declare n int; audit_p boolean;
begin
  audit_p := exists (select 1 from pg_trigger where tgname = 'trg_audit_personas' and tgrelid = 'public.personas'::regclass);
  if audit_p then alter table public.personas disable trigger trg_audit_personas; end if;

  insert into public.respaldo_v012_anio_fuente(id_persona, anio, valor_anterior)
    select id_persona, anio, anio_fuente from public.personas where anio_fuente = 'imputado';
  update public.personas set anio_fuente = 'registrado' where anio_fuente = 'imputado';
  get diagnostics n = row_count;

  if audit_p then alter table public.personas enable trigger trg_audit_personas; end if;
  insert into public.app_audit_log(email, action, detail)
  values ('(migración)', 'migration_V012', format('anio_fuente imputado -> registrado: %s filas', n));
  raise notice 'V012: % años unificados como «registrado» (respaldo en respaldo_v012_anio_fuente).', n;
end $$;

commit;
-- Verificación (no modifica nada; debe devolver 0):
--   select count(*) from public.personas where anio_fuente = 'imputado';
