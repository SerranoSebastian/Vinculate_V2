-- ================================================================
-- V001 — CIERRE DE BRECHAS DE SEGURIDAD
-- Vincúlate SEDECO v2
--
-- Qué hace (y SOLO esto):
--   1. El rol `anon` (cualquiera con la URL y la llave pública, sin iniciar
--      sesión) deja de tener acceso a todo el esquema public. Antes podía leer
--      la tabla `personas` completa (nombre, teléfono, correo).
--   2. Las altas, cambios y bajas DIRECTAS sobre app_profiles y app_permissions
--      quedan solo para administradores. Los delegados con permiso `usuarios`
--      siguen trabajando mediante los RPC (que traen sus propias reglas).
--      Antes, quien tenía `usuarios.edit` podía ponerse rol admin con un UPDATE.
--   3. Se reescriben los 5 RPC administrativos para que un usuario NO admin:
--        - no pueda dar rol admin ni tocar cuentas admin,
--        - no pueda restablecer la contraseña de un admin (ni "reparando" su alta),
--        - no pueda editar sus propios permisos ni otorgar permisos que no tiene.
--   4. admin_delete_user_account deja de borrar app_audit_log (la auditoría
--      se conserva; el FK ya la deja con user_id nulo y el correo intacto).
--   5. app_devices: un usuario ya no puede registrar su equipo como autorizado
--      ni cambiar user_id/device_id de una fila; autorizar requiere admin o
--      permiso `dispositivos.edit`.
--
-- NO modifica ni elimina ninguna fila de datos (personas, vacantes, etc.).
-- Es una transacción: si la verificación final falla, no queda nada aplicado.
-- Reversión: V001_rollback.sql (restaura el estado anterior textualmente).
--
-- CÓMO EJECUTAR: Supabase → SQL Editor. Primero en un proyecto de PRUEBAS.
-- ================================================================

begin;

-- ---------------------------------------------------------------
-- 1) anon sin acceso a nada en public
-- ---------------------------------------------------------------
drop policy if exists personas_anon_ping on public.personas;

revoke all on all tables    in schema public from anon;
revoke all on all sequences in schema public from anon;
revoke all on all functions in schema public from anon;

alter default privileges in schema public revoke all on tables    from anon;
alter default privileges in schema public revoke all on sequences from anon;
alter default privileges in schema public revoke all on functions from anon;

-- ---------------------------------------------------------------
-- 2) Escritura directa en perfiles y permisos: solo administradores
--    (la lectura no cambia: profiles_select / permissions_select)
-- ---------------------------------------------------------------
drop policy if exists profiles_insert    on public.app_profiles;
drop policy if exists profiles_update    on public.app_profiles;
drop policy if exists profiles_delete    on public.app_profiles;
drop policy if exists permissions_insert on public.app_permissions;
drop policy if exists permissions_update on public.app_permissions;
drop policy if exists permissions_delete on public.app_permissions;

create policy profiles_insert on public.app_profiles for insert to authenticated
  with check (public.is_admin());
create policy profiles_update on public.app_profiles for update to authenticated
  using (public.is_admin()) with check (public.is_admin());
create policy profiles_delete on public.app_profiles for delete to authenticated
  using (public.is_admin());

create policy permissions_insert on public.app_permissions for insert to authenticated
  with check (public.is_admin());
create policy permissions_update on public.app_permissions for update to authenticated
  using (public.is_admin()) with check (public.is_admin());
create policy permissions_delete on public.app_permissions for delete to authenticated
  using (public.is_admin());

