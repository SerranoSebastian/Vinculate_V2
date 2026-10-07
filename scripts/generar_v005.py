"""Genera supabase/migrations/V005_origen_del_dato.sql a partir de los CSV de correcciones de la v5.

Uso:
    python scripts/generar_v005.py CARPETA_CON_LOS_CSV [--base "Base de datos_Persona.csv"] [--destino ARCHIVO.sql]

Entradas (en la carpeta; NO se suben al repositorio porque traen nombres de personas):
  IMPUTACION_ANIOS_HISTORICOS_20260901.csv            → año asignado por imputación (anio_fuente = 'imputado')
  CORRECCIONES_ACADEMICAS_BALANCEADAS_20260901.csv    → institución asignada por balanceo (institucion_fuente = 'balanceado')
  CORRECCIONES_OFERTA_ACADEMICA_VERIFICADA_20260901.csv → ídem, por oferta educativa verificada

Seguridad del resultado:
  * El SQL contiene SOLO id_persona y el valor (año o institución). Ningún nombre, teléfono ni correo.
  * Cada UPDATE exige que el valor actual de la base coincida con el del CSV; si alguien ya corrigió ese
    dato a mano, la fila NO se etiqueta (sigue como 'registrado').
  * Si se pasa --base, se verifica ANTES de generar que los CSV coincidan con esa base (si no, aborta).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

DESTINO = Path(__file__).resolve().parents[1] / "supabase" / "migrations" / "V005_origen_del_dato.sql"
ARCHIVOS = {
    "imputados": "IMPUTACION_ANIOS_HISTORICOS_20260901.csv",
    "balanceadas": "CORRECCIONES_ACADEMICAS_BALANCEADAS_20260901.csv",
    "oferta": "CORRECCIONES_OFERTA_ACADEMICA_VERIFICADA_20260901.csv",
}


def _sql_texto(v: str) -> str:
    return "'" + str(v).replace("'", "''") + "'"


def _valores(pares: list[tuple[str, str]], entero: bool) -> str:
    filas = [f"    ({_sql_texto(i)}, {int(float(v)) if entero else _sql_texto(v)})" for i, v in pares]
    return ",\n".join(filas)


def main(carpeta: str, base: str | None, destino: Path = DESTINO) -> int:
    d = Path(carpeta)
    imp = pd.read_csv(d / ARCHIVOS["imputados"], dtype=str)[["id_persona", "Año_imputado"]].dropna()
    bal = pd.read_csv(d / ARCHIVOS["balanceadas"], dtype=str)[["id_persona", "institucion_nueva"]].dropna()
    ofe = pd.read_csv(d / ARCHIVOS["oferta"], dtype=str)[["id_persona", "institucion_nueva"]].dropna()
    inst = pd.concat([bal, ofe]).drop_duplicates("id_persona")
    if imp["id_persona"].duplicated().any():
        print("Hay IDs repetidos en el archivo de imputación.")
        return 1
    if base:
        b = pd.read_csv(base, dtype=str)
        ok_a = imp.merge(b[["id_persona", "Año"]], on="id_persona", how="left")
        ok_i = inst.merge(b[["id_persona", "Institución"]], on="id_persona", how="left")
        fallan_a = int((ok_a["Año"].astype(str).str.replace(".0", "", regex=False) != ok_a["Año_imputado"].astype(str)).sum())
        fallan_i = int((ok_i["Institución"] != ok_i["institucion_nueva"]).sum())
        print(f"Verificación contra la base: años que no coinciden = {fallan_a}; instituciones que no coinciden = {fallan_i}")
        if fallan_a or fallan_i:
            print("Los CSV no coinciden con la base indicada; revisa antes de generar la migración.")
            return 1
    pares_a = list(imp.itertuples(index=False, name=None))
    pares_i = list(inst.itertuples(index=False, name=None))

    sql = f"""-- ================================================================
