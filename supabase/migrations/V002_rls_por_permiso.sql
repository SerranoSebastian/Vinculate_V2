-- ================================================================
-- V002 — RLS POR PERMISO (módulo × acción)
-- Vincúlate SEDECO v2
--
-- Antes: las 8 tablas de datos y catálogos tenían UNA política `*_auth_all`
-- ("cualquier usuario activo puede todo"). Los permisos por módulo solo se
-- aplicaban en la interfaz, así que un colaborador con la llave pública y su
-- sesión podía leer, modificar o borrar datos por la API directamente.
--
-- Ahora la base de datos aplica la misma matriz que la app:
--   personas / vacantes / vinculaciones
--       SELECT  → has_permission(módulo,'view')
--       INSERT  → has_permission(módulo,'create')
--       UPDATE  → has_permission(módulo,'edit')
--       DELETE  → has_permission(módulo,'delete')
--   historial_cargas
--       SELECT  → ver cualquiera de personas/vacantes/vinculaciones/administracion
--       INSERT  → crear, editar o eliminar en personas/vacantes/vinculaciones
--       DELETE  → administracion.delete   (sin UPDATE: es un registro histórico)
--   catalogo_* (instituciones, carreras, municipios, empresas)
--       SELECT  → cualquier usuario activo
--       escritura → administracion.edit (empresas: también vacantes.create/edit)
--
-- Además agrega, de forma OPCIONAL y apagada por defecto, la validación de
-- equipo en la base (decisión D2: servidor compartido):
--   app_settings('enforce_device_rls') = 'false'  → comportamiento actual
--   app_settings('enforce_device_rls') = 'true'   → los datos solo se leen/escriben
--       desde un equipo autorizado, identificado por el encabezado HTTP
--       `x-device-id` que envía la app v2. El administrador la enciende DESPUÉS
--       de comprobar que la app ya envía ese encabezado (ver README).
--   Nota honesta: el identificador de equipo es un control suave (quien conozca
--   el ID de un equipo autorizado de su propio usuario podría reutilizarlo). La
--   defensa principal siguen siendo el inicio de sesión y los permisos.
--
-- IMPORTANTE: despliega esta migración JUNTO con la app v2 (guardado dirigido).
-- La app antigua hace upsert de la tabla completa y fallaría para quien solo
-- puede "crear". No modifica filas de datos. Reversión: V002_rollback.sql.
-- Requiere V001 aplicada.
-- ================================================================

begin;

-- ---------------------------------------------------------------
-- Funciones auxiliares
-- ---------------------------------------------------------------
create or replace function public.has_any_permission(p_modules text[], p_actions text[])
returns boolean language sql stable security definer set search_path=public as $$
  select exists (
    select 1 from unnest(p_modules) m cross join unnest(p_actions) a
    where public.has_permission(m, a)
  );
$$;

-- Encabezado x-device-id que la app envía en cada petición (PostgREST lo expone
-- en request.headers; los nombres llegan en minúsculas).
create or replace function public.request_device_id()
returns text language sql stable as $$
  select nullif(trim(coalesce(nullif(current_setting('request.headers', true), '')::json ->> 'x-device-id', '')), '');
$$;

create table if not exists public.app_settings (
  key         text primary key,
  value       text not null,
  updated_at  timestamptz not null default now(),
  updated_by  uuid
);
alter table public.app_settings enable row level security;
insert into public.app_settings(key, value) values ('enforce_device_rls', 'false')
  on conflict (key) do nothing;

drop policy if exists settings_select on public.app_settings;
drop policy if exists settings_insert on public.app_settings;
drop policy if exists settings_update on public.app_settings;
drop policy if exists settings_delete on public.app_settings;
create policy settings_select on public.app_settings for select to authenticated using (public.is_active_user());
create policy settings_insert on public.app_settings for insert to authenticated with check (public.is_admin());
create policy settings_update on public.app_settings for update to authenticated using (public.is_admin()) with check (public.is_admin());
create policy settings_delete on public.app_settings for delete to authenticated using (public.is_admin());
grant select, insert, update, delete on public.app_settings to authenticated;

-- Compuerta de equipo: verdadera si la opción está apagada, si es admin, o si
-- el equipo de la petición está autorizado para este usuario.
create or replace function public.device_gate()
returns boolean language sql stable security definer set search_path=public as $$
  select case
    when coalesce((select value from public.app_settings where key='enforce_device_rls'), 'false') <> 'true' then true
    when public.is_admin() then true
    else exists (
      select 1 from public.app_devices d
      where d.user_id = auth.uid() and d.device_id = public.request_device_id() and d.authorized
    )
  end;
$$;

