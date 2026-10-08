-- ================================================================
-- V009 — UNIFICAR REDACCIÓN DE «SEXO» Y «ESCOLARIDAD»   (corrección de datos)
-- Vincúlate SEDECO v2
--
-- QUÉ MODIFICA (y nada más):
--   personas.sexo        'MASCULINO' | 'masculino' | 'Hombre'  → 'Masculino'
--                        'FEMENINO'  | 'femenino'  | 'Mujer'   → 'Femenino'
--   personas.escolaridad primera letra en minúscula             → primera letra en mayúscula ('superior' → 'Superior')
--   Solo se tocan las filas que NO están ya escritas así. Cualquier otro valor (p. ej. 'Otro', vacíos) queda igual.
--
-- SEGURIDAD
--   · Antes de cambiar cada valor lo copia a public.respaldo_v009_redaccion (id_persona, columna, valor anterior y nuevo).
--   · V009_rollback.sql devuelve cada valor a como estaba usando ese respaldo.
--   · Re-ejecutable: la segunda vez no encuentra filas por cambiar.
--   · No toca IDs, nombres, ni ninguna otra columna. No borra filas.
--   · Pausa el disparador de auditoría solo durante el UPDATE y deja UNA fila resumen (como V005).
--
-- ANTES DE EJECUTARLA, mira cuántas filas cambiaría (no modifica nada):
--   select 'sexo' c, sexo v, count(*) from public.personas
--     where lower(btrim(sexo)) in ('masculino','hombre','femenino','mujer') and sexo not in ('Masculino','Femenino') group by 2
--   union all
--   select 'escolaridad', escolaridad, count(*) from public.personas
--     where escolaridad is not null and escolaridad <> '' and left(escolaridad,1) <> upper(left(escolaridad,1)) group by 2;
-- ================================================================
begin;

create table if not exists public.respaldo_v009_redaccion (
  id             bigserial primary key,
  id_persona     text not null,
  columna        text not null check (columna in ('sexo','escolaridad')),
  valor_anterior text,
  valor_nuevo    text,
  creado_en      timestamptz not null default now()
);
create index if not exists idx_respaldo_v009_persona on public.respaldo_v009_redaccion(id_persona, columna);
alter table public.respaldo_v009_redaccion enable row level security;
drop policy if exists respaldo_v009_admin on public.respaldo_v009_redaccion;
create policy respaldo_v009_admin on public.respaldo_v009_redaccion for all to authenticated
  using (public.is_admin()) with check (public.is_admin());
revoke all on public.respaldo_v009_redaccion from anon;
comment on table public.respaldo_v009_redaccion is 'Valores originales de personas.sexo / personas.escolaridad antes de V009 (para V009_rollback.sql).';

do $$
declare n_sexo integer; n_esc integer; v_audit boolean;
begin
  v_audit := exists (select 1 from pg_trigger where tgname = 'trg_audit_personas' and tgrelid = 'public.personas'::regclass);
  if v_audit then alter table public.personas disable trigger trg_audit_personas; end if;

  -- sexo
  insert into public.respaldo_v009_redaccion(id_persona, columna, valor_anterior, valor_nuevo)
  select id_persona, 'sexo', sexo,
         case when lower(btrim(sexo)) in ('masculino','hombre') then 'Masculino' else 'Femenino' end
    from public.personas
   where lower(btrim(sexo)) in ('masculino','hombre','femenino','mujer')
     and sexo is distinct from case when lower(btrim(sexo)) in ('masculino','hombre') then 'Masculino' else 'Femenino' end;
  get diagnostics n_sexo = row_count;
  update public.personas
     set sexo = case when lower(btrim(sexo)) in ('masculino','hombre') then 'Masculino' else 'Femenino' end
   where lower(btrim(sexo)) in ('masculino','hombre','femenino','mujer')
     and sexo is distinct from case when lower(btrim(sexo)) in ('masculino','hombre') then 'Masculino' else 'Femenino' end;

  -- escolaridad
  insert into public.respaldo_v009_redaccion(id_persona, columna, valor_anterior, valor_nuevo)
  select id_persona, 'escolaridad', escolaridad, upper(left(escolaridad,1)) || substr(escolaridad,2)
    from public.personas
   where escolaridad is not null and escolaridad <> '' and left(escolaridad,1) <> upper(left(escolaridad,1));
  get diagnostics n_esc = row_count;
  update public.personas
     set escolaridad = upper(left(escolaridad,1)) || substr(escolaridad,2)
   where escolaridad is not null and escolaridad <> '' and left(escolaridad,1) <> upper(left(escolaridad,1));

  if v_audit then alter table public.personas enable trigger trg_audit_personas; end if;
  insert into public.app_audit_log(email, action, detail)
  values ('(migración)', 'migration_V009', format('sexo unificado: %s filas; escolaridad con mayúscula inicial: %s filas', n_sexo, n_esc));
  raise notice 'V009: % valores de sexo y % de escolaridad unificados (respaldo en respaldo_v009_redaccion).', n_sexo, n_esc;
end $$;

commit;
-- Verificación (no modifica nada):
--   select sexo, count(*) from public.personas group by 1 order by 2 desc;   -- solo 'Masculino', 'Femenino' (y lo que ya fuera otro valor)
--   select columna, count(*) from public.respaldo_v009_redaccion group by 1;
