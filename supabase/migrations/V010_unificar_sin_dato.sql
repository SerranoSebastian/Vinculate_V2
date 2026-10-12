-- ================================================================
-- V010 — UNIFICAR «SIN DATO» EN LA BASE   (corrección de datos, opcional)
-- Vincúlate SEDECO v2
--
-- Hoy la base guarda «no hay dato» de varias formas: 'indefinido', 'Indefinido', 'Sin Información', 'Sin Dato',
-- 'Información no disponible', 'N/A'… Esta migración deja UNA sola: 'Indefinido'.
--
-- QUÉ MODIFICA (y nada más):
--   personas:  sexo, escolaridad, carrera, institucion, municipio, area_carrera, grupo_prioritario, telefono, correo
--   vacantes:  sector_empresa
--   Solo las celdas cuyo texto (sin espacios, sin importar mayúsculas) sea una de esas formas de «sin dato» y que NO estén
--   ya escritas exactamente 'Indefinido'. Las celdas vacías/NULL NO se tocan (siguen vacías; la app ya las muestra igual).
--   No toca IDs, nombres, fechas ni ninguna otra columna. No borra filas.
--
-- SEGURIDAD
--   · Cada valor se copia antes a public.respaldo_v010_sin_dato (tabla, id, columna, valor anterior y nuevo; solo administradores).
--   · V010_rollback.sql devuelve cada valor a como estaba.
--   · Re-ejecutable: la segunda vez no encuentra nada por cambiar.
--   · Pausa la auditoría fila por fila solo durante el UPDATE y deja UNA fila resumen (como V005/V009).
--   · NOTA: la app ya muestra «Indefinido» para todas esas formas aunque NO ejecutes esta migración.
--
-- ANTES DE EJECUTARLA, mira cuántas celdas cambiaría (no modifica nada):
--   select 'sexo' columna, sexo valor, count(*) from public.personas
--    where lower(btrim(sexo)) in ('indefinido','indefinida','sin informacion','sin información','sin dato','sin datos','sin especificar','no definido','información no disponible','informacion no disponible','no disponible','n/a','s/d')
--      and sexo <> 'Indefinido' group by 2;      -- (repite cambiando la columna)
-- ================================================================
begin;

create table if not exists public.respaldo_v010_sin_dato (
  id             bigserial primary key,
  tabla          text not null check (tabla in ('personas','vacantes')),
  id_registro    text not null,
  columna        text not null,
  valor_anterior text,
  valor_nuevo    text not null default 'Indefinido',
  creado_en      timestamptz not null default now()
);
create index if not exists idx_respaldo_v010 on public.respaldo_v010_sin_dato(tabla, id_registro, columna);
alter table public.respaldo_v010_sin_dato enable row level security;
drop policy if exists respaldo_v010_admin on public.respaldo_v010_sin_dato;
create policy respaldo_v010_admin on public.respaldo_v010_sin_dato for all to authenticated
  using (public.is_admin()) with check (public.is_admin());
revoke all on public.respaldo_v010_sin_dato from anon;
comment on table public.respaldo_v010_sin_dato is 'Valores originales antes de V010 (unificar «sin dato» en «Indefinido»), para V010_rollback.sql.';

do $$
declare
  formas text[] := array['indefinido','indefinida','sin informacion','sin información','sin dato','sin datos','sin especificar',
                         'no definido','información no disponible','informacion no disponible','no disponible','n/a','s/d'];
  destinos text[][] := array[
    ['personas','id_persona','sexo'], ['personas','id_persona','escolaridad'], ['personas','id_persona','carrera'],
    ['personas','id_persona','institucion'], ['personas','id_persona','municipio'], ['personas','id_persona','area_carrera'],
    ['personas','id_persona','grupo_prioritario'], ['personas','id_persona','telefono'], ['personas','id_persona','correo'],
    ['vacantes','id_vacante','sector_empresa']];
  i int; t text; pk text; c text; n int; total int := 0;
  audit_p boolean; audit_v boolean;
begin
  audit_p := exists (select 1 from pg_trigger where tgname = 'trg_audit_personas' and tgrelid = 'public.personas'::regclass);
  audit_v := exists (select 1 from pg_trigger where tgname = 'trg_audit_vacantes'  and tgrelid = 'public.vacantes'::regclass);
  if audit_p then alter table public.personas disable trigger trg_audit_personas; end if;
  if audit_v then alter table public.vacantes disable trigger trg_audit_vacantes; end if;

  for i in 1 .. array_length(destinos, 1) loop
    t := destinos[i][1]; pk := destinos[i][2]; c := destinos[i][3];
    execute format(
      'insert into public.respaldo_v010_sin_dato(tabla, id_registro, columna, valor_anterior)
         select %L, %I::text, %L, %I from public.%I where lower(btrim(%I)) = any($1) and %I <> ''Indefinido''',
      t, pk, c, c, t, c, c) using formas;
    get diagnostics n = row_count;
    execute format('update public.%I set %I = ''Indefinido'' where lower(btrim(%I)) = any($1) and %I <> ''Indefinido''', t, c, c, c) using formas;
    total := total + n;
  end loop;

  if audit_p then alter table public.personas enable trigger trg_audit_personas; end if;
  if audit_v then alter table public.vacantes enable trigger trg_audit_vacantes; end if;
  insert into public.app_audit_log(email, action, detail)
  values ('(migración)', 'migration_V010', format('celdas «sin dato» unificadas en Indefinido: %s', total));
  raise notice 'V010: % celdas unificadas en «Indefinido» (respaldo en respaldo_v010_sin_dato).', total;
end $$;

commit;
-- Verificación (no modifica nada):
--   select tabla, columna, count(*) from public.respaldo_v010_sin_dato group by 1,2 order by 1,2;