-- ---------------------------------------------------------------
-- Datos operativos: una política por acción
-- ---------------------------------------------------------------
do $$
declare t text;
begin
  foreach t in array array['personas','vacantes','vinculaciones'] loop
    execute format('drop policy if exists %I on public.%I', t||'_auth_all', t);
    execute format('drop policy if exists %I on public.%I', t||'_select', t);
    execute format('drop policy if exists %I on public.%I', t||'_insert', t);
    execute format('drop policy if exists %I on public.%I', t||'_update', t);
    execute format('drop policy if exists %I on public.%I', t||'_delete', t);
    execute format('create policy %I on public.%I for select to authenticated using (public.has_permission(%L,''view'') and public.device_gate())', t||'_select', t, t);
    execute format('create policy %I on public.%I for insert to authenticated with check (public.has_permission(%L,''create'') and public.device_gate())', t||'_insert', t, t);
    execute format('create policy %I on public.%I for update to authenticated using (public.has_permission(%L,''edit'') and public.device_gate()) with check (public.has_permission(%L,''edit'') and public.device_gate())', t||'_update', t, t, t);
    execute format('create policy %I on public.%I for delete to authenticated using (public.has_permission(%L,''delete'') and public.device_gate())', t||'_delete', t, t);
  end loop;
end $$;

-- ---------------------------------------------------------------
-- Historial de cargas
-- ---------------------------------------------------------------
drop policy if exists historial_cargas_auth_all on public.historial_cargas;
drop policy if exists historial_cargas_select on public.historial_cargas;
drop policy if exists historial_cargas_insert on public.historial_cargas;
drop policy if exists historial_cargas_delete on public.historial_cargas;
create policy historial_cargas_select on public.historial_cargas for select to authenticated
  using (public.has_any_permission(array['personas','vacantes','vinculaciones','administracion'], array['view']) and public.device_gate());
create policy historial_cargas_insert on public.historial_cargas for insert to authenticated
  with check (public.has_any_permission(array['personas','vacantes','vinculaciones'], array['create','edit','delete']) and public.device_gate());
create policy historial_cargas_delete on public.historial_cargas for delete to authenticated
  using (public.has_permission('administracion','delete'));

-- ---------------------------------------------------------------
-- Catálogos: lectura para cualquier usuario activo; escritura con permiso
-- ---------------------------------------------------------------
do $$
declare t text;
begin
  foreach t in array array['catalogo_instituciones','catalogo_carreras','catalogo_municipios_tlaxcala'] loop
    execute format('drop policy if exists %I on public.%I', t||'_auth_all', t);
    execute format('drop policy if exists %I on public.%I', t||'_select', t);
    execute format('drop policy if exists %I on public.%I', t||'_insert', t);
    execute format('drop policy if exists %I on public.%I', t||'_update', t);
    execute format('drop policy if exists %I on public.%I', t||'_delete', t);
    execute format('create policy %I on public.%I for select to authenticated using (public.is_active_user())', t||'_select', t);
    execute format('create policy %I on public.%I for insert to authenticated with check (public.has_permission(''administracion'',''edit''))', t||'_insert', t);
    execute format('create policy %I on public.%I for update to authenticated using (public.has_permission(''administracion'',''edit'')) with check (public.has_permission(''administracion'',''edit''))', t||'_update', t);
    execute format('create policy %I on public.%I for delete to authenticated using (public.has_permission(''administracion'',''delete''))', t||'_delete', t);
  end loop;
end $$;

-- catalogo_empresas: también lo mantiene quien administra vacantes
drop policy if exists catalogo_empresas_auth_all on public.catalogo_empresas;
drop policy if exists catalogo_empresas_select on public.catalogo_empresas;
drop policy if exists catalogo_empresas_insert on public.catalogo_empresas;
drop policy if exists catalogo_empresas_update on public.catalogo_empresas;
drop policy if exists catalogo_empresas_delete on public.catalogo_empresas;
create policy catalogo_empresas_select on public.catalogo_empresas for select to authenticated using (public.is_active_user());
create policy catalogo_empresas_insert on public.catalogo_empresas for insert to authenticated
  with check (public.has_permission('administracion','edit') or public.has_permission('vacantes','create'));
create policy catalogo_empresas_update on public.catalogo_empresas for update to authenticated
  using (public.has_permission('administracion','edit') or public.has_permission('vacantes','edit'))
  with check (public.has_permission('administracion','edit') or public.has_permission('vacantes','edit'));
create policy catalogo_empresas_delete on public.catalogo_empresas for delete to authenticated
  using (public.has_permission('administracion','delete'));

-- ---------------------------------------------------------------
-- Verificación: ya no debe quedar ninguna política "for all" en estas tablas
-- ---------------------------------------------------------------
do $$
begin
  if exists (
    select 1 from pg_policies
    where schemaname='public' and cmd='ALL'
      and tablename in ('personas','vacantes','vinculaciones','historial_cargas','catalogo_instituciones','catalogo_carreras','catalogo_municipios_tlaxcala','catalogo_empresas')
  ) then
    raise exception 'V002: aún existen políticas de acceso total en tablas de datos';
  end if;
end $$;

commit;

-- Para ENCENDER la validación de equipo en la base (solo cuando la app ya la envíe):
--   update public.app_settings set value='true', updated_at=now() where key='enforce_device_rls';
-- Para apagarla:
--   update public.app_settings set value='false', updated_at=now() where key='enforce_device_rls';
