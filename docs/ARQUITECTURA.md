# Arquitectura

## Capas (cada una solo conoce a la de abajo)

```
vistas/        pantallas Streamlit; no hablan con Supabase ni contienen reglas de negocio
components/    piezas visuales reutilizables: ui (KPI, tablas, confirmaciones, exportar), charts, filtros, paneles, avisos
services/      reglas de negocio y casos de uso; reciben la `sesion` de forma explícita (no leen variables globales)
repositories/  ÚNICO lugar que llama a Supabase (PostgREST/RPC); traduce errores a mensajes entendibles
core/          Python puro (sin Streamlit ni Supabase): limpieza, IDs, catálogos, vigencia, RIDET, mapa; 100 % probable con pytest
auth/          sesión, permisos (`sesion.puede(modulo, accion)`), identificador de equipo
```

Regla práctica: si un cambio de interfaz obliga a tocar `repositories/`, algo está mal ubicado.

## Modelo de datos (sin cambios sobre la v5)

Tablas: `personas` (una fila por **vinculación histórica**), `vacantes`, `vinculaciones`, `historial_cargas`, `catalogo_*`,
`app_profiles`, `app_permissions`, `app_devices`, `app_audit_log`, `app_priorities` (+ `app_settings` de V002 y las tablas/columnas opcionales de V004–V008).

**Persona maestra.** `id_persona` identifica *un registro histórico*; `id_persona_maestro` (`PER-0001`…) identifica a *la persona*.
Un mismo maestro puede tener varias filas. Todo conteo de «personas» usa maestros únicos (593); todo conteo de «vinculaciones históricas»
usa filas (697). La interfaz lo rotula siempre así.

## Permisos

12 módulos × 5 acciones (`view/create/edit/delete/export`):
`inicio, personas, vacantes, vinculaciones, explorador, ridet, administracion, usuarios, dispositivos, prioridades, auditoria, respaldos`.

Se aplican en **dos lugares**: la interfaz (qué se muestra) y la base (RLS, V002: lo que realmente se puede leer/escribir). Cualquier acción
exige `view` del mismo módulo. Un delegado con `usuarios.edit` no puede darse rol de administrador ni otorgar permisos que no tiene (V001).
El mapa y el RIDET dependen de `ridet.view`; cada capa del mapa además exige el permiso de los datos que dibuja.

## Sesión y equipo

- Un cliente de Supabase **por sesión de navegador** (`st.session_state`), autenticado con el JWT del usuario: RLS aplica de verdad.
  Ningún cliente se comparte entre usuarios (no hay `cache_resource` con clientes).
- Solo llave pública. `config/settings.py` detecta una `service_role`/`sb_secret_…` y **bloquea el arranque**.
- Cinco intentos fallidos de login → espera de 60 s. La sesión se **revalida** cada pocos segundos (perfil, permisos, equipo), así que un
  cambio del administrador surte efecto sin que la persona vuelva a entrar.
- Equipo = cookie del navegador `vinculate_device` (UUID) enviada como encabezado `x-device-id`. Ver DESPLIEGUE.md §6.

## Caché sin datos obsoletos

`st.cache_data` es global entre sesiones, por eso la llave siempre incluye `(id de usuario, tabla, huella)`, donde la huella es
`conteo | máx(actualizado_en)` de la tabla (consulta barata, como máximo cada 4 s por sesión). Un guardado propio descarta la huella al instante; el guardado
de otra persona cambia la huella y la siguiente lectura recarga sola (V003 mantiene `actualizado_en` también en las ediciones).
El botón «🔄 Actualizar datos y permisos» limpia todo a demanda.

## Escritura de datos

Todo guardado pasa por `services/guardado.py`: valida y normaliza (`core/`), pide confirmación en acciones destructivas, escribe solo columnas
que existen (las opcionales de V004/V005/V007 se detectan), registra `historial_cargas` y la auditoría. Las cargas masivas muestran una **vista previa**
con errores por fila antes de guardar y se pueden **deshacer** dentro de la sesión (borra exactamente lo insertado).

## Territorio

- Región RIDET: 6 regiones; `core/ridet.py` trae el reparto de los 60 municipios. La lista de **empresas del RIDET** (307) sale del PDF oficial con
  `scripts/extraer_ridet.py`, que **se niega a escribir** si los conteos por región no coinciden con los totales impresos en el documento.
  Municipio y parque industrial de cada empresa **no** se infieren (el orden de lectura del PDF los vuelve ambiguos).
- Clasificación de las empresas con vacantes: coincidencia exacta (con alias documentados) contra esa lista; lo ambiguo o sin coincidencia queda
  como «Pendiente de asignar». Nunca se asigna por parecido.
- Mapa: por **municipio**, no por coordenada, dibujado con Plotly `Choroplethmap` y fondo blanco incluido (**sin descargar teselas ni archivos desde un CDN**: funciona en redes que bloqueen sitios externos). La geometría debe ser la oficial de INEGI y pasa por una validación estricta (entidad 29, exactamente 60,
  nombres contra el catálogo). No se geocodifica nada y la falta de coordenadas nunca bloquea una pantalla (`latitud/longitud` son opcionales y hoy no se usan).
  Lo que no tiene municipio, está fuera de Tlaxcala o no se reconoce se informa **aparte**; nada se reparte ni se estima.

## Calidad de los datos mostrados

- Nunca se muestra `NaN`, `None` ni trazas de Python: faltantes → «Información no disponible»; errores → mensajes en español (`repositories/errores.py`).
- Los años imputados y las instituciones balanceadas (V005) se **etiquetan** y hay interruptor para ver «solo años registrados».
- «Vacantes vigentes» = estado Activa **y** sin fecha de cierre vencida (V007). «Disponibles para vincular» = marca manual (V008); sin ella, «No disponible».

## Pruebas

| Suite | Qué cubre |
|---|---|
| `tests/test_sql_migraciones.py` | Migraciones y rollbacks contra PostgreSQL real: RLS, brechas de V001, auditoría, idempotencia, V005 con datos reales anonimizados, primer administrador. |
| `tests/test_guardado.py`, `test_servicios_admin.py` | Servicios con un Supabase falso en memoria (`tests/fakes.py`). |
| `tests/test_paginas.py`, `test_entrada.py` | Cada página y cada apartado dentro del runtime de Streamlit (`AppTest`), login y bloqueo, con datos sintéticos. |
| `tests/test_territorio.py` | RIDET, mapa, estado del sistema, empresas, disponibilidad. |

Verificado con Streamlit 1.52 y 1.65, pandas 2.3 y 3.0.
