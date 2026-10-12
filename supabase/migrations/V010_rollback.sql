-- ================================================================
-- V010_rollback — Devuelve cada celda a como estaba antes de V010 (usa public.respaldo_v010_sin_dato).
-- Solo restaura una celda si su valor actual sigue siendo 'Indefinido' (si alguien la corrigió después, se respeta).
-- La tabla de respaldo NO se borra.
-- ================================================================
begin;
do $$
declare r record; n int := 0; audit_p boolean; audit_v boolean;
begin
  audit_p := exists (select 1 from pg_trigger where tgname = 'trg_audit_personas' and tgrelid = 'public.personas'::regclass);
  audit_v := exists (select 1 from pg_trigger where tgname = 'trg_audit_vacantes'  and tgrelid = 'public.vacantes'::regclass);
  if audit_p then alter table public.personas disable trigger trg_audit_personas; end if;
  if audit_v then alter table public.vacantes disable trigger trg_audit_vacantes; end if;
  for r in select distinct on (tabla, id_registro, columna) tabla, id_registro, columna, valor_anterior
             from public.respaldo_v010_sin_dato order by tabla, id_registro, columna, id asc loop
    execute format('update public.%I set %I = $1 where %I::text = $2 and %I = ''Indefinido''',
                   r.tabla, r.columna, case r.tabla when 'personas' then 'id_persona' else 'id_vacante' end, r.columna)
      using r.valor_anterior, r.id_registro;
    n := n + 1;
  end loop;
  if audit_p then alter table public.personas enable trigger trg_audit_personas; end if;
  if audit_v then alter table public.vacantes enable trigger trg_audit_vacantes; end if;
  insert into public.app_audit_log(email, action, detail) values ('(migración)', 'migration_V010_rollback', format('celdas revisadas: %s', n));
end $$;
commit;