-- ---------------------------------------------------------------
-- 3) RPC administrativos con reglas anti-escalamiento
-- ---------------------------------------------------------------
create or replace function public.admin_finalize_collaborator(p_email text,p_new_password text,p_display_name text)
returns uuid language plpgsql security definer set search_path=public,auth,extensions as $$
declare v_email text:=lower(trim(coalesce(p_email,''))); v_uid uuid; v_name text:=trim(coalesce(p_display_name,'')); v_role text;
begin
 if not(public.is_admin() or public.has_permission('usuarios','create')) then raise exception 'No autorizado para crear usuarios'; end if;
 if v_email='' or position('@' in v_email)<=1 then raise exception 'Correo electrónico inválido'; end if;
 if p_new_password is null or length(p_new_password)<8 or length(p_new_password)>72 then raise exception 'La contraseña debe tener entre 8 y 72 caracteres'; end if;
 select id into v_uid from auth.users where lower(email)=v_email order by created_at desc limit 1;
 if v_uid is null then raise exception 'El usuario todavía no existe en Supabase Authentication. Reintenta el alta.'; end if;
 -- V001: este RPC restablece la contraseña del usuario existente ("reparar alta").
 -- Un delegado no puede hacerlo sobre un administrador, y sobre cualquier cuenta
 -- ya existente necesita además permiso de edición de usuarios.
 select role into v_role from public.app_profiles where user_id=v_uid;
 if v_role is not null and not public.is_admin() then
   if v_role='admin' then raise exception 'Solo un administrador puede modificar una cuenta de administrador'; end if;
   if not public.has_permission('usuarios','edit') then raise exception 'Ese usuario ya existe; repararlo requiere permiso de edición de usuarios'; end if;
 end if;
 if v_name='' then v_name:=v_email; end if;
 if exists(select 1 from public.app_profiles where lower(email)=v_email and user_id<>v_uid) then raise exception 'Existe un perfil duplicado con este correo.'; end if;
 update auth.users set encrypted_password=extensions.crypt(p_new_password,extensions.gen_salt('bf')),email_confirmed_at=coalesce(email_confirmed_at,now()),raw_user_meta_data=coalesce(raw_user_meta_data,'{}'::jsonb)||jsonb_build_object('display_name',v_name),updated_at=now() where id=v_uid;
 insert into public.app_profiles(user_id,email,display_name,role,status) values(v_uid,v_email,v_name,'collaborator','active') on conflict(user_id) do update set email=excluded.email,display_name=excluded.display_name,role=case when public.app_profiles.role='admin' then 'admin' else 'collaborator' end,status='active',updated_at=now();
 insert into public.app_permissions(user_id,module_key,can_view,can_create,can_edit,can_delete,can_export,updated_at)
 select v_uid,m,(m='inicio'),false,false,false,false,now() from unnest(array['inicio','personas','vacantes','vinculaciones','explorador','ridet','administracion','usuarios','dispositivos','prioridades','auditoria','respaldos']) m on conflict(user_id,module_key) do nothing;
 return v_uid;
end $$;

create or replace function public.admin_replace_user_permissions(p_user_id uuid,p_permissions jsonb)
returns void language plpgsql security definer set search_path=public as $$
declare item jsonb; mk text; cv boolean; cc boolean; ce boolean; cd boolean; cx boolean; v_admin boolean:=public.is_admin();
begin
 if not(v_admin or public.has_permission('usuarios','edit')) then raise exception 'No autorizado para modificar permisos'; end if;
 if not v_admin and p_user_id=auth.uid() then raise exception 'No puedes modificar tus propios permisos'; end if;
 if not exists(select 1 from public.app_profiles where user_id=p_user_id) then raise exception 'El perfil indicado no existe'; end if;
 if exists(select 1 from public.app_profiles where user_id=p_user_id and role='admin') then raise exception 'La matriz de un administrador no se modifica desde esta operación'; end if;
 if jsonb_typeof(p_permissions)<>'array' then raise exception 'Formato de permisos inválido'; end if;
 delete from public.app_permissions where user_id=p_user_id;
 for item in select value from jsonb_array_elements(p_permissions) loop
  mk:=trim(coalesce(item->>'module_key','')); if mk<>all(array['inicio','personas','vacantes','vinculaciones','explorador','ridet','administracion','usuarios','dispositivos','prioridades','auditoria','respaldos']) then continue; end if;
  cv:=coalesce((item->>'can_view')::boolean,false);
  cc:=cv and coalesce((item->>'can_create')::boolean,false);
  ce:=cv and coalesce((item->>'can_edit')::boolean,false);
  cd:=cv and coalesce((item->>'can_delete')::boolean,false);
  cx:=cv and coalesce((item->>'can_export')::boolean,false);
  -- V001: un delegado no puede otorgar lo que él mismo no tiene.
  if not v_admin then
    if (cv and not public.has_permission(mk,'view')) or (cc and not public.has_permission(mk,'create'))
       or (ce and not public.has_permission(mk,'edit')) or (cd and not public.has_permission(mk,'delete'))
       or (cx and not public.has_permission(mk,'export')) then
      raise exception 'No puedes otorgar permisos que tú no tienes (módulo %)',mk;
    end if;
  end if;
  insert into public.app_permissions(user_id,module_key,can_view,can_create,can_edit,can_delete,can_export,updated_at) values(p_user_id,mk,cv,cc,ce,cd,cx,now());
 end loop;
