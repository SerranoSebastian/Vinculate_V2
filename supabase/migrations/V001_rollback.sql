-- ================================================================
-- V001_rollback — Restaura el estado ANTERIOR a V001 (SQL maestro 2026-09-21)
--
-- ADVERTENCIA: este script REABRE las brechas que V001 cerró:
--   * `anon` vuelve a poder leer public.personas sin iniciar sesión.
--   * Quien tenga usuarios.edit vuelve a poder darse rol admin.
-- Úsalo solo si V001 provoca un problema operativo y mientras se corrige.
--
-- El texto de políticas y funciones está copiado literalmente de
-- supabase/schema/00_esquema_base.sql (mismas definiciones del SQL maestro 2026-09-21).
-- ================================================================
begin;

-- anon: privilegios por defecto de Supabase + política de "ping"
alter default privileges in schema public grant all on tables    to anon;
alter default privileges in schema public grant all on sequences to anon;
alter default privileges in schema public grant all on functions to anon;
grant all on all tables    in schema public to anon;
grant all on all sequences in schema public to anon;
grant all on all functions in schema public to anon;

grant select on public.personas to anon;
drop policy if exists personas_anon_ping on public.personas;
create policy personas_anon_ping on public.personas for select to anon using (true);

-- Equipos: quitar guardia y restaurar política original
drop trigger if exists trg_app_devices_guard on public.app_devices;
drop function if exists public.app_devices_guard();
drop policy if exists devices_insert on public.app_devices;
create policy devices_insert on public.app_devices for insert to authenticated with check(user_id=auth.uid() and public.is_active_user());

-- Perfiles y permisos: políticas originales (delegados con usuarios.* podían escribir directo)
drop policy if exists profiles_insert    on public.app_profiles;
drop policy if exists profiles_update    on public.app_profiles;
drop policy if exists profiles_delete    on public.app_profiles;
drop policy if exists permissions_insert on public.app_permissions;
drop policy if exists permissions_update on public.app_permissions;
drop policy if exists permissions_delete on public.app_permissions;
create policy profiles_insert on public.app_profiles for insert to authenticated with check(public.is_admin() or public.has_permission('usuarios','create'));
create policy profiles_update on public.app_profiles for update to authenticated using(public.is_admin() or public.has_permission('usuarios','edit')) with check(public.is_admin() or public.has_permission('usuarios','edit'));
create policy profiles_delete on public.app_profiles for delete to authenticated using(public.is_admin() or public.has_permission('usuarios','delete'));
create policy permissions_insert on public.app_permissions for insert to authenticated with check(public.is_admin() or public.has_permission('usuarios','edit'));
create policy permissions_update on public.app_permissions for update to authenticated using(public.is_admin() or public.has_permission('usuarios','edit')) with check(public.is_admin() or public.has_permission('usuarios','edit'));
create policy permissions_delete on public.app_permissions for delete to authenticated using(public.is_admin() or public.has_permission('usuarios','delete'));

