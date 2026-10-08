-- ================================================================
-- V009_rollback — Devuelve sexo y escolaridad a como estaban antes de V009 (usa public.respaldo_v009_redaccion).
-- Solo restaura una persona si su valor actual sigue siendo el que puso V009 (si alguien lo corrigió después, se respeta).
-- La tabla de respaldo NO se borra (puedes borrarla a mano cuando estés seguro).
-- ================================================================
begin;
do $$
declare n integer; v_audit boolean;
begin
  v_audit := exists (select 1 from pg_trigger where tgname = 'trg_audit_personas' and tgrelid = 'public.personas'::regclass);
  if v_audit then alter table public.personas disable trigger trg_audit_personas; end if;
  update public.personas p set sexo = r.valor_anterior
    from (select distinct on (id_persona) id_persona, valor_anterior, valor_nuevo
            from public.respaldo_v009_redaccion where columna = 'sexo' order by id_persona, id asc) r
   where p.id_persona = r.id_persona and p.sexo is not distinct from r.valor_nuevo;
  get diagnostics n = row_count;
  update public.personas p set escolaridad = r.valor_anterior
    from (select distinct on (id_persona) id_persona, valor_anterior, valor_nuevo
            from public.respaldo_v009_redaccion where columna = 'escolaridad' order by id_persona, id asc) r
   where p.id_persona = r.id_persona and p.escolaridad is not distinct from r.valor_nuevo;
  if v_audit then alter table public.personas enable trigger trg_audit_personas; end if;
  insert into public.app_audit_log(email, action, detail) values ('(migración)', 'migration_V009_rollback', format('sexo restaurado: %s filas', n));
end $$;
commit;