end $$;

create or replace function public.admin_set_user_password(p_user_id uuid,p_new_password text)
returns void language plpgsql security definer set search_path=public,auth,extensions as $$
begin
 if not(public.is_admin() or public.has_permission('usuarios','edit')) then raise exception 'No autorizado'; end if;
 if p_new_password is null or length(p_new_password)<8 or length(p_new_password)>72 then raise exception 'La contraseña debe tener entre 8 y 72 caracteres'; end if;
 if not public.is_admin() and exists(select 1 from public.app_profiles where user_id=p_user_id and role='admin') then raise exception 'Solo un administrador puede cambiar la contraseña de un administrador'; end if;
 update auth.users set encrypted_password=extensions.crypt(p_new_password,extensions.gen_salt('bf')),email_confirmed_at=coalesce(email_confirmed_at,now()),updated_at=now() where id=p_user_id;
 if not found then raise exception 'Usuario no encontrado'; end if;
end $$;

create or replace function public.admin_update_user_account(p_user_id uuid,p_email text,p_display_name text,p_role text,p_status text)
returns void language plpgsql security definer set search_path=public,auth,extensions as $$
declare v_email text:=lower(trim(coalesce(p_email,''))); v_name text:=trim(coalesce(p_display_name,''));
begin
 if not(public.is_admin() or public.has_permission('usuarios','edit')) then raise exception 'No autorizado para modificar cuentas'; end if;
 -- V001: reglas para quien NO es administrador
 if not public.is_admin() then
   if p_user_id=auth.uid() then raise exception 'No puedes modificar tu propia cuenta con esta operación'; end if;
   if exists(select 1 from public.app_profiles where user_id=p_user_id and role='admin') then raise exception 'Solo un administrador puede modificar una cuenta de administrador'; end if;
   if p_role is distinct from 'collaborator' then raise exception 'Solo un administrador puede asignar el rol de administrador'; end if;
 end if;
 if v_email='' or v_email !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$' then raise exception 'Correo electrónico inválido'; end if;
 if p_role not in('admin','collaborator') then raise exception 'Rol inválido'; end if; if p_status not in('pending','active','disabled') then raise exception 'Estado inválido'; end if; if v_name='' then v_name:=v_email; end if;
 if exists(select 1 from auth.users where lower(email)=v_email and id<>p_user_id) or exists(select 1 from public.app_profiles where lower(email)=v_email and user_id<>p_user_id) then raise exception 'Ese correo ya pertenece a otra cuenta'; end if;
 if exists(select 1 from public.app_profiles where user_id=p_user_id and role='admin' and status='active') and (p_role<>'admin' or p_status<>'active') and (select count(*) from public.app_profiles where role='admin' and status='active')<=1 then raise exception 'No se puede desactivar o degradar al último administrador activo'; end if;
 update auth.users set email=v_email,email_confirmed_at=coalesce(email_confirmed_at,now()),raw_user_meta_data=coalesce(raw_user_meta_data,'{}'::jsonb)||jsonb_build_object('display_name',v_name),updated_at=now() where id=p_user_id; if not found then raise exception 'Usuario no encontrado en Authentication'; end if;
 update auth.identities set identity_data=coalesce(identity_data,'{}'::jsonb)||jsonb_build_object('email',v_email),updated_at=now() where user_id=p_user_id and provider='email';
 update public.app_profiles set email=v_email,display_name=v_name,role=p_role,status=p_status,updated_at=now() where user_id=p_user_id; if not found then raise exception 'Perfil Vincúlate no encontrado'; end if;
 if p_status='disabled' then update public.app_devices set authorized=false where user_id=p_user_id; end if;
end $$;

