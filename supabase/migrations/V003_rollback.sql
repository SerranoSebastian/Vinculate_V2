-- ================================================================
-- V003_rollback — Quita los triggers y funciones de V003.
-- Las filas ya escritas en app_audit_log se conservan (son historial).
-- ================================================================
begin;
drop trigger if exists trg_audit_personas      on public.personas;
drop trigger if exists trg_audit_vacantes      on public.vacantes;
drop trigger if exists trg_audit_vinculaciones on public.vinculaciones;
drop trigger if exists trg_touch_personas      on public.personas;
drop trigger if exists trg_touch_vacantes      on public.vacantes;
drop trigger if exists trg_touch_vinculaciones on public.vinculaciones;
drop function if exists public.audit_row_change();
drop function if exists public.touch_actualizado_en();
commit;
