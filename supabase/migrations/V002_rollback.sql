-- ================================================================
-- V002_rollback — Restaura las políticas *_auth_all (acceso total a cualquier
-- usuario activo) y elimina app_settings y las funciones auxiliares de V002.
--
-- ADVERTENCIA: tras este script, los permisos por módulo vuelven a depender
-- solo de la interfaz. Si V003 está aplicada, ejecuta ANTES V003_rollback.sql
-- (V003 usa request_device_id()).
-- Texto de las políticas copiado literalmente del SQL maestro 2026-09-21.
-- ================================================================
begin;

do $$
declare t text;
begin
  foreach t in array array['personas','vacantes','vinculaciones','historial_cargas','catalogo_instituciones','catalogo_carreras','catalogo_municipios_tlaxcala','catalogo_empresas'] loop
    execute format('drop policy if exists %I on public.%I', t||'_select', t);
    execute format('drop policy if exists %I on public.%I', t||'_insert', t);
    execute format('drop policy if exists %I on public.%I', t||'_update', t);
    execute format('drop policy if exists %I on public.%I', t||'_delete', t);
    execute format('drop policy if exists %I on public.%I',t||'_auth_all',t);
    execute format('create policy %I on public.%I for all to authenticated using (public.is_active_user()) with check (public.is_active_user())',t||'_auth_all',t);
  end loop;
end $$;

drop table if exists public.app_settings;
drop function if exists public.device_gate();
drop function if exists public.request_device_id();
drop function if exists public.has_any_permission(text[], text[]);

commit;