-- RPC administrativos: definiciones originales
create or replace function public.admin_finalize_collaborator(p_email text,p_new_password text,p_display_name text) returns uuid language plpgsql security definer set search_path=public,auth,extensions as $$
declare v_email text:=lower(trim(coalesce(p_email,''))); v_uid uuid; v_name text:=trim(coalesce(p_display_name,''));
begin
 if not(public.is_admin() or public.has_permission('usuarios','create')) then raise exception 'No autorizado para crear usuarios'; end if;
 if v_email='' or position('@' in v_email)<=1 then raise exception 'Correo electrónico inválido'; end if;
 if p_new_password is null or length(p_new_password)<8 or length(p_new_password)>72 then raise exception 'La contraseña debe tener entre 8 y 72 caracteres'; end if;
 select id into v_uid from auth.users where lower(email)=v_email order by created_at desc limit 1;
 if v_uid is null then raise exception 'El usuario todavía no existe en Supabase Authentication. Reintenta el alta.'; end if;
 if v_name='' then v_name:=v_email; end if;
 if exists(select 1 from public.app_profiles where lower(email)=v_email and user_id<>v_uid) then raise exception 'Existe un perfil duplicado con este correo.'; end if;
 update auth.users set encrypted_password=extensions.crypt(p_new_password,extensions.gen_salt('bf')),email_confirmed_at=coalesce(email_confirmed_at,now()),raw_user_meta_data=coalesce(raw_user_meta_data,'{}'::jsonb)||jsonb_build_object('display_name',v_name),updated_at=now() where id=v_uid;
 insert into public.app_profiles(user_id,email,display_name,role,status) values(v_uid,v_email,v_name,'collaborator','active') on conflict(user_id) do update set email=excluded.email,display_name=excluded.display_name,role=case when public.app_profiles.role='admin' then 'admin' else 'collaborator' end,status='active',updated_at=now();
 insert into public.app_permissions(user_id,module_key,can_view,can_create,can_edit,can_delete,can_export,updated_at)
 select v_uid,m,(m='inicio'),false,false,false,false,now() from unnest(array['inicio','personas','vacantes','vinculaciones','explorador','ridet','administracion','usuarios','dispositivos','prioridades','auditoria','respaldos']) m on conflict(user_id,module_key) do nothing;
 return v_uid;
end $$;

create or replace function public.admin_replace_user_permissions(p_user_id uuid,p_permissions jsonb) returns void language plpgsql security definer set search_path=public as $$
declare item jsonb; mk text; cv boolean;
begin
 if not(public.is_admin() or public.has_permission('usuarios','edit')) then raise exception 'No autorizado para modificar permisos'; end if;
 if not exists(select 1 from public.app_profiles where user_id=p_user_id) then raise exception 'El perfil indicado no existe'; end if;
 if exists(select 1 from public.app_profiles where user_id=p_user_id and role='admin') then raise exception 'La matriz de un administrador no se modifica desde esta operación'; end if;
 if jsonb_typeof(p_permissions)<>'array' then raise exception 'Formato de permisos inválido'; end if;
 delete from public.app_permissions where user_id=p_user_id;
 for item in select value from jsonb_array_elements(p_permissions) loop
  mk:=trim(coalesce(item->>'module_key','')); if mk<>all(array['inicio','personas','vacantes','vinculaciones','explorador','ridet','administracion','usuarios','dispositivos','prioridades','auditoria','respaldos']) then continue; end if;
  cv:=coalesce((item->>'can_view')::boolean,false);
  insert into public.app_permissions(user_id,module_key,can_view,can_create,can_edit,can_delete,can_export,updated_at) values(p_user_id,mk,cv,cv and coalesce((item->>'can_create')::boolean,false),cv and coalesce((item->>'can_edit')::boolean,false),cv and coalesce((item->>'can_delete')::boolean,false),cv and coalesce((item->>'can_export')::boolean,false),now());
 end loop;
end $$;

create or replace function public.admin_set_user_password(p_user_id uuid,p_new_password text) returns void language plpgsql security definer set search_path=public,auth,extensions as $$
begin
 if not(public.is_admin() or public.has_permission('usuarios','edit')) then raise exception 'No autorizado'; end if;
 if p_new_password is null or length(p_new_password)<8 or length(p_new_password)>72 then raise exception 'La contraseña debe tener entre 8 y 72 caracteres'; end if;
 update auth.users set encrypted_password=extensions.crypt(p_new_password,extensions.gen_salt('bf')),email_confirmed_at=coalesce(email_confirmed_at,now()),updated_at=now() where id=p_user_id;
 if not found then raise exception 'Usuario no encontrado'; end if;
end $$;

