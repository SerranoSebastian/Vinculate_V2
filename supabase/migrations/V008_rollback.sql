-- ================================================================
-- V008_rollback — Elimina la tabla de disponibilidad. Se pierden las marcas capturadas.
-- Respaldo previo sugerido:  select * from public.persona_disponibilidad;
-- ================================================================
begin;
drop trigger if exists trg_audit_persona_disponibilidad on public.persona_disponibilidad;
drop trigger if exists trg_touch_persona_disponibilidad on public.persona_disponibilidad;
drop table if exists public.persona_disponibilidad;
commit;
