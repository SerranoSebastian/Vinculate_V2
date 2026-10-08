# Migraciones de Supabase

Reglas que cumplen **todas**: no borran ni renombran tablas, columnas ni IDs existentes · no cambian ni inventan datos
(salvo lo que se indica expresamente en V005, que solo *etiqueta*) · van dentro de una transacción (si falla, no queda nada a medias) ·
son re-ejecutables sin duplicar nada · tienen un `_rollback.sql` · están probadas contra un PostgreSQL real
(`tests/test_sql_migraciones.py`, 77 pruebas).

**Cómo se ejecutan:** a mano, en *Supabase → SQL Editor*, **primero en un proyecto de prueba**. La app solo *lee* qué migraciones
están aplicadas (*Administración → Estado del sistema*) y funciona, con menos funciones, si falta alguna de las opcionales (V004, V005, V007, V008).

Orden de aplicación: **V001 → V002 → V003 → V004 → V005 → V007 → V008 → V009**. Orden de reversión: el inverso.
Dependencias: V003 y V008 requieren V002 (la migración se detiene con un mensaje claro si falta).

---

## V001 — Cierre de brechas de seguridad  *(obligatoria)*
**Problema que corrige (comprobado en el SQL maestro de la v5):** cualquiera con la URL y la llave pública, *sin iniciar sesión*, podía leer
la tabla `personas` completa (nombre, teléfono, correo); y quien tuviera `usuarios.edit` podía darse rol administrador con un UPDATE directo.

| Hace | Efecto |
|---|---|
| Retira a `anon` todo acceso al esquema `public` | Sin sesión no se lee nada. |
| Altas/cambios/bajas directas en `app_profiles` y `app_permissions` solo para administradores | Los delegados usan los RPC, que traen sus propias reglas. |
| Reescribe los 5 RPC administrativos | Un no-admin no puede dar rol admin, tocar cuentas admin, restablecer su contraseña ni darse permisos que no tiene. |
| `admin_delete_user_account` ya no borra `app_audit_log` | La auditoría se conserva. |
| `app_devices`: nadie registra su equipo como autorizado | Autorizar exige administrador o `dispositivos.edit`. |

**Verificar** (SQL Editor): `select has_table_privilege('anon','public.personas','select');` → debe dar `false`. (La app lo muestra como «No verificable»: con la llave pública no puede inspeccionar privilegios.)
**Revertir:** `V001_rollback.sql` — **reabre** las brechas anteriores; úsalo solo como emergencia.

## V002 — RLS por permiso  *(obligatoria)*
Antes: una política «cualquier usuario activo puede todo». Ahora la base aplica la matriz módulo × acción:
`personas / vacantes / vinculaciones` → SELECT=`view`, INSERT=`create`, UPDATE=`edit`, DELETE=`delete`;
`historial_cargas` se lee e inserta pero no se actualiza (es un registro histórico; borrar exige `administracion.delete`); catálogos se leen por cualquier usuario activo y se escriben con
`administracion.edit` (empresas también con `vacantes.create/edit`).
Crea `app_settings` y las funciones `has_any_permission`, `request_device_id`, `device_gate`. La validación de equipo en la base queda
**apagada** (`enforce_device_rls = 'false'`).
**Verificar:** un usuario con solo `inicio.view` no puede leer `personas` ni con la API directa.
**Revertir:** `V002_rollback.sql` (si V003 está aplicada, ejecuta antes `V003_rollback.sql`).

## V003 — Auditoría en servidor y marca de actualización  *(recomendada)*
Disparadores en `personas`, `vacantes`, `vinculaciones`: cada alta/cambio/baja se escribe en `app_audit_log` (usuario, acción, tabla, ID y
**nombres** de las columnas cambiadas, nunca los valores, para no duplicar datos personales). Otro disparador mantiene `actualizado_en`:
la app usa `(conteo, max(actualizado_en))` como versión del caché para no mostrar datos viejos.
No modifica filas existentes.
**Verificar:** `select count(*) from pg_trigger where not tgisinternal and (tgname like 'trg_audit_%' or tgname like 'trg_touch_%') and tgrelid in ('public.personas'::regclass,'public.vacantes'::regclass,'public.vinculaciones'::regclass);` → `6` (la app tampoco puede comprobarlo y dice «No verificable»).
**Revertir:** `V003_rollback.sql` (las filas de auditoría ya escritas se conservan).