create or replace function public.admin_update_user_account(p_user_id uuid,p_email text,p_display_name text,p_role text,p_status text) returns void language plpgsql security definer set search_path=public,auth,extensions as $$
declare v_email text:=lower(trim(coalesce(p_email,''))); v_name text:=trim(coalesce(p_display_name,''));
begin
 if not(public.is_admin() or public.has_permission('usuarios','edit')) then raise exception 'No autorizado para modificar cuentas'; end if;
 if v_email='' or v_email !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$' then raise exception 'Correo electrónico inválido'; end if;
 if p_role not in('admin','collaborator') then raise exception 'Rol inválido'; end if; if p_status not in('pending','active','disabled') then raise exception 'Estado inválido'; end if; if v_name='' then v_name:=v_email; end if;
 if exists(select 1 from auth.users where lower(email)=v_email and id<>p_user_id) or exists(select 1 from public.app_profiles where lower(email)=v_email and user_id<>p_user_id) then raise exception 'Ese correo ya pertenece a otra cuenta'; end if;
 if exists(select 1 from public.app_profiles where user_id=p_user_id and role='admin' and status='active') and (p_role<>'admin' or p_status<>'active') and (select count(*) from public.app_profiles where role='admin' and status='active')<=1 then raise exception 'No se puede desactivar o degradar al último administrador activo'; end if;
 update auth.users set email=v_email,email_confirmed_at=coalesce(email_confirmed_at,now()),raw_user_meta_data=coalesce(raw_user_meta_data,'{}'::jsonb)||jsonb_build_object('display_name',v_name),updated_at=now() where id=p_user_id; if not found then raise exception 'Usuario no encontrado en Authentication'; end if;
 update auth.identities set identity_data=coalesce(identity_data,'{}'::jsonb)||jsonb_build_object('email',v_email),updated_at=now() where user_id=p_user_id and provider='email';
 update public.app_profiles set email=v_email,display_name=v_name,role=p_role,status=p_status,updated_at=now() where user_id=p_user_id; if not found then raise exception 'Perfil Vincúlate no encontrado'; end if;
 if p_status='disabled' then update public.app_devices set authorized=false where user_id=p_user_id; end if;
end $$;

create or replace function public.admin_delete_user_account(p_user_id uuid) returns void language plpgsql security definer set search_path=public,auth as $$
begin
 if not(public.is_admin() or public.has_permission('usuarios','delete')) then raise exception 'No autorizado para eliminar cuentas'; end if;
 if p_user_id=auth.uid() then raise exception 'No puedes eliminar tu propia cuenta durante una sesión activa'; end if;
 if not exists(select 1 from public.app_profiles where user_id=p_user_id) then raise exception 'Perfil no encontrado'; end if;
 if exists(select 1 from public.app_profiles where user_id=p_user_id and role='admin' and status='active') and (select count(*) from public.app_profiles where role='admin' and status='active')<=1 then raise exception 'No se puede eliminar al último administrador activo'; end if;
 delete from public.app_priority_notifications where user_id=p_user_id; delete from public.app_priorities where created_by=p_user_id; delete from public.app_audit_log where user_id=p_user_id; delete from public.app_permissions where user_id=p_user_id; delete from public.app_devices where user_id=p_user_id; delete from public.app_profiles where user_id=p_user_id; delete from auth.users where id=p_user_id;
end $$;

revoke all on function public.admin_finalize_collaborator(text,text,text) from public;
revoke all on function public.admin_replace_user_permissions(uuid,jsonb) from public;
revoke all on function public.admin_set_user_password(uuid,text) from public;
revoke all on function public.admin_update_user_account(uuid,text,text,text,text) from public;
revoke all on function public.admin_delete_user_account(uuid) from public;
grant execute on function public.admin_finalize_collaborator(text,text,text),public.admin_replace_user_permissions(uuid,jsonb),public.admin_set_user_password(uuid,text),public.admin_update_user_account(uuid,text,text,text,text),public.admin_delete_user_account(uuid) to authenticated;

commit;
