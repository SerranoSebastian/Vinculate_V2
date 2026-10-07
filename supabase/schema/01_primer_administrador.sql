-- ================================================================
-- PRIMER ADMINISTRADOR — solo para un proyecto Supabase NUEVO (sin perfiles)
-- Vincúlate SEDECO v2
--
-- Por qué existe: la app solo deja entrar a quien ya tiene perfil en
-- public.app_profiles, y el único que puede crear perfiles es un administrador.
-- Para el PRIMER administrador hay que crearlo desde aquí (SQL Editor).
-- La función bootstrap_first_admin() del esquema base necesita una sesión
-- iniciada (auth.uid()), que el SQL Editor no tiene; este script la sustituye.
--
-- Pasos:
--   1. Supabase → Authentication → Users → "Add user" → correo + contraseña
--      (marca "Auto Confirm User").
--   2. Cambia SOLO el correo de la línea marcada abajo por el que acabas de crear.
--   3. Ejecuta el script. Si ya existe algún perfil, se niega a hacer nada.
-- No modifica datos de personas/vacantes/vinculaciones.
-- ================================================================
do $$
declare
  v_email text := lower(trim('CAMBIA_ESTE_CORREO@ejemplo.com'));   -- <<< CAMBIA SOLO ESTA LÍNEA
  v_uid uuid;
  v_name text;
begin
  if exists (select 1 from public.app_profiles) then
    raise exception 'Ya existen perfiles en este proyecto: usa la pantalla Administración → Usuarios (este script es solo para el primero).';
  end if;
  select id, coalesce(raw_user_meta_data->>'display_name', email) into v_uid, v_name
    from auth.users where lower(email) = v_email;
  if v_uid is null then
    raise exception 'No existe ningún usuario con el correo "%" en Authentication → Users. Créalo primero y vuelve a ejecutar.', v_email;
  end if;
  insert into public.app_profiles(user_id, email, display_name, role, status)
    values (v_uid, v_email, v_name, 'admin', 'active');
  insert into public.app_permissions(user_id, module_key, can_view, can_create, can_edit, can_delete, can_export)
    select v_uid, m, true, true, true, true, true
    from unnest(array['inicio','personas','vacantes','vinculaciones','explorador','ridet','administracion',
                      'usuarios','dispositivos','prioridades','auditoria','respaldos']) m;
  raise notice 'Listo: % ahora es administrador.', v_email;
end $$;