## V004 — Ubicación de empresas y excepción de municipio por vacante  *(opcional)*
Columnas nuevas y opcionales: `catalogo_empresas.{municipio, cve_mun, direccion, codigo_postal, latitud, longitud, ubicacion_fuente, ubicacion_actualizada}`,
`catalogo_municipios_tlaxcala.cve_mun`, `vacantes.municipio_excepcion`, con restricciones de formato (CP de 5 dígitos, clave de 3 dígitos,
coordenadas dentro de México y siempre en pareja, fuente ∈ manual|ridet|importada|geocodificada). **No rellena nada y no geocodifica.**
La clave INEGI de cada municipio se llena con `geo/cve_mun_municipios.sql` (lo genera `scripts/preparar_geometria.py`).
**Revertir:** `V004_rollback.sql` (se pierde lo capturado después; el archivo trae las consultas de respaldo).

## V005 — Origen del dato (año e institución)  *(opcional; archivo generado)*
En la base hay 534 años de registro asignados por **imputación** y 259 instituciones asignadas por **balanceo** / oferta educativa
(septiembre 2026). Esta migración **conserva esos valores** y solo agrega `personas.anio_fuente` y `personas.institucion_fuente`
(`registrado` por omisión), etiquetando las filas afectadas para que los reportes puedan decir «dato estimado» y ofrecer
«solo años registrados».
Seguridad: cada UPDATE exige que el valor actual coincida con el asignado entonces (si alguien ya lo corrigió, no se etiqueta);
solo contiene `id_persona` y el valor; pausa el disparador de auditoría y deja **una** fila resumen (`migration_V005`).
**Verificar:** `select anio_fuente, count(*) from personas group by 1;` → `imputado = 534`; `select institucion_fuente, count(*) …` → `balanceado = 259`.
En un proyecto sin esos datos (Camino B) no etiqueta nada. Si tus CSV cambian, se regenera con `scripts/generar_v005.py`.
**Revertir:** `V005_rollback.sql` (los años e instituciones no cambian; solo se pierde la etiqueta).

## V007 — Vigencia de vacantes  *(opcional)*
Agrega `vacantes.fecha_cierre` (opcional). Una vacante es **vigente** si su estado es «Activa» **y** no tiene fecha de cierre vencida.
No se rellena ni se cambia ningún estado automáticamente: las vacantes «Activa» de 2024 se revisan una por una en *Vacantes → 🕒 Revisión de vigencia*.
La restricción `fecha_cierre >= fecha` se crea `NOT VALID`: rige para lo nuevo y nunca rechaza filas históricas.
**Revertir:** `V007_rollback.sql` (se pierden las fechas capturadas; el archivo trae la consulta de respaldo).

## V008 — Disponibilidad de personas para vincular  *(opcional)*
Tabla nueva `persona_disponibilidad` (una marca **manual** por persona maestra + nota). No se deduce de ningún otro dato: mientras nadie
marque personas, el indicador «Disponibles para vincular» dice «No disponible». RLS con la misma lógica de V002 (leer = personas·ver,
escribir = personas·editar, borrar = personas·eliminar) más el candado de equipo; si V003 está aplicada, también auditoría.
**Revertir:** `V008_rollback.sql` (se pierden las marcas; respaldo: `select * from persona_disponibilidad;`).

## V009 — Unificar redacción de sexo y escolaridad  *(opcional; corrige datos)*
**Modifica datos**, por eso trae respaldo propio. Solo cambia `personas.sexo` (`MASCULINO`/`masculino`/`Hombre` → `Masculino`; `FEMENINO`/`femenino`/`Mujer` → `Femenino`)
y la primera letra de `personas.escolaridad` (`superior` → `Superior`). No toca IDs, nombres ni ninguna otra columna; cualquier otro valor (p. ej. `Otro`, vacíos) queda igual.
Antes de cada cambio copia el valor original a `respaldo_v009_redaccion` (solo administradores). Re-ejecutable. Pausa la auditoría fila por fila y deja **una** fila resumen.
**Antes de ejecutarla** el archivo trae una consulta que muestra cuántas filas cambiaría (no modifica nada).
La app **ya unifica estas variantes al dibujar gráficas** y al cargar archivos nuevos, así que V009 solo sirve para dejar también *la base* limpia.
**Revertir:** `V009_rollback.sql` (devuelve cada valor al original; respeta lo que alguien haya corregido después).

---

## V006 — diferida
Estaba prevista para vistas SQL de analítica. Se difiere: con el volumen actual (≈700 filas) la app calcula los indicadores en Python con
los datos que ya lee con RLS, y una vista añade superficie de seguridad (las vistas de Postgres ignoran RLS salvo que se declaren con
`security_invoker`). Se retoma si el volumen lo justifica.

## Si necesitas deshacer todo
Ejecuta los `_rollback.sql` en este orden: **V009 → V008 → V007 → V005 → V004 → V003 → V002 → V001**. Antes, respalda lo que se capturó después de aplicarlas
(los archivos indican cómo). V001_rollback reabre las brechas de seguridad: solo como emergencia.
