-- ================================================================
-- V003 — AUDITORÍA EN SERVIDOR Y MARCA DE ACTUALIZACIÓN
-- Vincúlate SEDECO v2
--
-- 1) Triggers AFTER INSERT/UPDATE/DELETE en personas, vacantes y vinculaciones
--    que escriben en app_audit_log (usuario, acción, tabla, ID y NOMBRES de las
--    columnas cambiadas; nunca los valores, para no duplicar datos personales).
--    Así la auditoría no depende de que el cliente "se acuerde" de registrar
--    y no puede omitirse desde la API directa.
--      acciones: srv_insert · srv_update · srv_delete
-- 2) Trigger BEFORE UPDATE que mantiene `actualizado_en`: la app usa
--    (conteo, max(actualizado_en)) como versión del caché para no mostrar
--    datos obsoletos. Antes ese campo solo se llenaba al insertar.
--
-- No modifica filas existentes. Reversión: V003_rollback.sql.
-- Requiere V002 (usa request_device_id()).
-- ================================================================
begin;

do $$
begin
  if to_regprocedure('public.request_device_id()') is null then
    raise exception 'V003 requiere V002 (falta public.request_device_id)';
  end if;
end $$;

create or replace function public.touch_actualizado_en() returns trigger language plpgsql as $$
begin
  new.actualizado_en := now();
  return new;
end $$;

create or replace function public.audit_row_change() returns trigger
language plpgsql security definer set search_path=public as $$
declare
  v_old jsonb; v_new jsonb; v_id text; v_cols text; v_email text;
  v_uid uuid := auth.uid(); v_action text;
begin
  if tg_op = 'INSERT' then
    v_new := to_jsonb(new); v_id := v_new ->> tg_argv[0]; v_action := 'srv_insert';
  elsif tg_op = 'UPDATE' then
    v_old := to_jsonb(old); v_new := to_jsonb(new); v_id := v_new ->> tg_argv[0]; v_action := 'srv_update';
    select string_agg(n.key, ', ' order by n.key) into v_cols
      from jsonb_each(v_new) n join jsonb_each(v_old) o on o.key = n.key
     where n.key <> 'actualizado_en' and n.value is distinct from o.value;
    if v_cols is null then return null; end if;   -- UPDATE sin cambios reales
  else
    v_old := to_jsonb(old); v_id := v_old ->> tg_argv[0]; v_action := 'srv_delete';
  end if;
  select email into v_email from public.app_profiles where user_id = v_uid;
  insert into public.app_audit_log(user_id, email, action, detail, device_id)
  values (
    v_uid, coalesce(v_email, '(sistema)'), v_action,
    tg_table_name || ' ' || coalesce(v_id, '?') || case when v_cols is not null then ' · columnas: ' || v_cols else '' end,
    public.request_device_id()
  );
  return null;
end $$;

drop trigger if exists trg_touch_personas       on public.personas;
drop trigger if exists trg_touch_vacantes       on public.vacantes;
drop trigger if exists trg_touch_vinculaciones  on public.vinculaciones;
create trigger trg_touch_personas      before update on public.personas      for each row execute function public.touch_actualizado_en();
create trigger trg_touch_vacantes      before update on public.vacantes      for each row execute function public.touch_actualizado_en();
create trigger trg_touch_vinculaciones before update on public.vinculaciones for each row execute function public.touch_actualizado_en();

drop trigger if exists trg_audit_personas       on public.personas;
drop trigger if exists trg_audit_vacantes       on public.vacantes;
drop trigger if exists trg_audit_vinculaciones  on public.vinculaciones;
create trigger trg_audit_personas      after insert or update or delete on public.personas      for each row execute function public.audit_row_change('id_persona');
create trigger trg_audit_vacantes      after insert or update or delete on public.vacantes      for each row execute function public.audit_row_change('id_vacante');
create trigger trg_audit_vinculaciones after insert or update or delete on public.vinculaciones for each row execute function public.audit_row_change('id_vinculacion');

commit;
