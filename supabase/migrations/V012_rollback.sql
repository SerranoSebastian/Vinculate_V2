-- ================================================================
-- V012_rollback — Vuelve a marcar como 'imputado' los años que V012 unificó (usa public.respaldo_v012_anio_fuente).
-- Solo restaura una fila si su año sigue siendo el mismo que tenía al aplicar V012 (si alguien lo corrigió después, se respeta).
-- La tabla de respaldo NO se borra.
-- ================================================================
begin;
do $$
declare n int; audit_p boolean;
begin
  audit_p := exists (select 1 from pg_trigger where tgname = 'trg_audit_personas' and tgrelid = 'public.personas'::regclass);
  if audit_p then alter table public.personas disable trigger trg_audit_personas; end if;
  update public.personas p set anio_fuente = r.valor_anterior
    from (select distinct on (id_persona) id_persona, anio, valor_anterior from public.respaldo_v012_anio_fuente order by id_persona, id asc) r
   where p.id_persona = r.id_persona and p.anio is not distinct from r.anio and p.anio_fuente = 'registrado';
  get diagnostics n = row_count;
  if audit_p then alter table public.personas enable trigger trg_audit_personas; end if;
  insert into public.app_audit_log(email, action, detail) values ('(migración)', 'migration_V012_rollback', format('filas restauradas: %s', n));
end $$;
commit;