-- V005 — ORIGEN DEL DATO: año e institución «registrados» vs. estimados   (decisión D5)
-- Vincúlate SEDECO v2        (archivo GENERADO por scripts/generar_v005.py — no editar a mano)
--
-- En la base hay datos que NO los capturó una persona, sino que se completaron en septiembre de 2026:
--   · {len(pares_a)} años de registro por IMPUTACIÓN histórica (se repartieron para completar años faltantes)
--   · {len(pares_i)} instituciones asignadas por BALANCEO / oferta educativa verificada
-- Esos valores se CONSERVAN tal cual (esta migración no cambia ningún dato). Solo se agregan dos
-- columnas que dicen de dónde viene cada valor, para que los reportes puedan mostrarlo y filtrarlo:
--   personas.anio_fuente         'registrado' (por defecto) | 'imputado'
--   personas.institucion_fuente  'registrado' (por defecto) | 'balanceado'
--
-- Cada UPDATE solo etiqueta la fila si el valor actual coincide con el que se asignó entonces;
-- si alguien ya lo corrigió, se queda como 'registrado'. Al final se informa cuántas filas se etiquetaron.
-- Esta migración contiene SOLO id_persona y el valor; ningún nombre ni dato de contacto.
-- Reversión: V005_rollback.sql
-- ================================================================
begin;

alter table public.personas add column if not exists anio_fuente        text not null default 'registrado';
alter table public.personas add column if not exists institucion_fuente text not null default 'registrado';

alter table public.personas drop constraint if exists personas_anio_fuente_check;
alter table public.personas add constraint personas_anio_fuente_check check (anio_fuente in ('registrado','imputado'));
alter table public.personas drop constraint if exists personas_institucion_fuente_check;
alter table public.personas add constraint personas_institucion_fuente_check check (institucion_fuente in ('registrado','balanceado'));

do $$
declare n_a integer; n_i integer; v_audit boolean;
begin
  -- Las ~800 etiquetas no deben inundar la auditoría con una fila por persona: se pausa el disparador de
  -- auditoría (V003, si existe) solo durante este bloque y se deja UNA fila resumen.
  v_audit := exists (select 1 from pg_trigger where tgname = 'trg_audit_personas' and tgrelid = 'public.personas'::regclass);
  if v_audit then alter table public.personas disable trigger trg_audit_personas; end if;

  update public.personas p set anio_fuente = 'imputado'
    from (values
{_valores(pares_a, True)}
    ) as v(id_persona, anio)
   where p.id_persona = v.id_persona and p.anio = v.anio and p.anio_fuente = 'registrado';
  get diagnostics n_a = row_count;

  update public.personas p set institucion_fuente = 'balanceado'
    from (values
{_valores(pares_i, False)}
    ) as v(id_persona, institucion)
   where p.id_persona = v.id_persona and p.institucion = v.institucion and p.institucion_fuente = 'registrado';
  get diagnostics n_i = row_count;

  if v_audit then alter table public.personas enable trigger trg_audit_personas; end if;
  insert into public.app_audit_log(email, action, detail)
  values ('(migración)', 'migration_V005', format('anio_fuente=imputado: %s filas; institucion_fuente=balanceado: %s filas', n_a, n_i));

  raise notice 'V005: % de {len(pares_a)} años etiquetados como imputados; % de {len(pares_i)} instituciones etiquetadas como balanceadas.', n_a, n_i;
end $$;

commit;

-- Verificación (no modifica nada):
--   select anio_fuente, count(*) from public.personas group by 1;         -- esperado: imputado={len(pares_a)} (si no hubo cambios manuales)
--   select institucion_fuente, count(*) from public.personas group by 1;  -- esperado: balanceado={len(pares_i)}
"""
    destino.write_text(sql, encoding="utf-8")
    print(f"Escrito {destino} ({len(pares_a)} años, {len(pares_i)} instituciones)")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(2)
    base_arg = args[args.index("--base") + 1] if "--base" in args else None
    destino_arg = Path(args[args.index("--destino") + 1]) if "--destino" in args else DESTINO
    sys.exit(main(args[0], base_arg, destino_arg))