create or replace function public.admin_delete_user_account(p_user_id uuid)
returns void language plpgsql security definer set search_path=public,auth as $$
begin
 if not(public.is_admin() or public.has_permission('usuarios','delete')) then raise exception 'No autorizado para eliminar cuentas'; end if;
 if p_user_id=auth.uid() then raise exception 'No puedes eliminar tu propia cuenta durante una sesión activa'; end if;
 if not exists(select 1 from public.app_profiles where user_id=p_user_id) then raise exception 'Perfil no encontrado'; end if;
 if not public.is_admin() and exists(select 1 from public.app_profiles where user_id=p_user_id and role='admin') then raise exception 'Solo un administrador puede eliminar una cuenta de administrador'; end if;
 if exists(select 1 from public.app_profiles where user_id=p_user_id and role='admin' and status='active') and (select count(*) from public.app_profiles where role='admin' and status='active')<=1 then raise exception 'No se puede eliminar al último administrador activo'; end if;
 -- V001: ya NO se borra app_audit_log. Al eliminar el perfil, el FK
 -- (on delete set null) deja las filas de auditoría con user_id nulo y el correo intacto.
 delete from public.app_priority_notifications where user_id=p_user_id; delete from public.app_priorities where created_by=p_user_id; delete from public.app_permissions where user_id=p_user_id; delete from public.app_devices where user_id=p_user_id; delete from public.app_profiles where user_id=p_user_id; delete from auth.users where id=p_user_id;
end $$;

-- Mismos privilegios que antes (solo usuarios autenticados; nunca anon)
revoke all on function public.admin_finalize_collaborator(text,text,text) from public;
revoke all on function public.admin_replace_user_permissions(uuid,jsonb) from public;
revoke all on function public.admin_set_user_password(uuid,text) from public;
revoke all on function public.admin_update_user_account(uuid,text,text,text,text) from public;
revoke all on function public.admin_delete_user_account(uuid) from public;
grant execute on function public.admin_finalize_collaborator(text,text,text),public.admin_replace_user_permissions(uuid,jsonb),public.admin_set_user_password(uuid,text),public.admin_update_user_account(uuid,text,text,text,text),public.admin_delete_user_account(uuid) to authenticated;

-- ---------------------------------------------------------------
-- 4) Equipos: no auto-autorizarse ni cambiar la identidad de la fila
-- ---------------------------------------------------------------
drop policy if exists devices_insert on public.app_devices;
create policy devices_insert on public.app_devices for insert to authenticated
  with check (user_id=auth.uid() and public.is_active_user() and (authorized=false or public.is_admin()));

create or replace function public.app_devices_guard() returns trigger language plpgsql as $$
begin
 if auth.uid() is null then return new; end if;   -- SQL Editor / mantenimiento directo
 if public.is_admin() then return new; end if;
 if new.user_id is distinct from old.user_id or new.device_id is distinct from old.device_id then
   raise exception 'Solo un administrador puede cambiar el usuario o el identificador de un equipo';
 end if;
 if new.authorized is distinct from old.authorized and not public.has_permission('dispositivos','edit') then
   raise exception 'No tienes permiso para autorizar o bloquear equipos';
 end if;
 return new;
end $$;

drop trigger if exists trg_app_devices_guard on public.app_devices;
create trigger trg_app_devices_guard before update on public.app_devices
  for each row execute function public.app_devices_guard();

-- ---------------------------------------------------------------
-- 5) Verificación: si algo no quedó cerrado, TODA la migración se revierte
-- ---------------------------------------------------------------
do $$
begin
 if has_table_privilege('anon','public.personas','select') then
   raise exception 'V001: anon todavía puede leer public.personas';
 end if;
 if exists(select 1 from pg_policies where schemaname='public' and 'anon' = any(roles)) then
   raise exception 'V001: todavía existen políticas RLS para anon';
 end if;
 if has_function_privilege('anon','public.admin_set_user_password(uuid,text)','execute') then
   raise exception 'V001: anon todavía puede ejecutar RPC administrativos';
 end if;
end $$;

commit;

-- Consulta de control (debe devolver 0 filas):
--   select schemaname, tablename, policyname, roles from pg_policies where 'anon' = any(roles);
