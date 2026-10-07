-- ================================================================
-- V008 — DISPONIBILIDAD DE PERSONAS PARA VINCULAR   (decisión D3)
-- Vincúlate SEDECO v2
--
-- Tabla NUEVA con una marca MANUAL por persona maestra («disponible para vincular»,
-- con una nota). No se deduce de ningún otro dato: hasta que alguien marque personas,
-- el indicador «Disponibles para vincular» del dashboard muestra «No disponible».
--
-- No hay llave foránea a personas porque id_persona_maestro se repite en esa tabla
-- (una fila por vinculación histórica); la app valida que la persona exista.
--
-- RLS (misma lógica que V002): leer = personas·ver · escribir = personas·editar ·
-- borrar = personas·eliminar, además de device_gate(). Si V003 está aplicada, se
-- conectan también sus disparadores de auditoría y de «actualizado_en».
-- Requiere V002. Reversión: V008_rollback.sql
-- ================================================================
begin;

do $$
begin
  if to_regprocedure('public.device_gate()') is null or to_regprocedure('public.has_permission(text,text)') is null then
    raise exception 'V008 requiere V002 (faltan has_permission/device_gate)';
  end if;
end $$;

create table if not exists public.persona_disponibilidad (
  id_persona_maestro text primary key,
  disponible         boolean not null,
  nota               text,
  actualizado_por    text,
  actualizado_en     timestamptz not null default now(),
  constraint persona_disponibilidad_maestro_check check (id_persona_maestro ~ '^PER-[0-9]{4,}$')
);

alter table public.persona_disponibilidad enable row level security;
drop policy if exists persona_disponibilidad_select on public.persona_disponibilidad;
drop policy if exists persona_disponibilidad_insert on public.persona_disponibilidad;
drop policy if exists persona_disponibilidad_update on public.persona_disponibilidad;
drop policy if exists persona_disponibilidad_delete on public.persona_disponibilidad;
create policy persona_disponibilidad_select on public.persona_disponibilidad for select to authenticated
  using (public.has_permission('personas','view') and public.device_gate());
create policy persona_disponibilidad_insert on public.persona_disponibilidad for insert to authenticated
  with check (public.has_permission('personas','edit') and public.device_gate());
create policy persona_disponibilidad_update on public.persona_disponibilidad for update to authenticated
  using (public.has_permission('personas','edit') and public.device_gate())
  with check (public.has_permission('personas','edit') and public.device_gate());
create policy persona_disponibilidad_delete on public.persona_disponibilidad for delete to authenticated
  using (public.has_permission('personas','delete') and public.device_gate());

revoke all on public.persona_disponibilidad from anon;
grant select, insert, update, delete on public.persona_disponibilidad to authenticated;

-- Disparadores de V003, solo si existen
do $$
begin
  if to_regprocedure('public.touch_actualizado_en()') is not null then
    execute 'drop trigger if exists trg_touch_persona_disponibilidad on public.persona_disponibilidad';
    execute 'create trigger trg_touch_persona_disponibilidad before update on public.persona_disponibilidad
             for each row execute function public.touch_actualizado_en()';
  end if;
  if to_regprocedure('public.audit_row_change()') is not null then
    execute 'drop trigger if exists trg_audit_persona_disponibilidad on public.persona_disponibilidad';
    execute 'create trigger trg_audit_persona_disponibilidad after insert or update or delete on public.persona_disponibilidad
             for each row execute function public.audit_row_change(''id_persona_maestro'')';
  end if;
end $$;

commit;
