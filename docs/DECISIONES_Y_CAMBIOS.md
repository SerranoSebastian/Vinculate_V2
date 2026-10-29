# Decisiones, cambios respecto a la v5 y pendientes

## 1. Decisiones adoptadas (D1–D6)

| # | Decisión | Cómo quedó |
|---|---|---|
| D1 | Aplicar V001 (cierre de brechas) | Entregada como archivo. Se prueba primero en un proyecto de **prueba** y luego en el real; la ejecuta una persona, nunca la app. |
| D2 | Servidor compartido (Streamlit Cloud) | El identificador de equipo vive en el **navegador** (localStorage/cookie, entregado por URL) y se valida en RLS (V002, opcional y apagado por defecto). Control suave. |
| D3 | «Disponible para vincular» | **Marca manual** por persona (V008). Hasta que alguien marque personas, el indicador dice «No disponible». |
| D4 | Vigencia de vacantes | `fecha_cierre` (V007): vigente = «Activa» y sin cierre vencido. Las «Activa» de 2024 se revisan a mano en *Vacantes → Revisión de vigencia*; nada cambia solo. |
| D5 | Años e instituciones asignados por limpieza | Se **conservan** (534 años imputados, 259 instituciones balanceadas) pero **etiquetados** (V005), con interruptor «solo años registrados». |
| D6 | Ubicación de empresas | Municipio por empresa: extracción del PDF del RIDET + captura manual (V004). Sin geocodificación masiva. |

## 2. Cambios de comportamiento respecto a la v5 (conviene avisar a los usuarios)

1. **Sin disco local.** Streamlit Cloud tiene sistema de archivos efímero: ya no hay carpeta `data/` ni respaldo CSV automático antes de cada cambio.
   Supabase es la única fuente; los respaldos son **descargas bajo demanda** (*Administración → Respaldos*, ZIP con CSV reimportables) y la auditoría
   en servidor (V003) deja constancia de cada cambio. Recomendación: descargar un respaldo antes de cargas grandes y activar los respaldos de Supabase.
2. **Cargas con duplicados.** Cuando un ID ya existía, la v5 le asignaba un ID nuevo al registro entrante, así que importar dos veces el mismo
   archivo duplicaba filas. La v2 **omite** lo que ya existe (mismo ID, o misma vacante), **nunca sobrescribe** y te informa cuántos fueron en la vista previa.
   La columna `historial_cargas.duplicados_actualizados` conserva su nombre (no se renombra nada) pero ahora cuenta los **omitidos**.
3. **Deshacer** la última carga disponible dentro de la sesión (borra exactamente lo insertado, con confirmación).
4. **Permisos:** cualquier acción exige también `view` del mismo módulo (no se puede crear lo que no se ve). Un usuario con `create/edit` sin `view` quedaría sin acceso útil; la matriz lo impide al guardar.
5. **Mapa y RIDET** requieren `ridet.view`; cada capa del mapa exige además el permiso de sus datos.
6. **Equipos:** identificador guardado en el navegador en vez de archivo local (ver DESPLIEGUE.md §6). Un navegador nuevo de un colaborador queda «pendiente» hasta que un administrador lo autoriza.
7. **Bloqueo de login:** 5 intentos fallidos → 60 s de espera (por sesión de navegador).
8. **Gráficas (08/10/2026):** en las gráficas de tipo de vinculación, «Prácticas profesionales» + «Servicio social» se muestran juntas y «Atención» + «Inserción laboral» también; las tablas, filtros, fichas y exportaciones conservan los cuatro tipos. Las gráficas cuentan juntas las variantes de redacción («MASCULINO»/«Masculino»); los datos solo se corrigen con V009 (opcional) o al cargar archivos nuevos.
9. **Dato faltante (12/10/2026):** todas las formas de «sin dato» (vacío, «Indefinido», «Sin información», «Sin dato», «Información no disponible») se muestran con **una sola etiqueta**, `SIN_DATO = "Indefinido"` en `core/constantes.py` (cambiarla ahí la cambia en toda la app). Aplica a gráficas, tablas, filtros, fichas y el detalle de cada barra. Los indicadores («No disponible») conservan su texto porque significan «todavía no se puede calcular». V010 (opcional) deja también la base con una sola forma.
10. **Interfaz:** navegación lateral por secciones, búsqueda global, centro de avisos, componentes unificados. Mismos módulos y mismos nombres de tablas/columnas.

## 3. Lo que NO se hizo y por qué

- **V006 (vistas SQL):** diferida; ver MIGRACIONES.md.
- **Mapa dibujado (resuelto el 07/10/2026):** `geo/tlaxcala_municipios.geojson` se generó del AGEM 2026 de INEGI. Antes requería la geometría oficial de INEGI, que no se pudo descargar desde el entorno donde se construyó el proyecto. Está **todo listo**
  (validación estricta + `scripts/preparar_geometria.py` + `geo/LEEME.md`); mientras no esté el archivo, se muestra el ranking con los mismos datos.
- **Geocodificación:** no se hizo ni se hará de forma masiva (no hay coordenadas inventadas; la ubicación es por municipio).
- **Municipio y parque industrial de las 307 empresas del RIDET:** no se infieren automáticamente (el PDF es ambiguo en ese punto); solo la **región**, que sí es confiable.
- **Ninguna migración se ejecutó contra Supabase** y la app nunca se conectó a tu base real: todo se probó con PostgreSQL local, un Supabase simulado y datos sintéticos.
- **Subida a GitHub:** el entorno no tiene tu cuenta de GitHub enlazada, así que el repositorio queda listo para que lo subas tú (DESPLIEGUE.md §3).

## 4. Límites conocidos

- El control de equipo es **suave**: identifica un navegador, no lo autentica.
- Con *Allow new users to sign up* encendido (necesario para que la app dé de alta colaboradores), cualquiera con la URL y la llave pública puede crear un usuario en Authentication,
  pero **sin perfil activo no puede leer ni escribir nada** (V001 + V002). Revisa periódicamente *Authentication → Users*.
- Los indicadores se calculan en Python sobre las filas que Supabase entrega (≈700 hoy). Con decenas de miles de filas habría que mover agregaciones a la base (V006).
- `RIDET.pdf` pesa ~45 MB en el repositorio; si más adelante molesta, se puede alojar aparte.

## 5. Pendientes que necesitan revisión humana (no son bugs; son decisiones de negocio)

1. **Proyecto Supabase anterior:** revisar qué proyecto es el «real» y probar primero en uno de prueba (D1).
2. **Vacantes «Activa» de 2024 (167 en total):** decidir una por una en *Revisión de vigencia* o capturar la `fecha_cierre`.
3. **«Disponible para vincular»:** definir quién marca y con qué criterio (la v2 solo da la herramienta).
4. **RIDET:** revisar la extracción (307 empresas; por región: Centro-Sur 82, Sur 78, Centro-Norte 75, Oriente 39, Norte 20, Poniente 13) y las **5 empresas con vacantes
   sin municipio** (UMÁ RM3, EC Grupo San Luis, Stripseel, DDEQSA, MJCR). Confirmar con quien elaboró el RIDET el caso **Altzayanca**: el encabezado de Oriente dice
   «7 municipios» y no lo nombra, pero el cuerpo le asigna zona, empresa y planteles; aquí se cuenta en Oriente para que los 60 municipios queden en una región.
6. **Versión de Streamlit en producción:** el proyecto declara `streamlit>=1.52,<2` (probado en 1.52 y 1.65).

## Mapa único con capas (personas + empresas)
- Un solo mapa con casillas «Personas» y «Empresas»; reemplaza el selector entre mapas.
- Empresas: un punto por empresa en su latitud/longitud reales (V004, sin migración nueva). Nunca se estiman coordenadas: sin coordenadas = se listan aparte; con coordenadas inválidas (fuera de México, invertidas, una sola) = se listan con el problema.
- Distinción entre empresas de la misma zona: color propio por empresa, tamaño por vacantes, leyenda que oculta/muestra, filtro, «Acercar a» y separación visual opcional (~40 m) de coordenadas idénticas; el hover siempre muestra la coordenada real.
- Captura rápida de coordenadas en Vacantes → Empresas (se puede pegar «lat, lon» de Google Maps); respeta permisos y auditoría.
- Los fondos CARTO/OSM piden teselas al navegador; «Sin fondo» no depende de ningún servidor externo.

## Ayudas ❓ en el Inicio
- Cada indicador y gráfica del Inicio tiene un ❓ que muestra su explicación al pasar el mouse (o al tocarlo / enfocarlo con teclado). Se quitaron los recuadros «Fuente, significado e interpretación» del Inicio.
- Todos los textos viven en un solo archivo: `vinculate/config/ayudas.py` (diccionario `AYUDAS`). Para cambiar una explicación solo se edita ese texto; no se toca la lógica ni los datos.
- Reglas de redacción (las revisa `tests/test_ayudas.py`): usar siempre «vinculación», lenguaje para personas ajenas al programa y nada de avisos internos de pendientes o revisiones.
- Para agregar una ayuda nueva: añadir su texto en `AYUDAS` y pasar `info="clave"` a `ui.kpi(...)` o llamar `ui.ayuda_grafica("clave")` antes de la gráfica.

## Ayudas ❓ en el Mapa territorial
- Mismo mecanismo que en el Inicio: los 8 indicadores, las casillas «Personas»/«Empresas», el interruptor de separar empresas, el mapa y las tres tablas (municipios, empresas sin coordenadas, coordenadas con problema) tienen su ❓.
- Los textos están en `vinculate/config/ayudas.py`, claves que empiezan con `mapa.`. Se quitó el recuadro «Fuente, significado e interpretación» del mapa.
- En el mapa el ❓ va en su propia línea sobre la gráfica (esa esquina la ocupan los botones de zoom); las casillas e interruptores usan la ayuda nativa de Streamlit con el mismo texto.

## Ayudas ❓ en RIDET
- Las cinco vistas de RIDET (General, Regiones, Empresas y vacantes, Estadísticas) tienen su ❓: 11 indicadores, 2 gráficas y las tablas e imágenes del documento. Se quitaron los recuadros «Fuente, significado e interpretación».
- Textos en `vinculate/config/ayudas.py`, claves que empiezan con `ridet.`. La explicación de los criterios de asignación de región (por municipio, coincidencia exacta, alias, parcial, ambigua) está en `ridet.emp_tabla`.
- La observación sobre los municipios del documento (Altzayanca) y las etiquetas de criterio de la tabla no se modificaron.

## Ayudas ❓ en Personas
- Personas ya tiene ❓ en el Análisis completo (Resumen, Evolución anual, Recurrencia y Perfil: 6+3+2+4+5 elementos), en la tabla del Directorio, en los 4 indicadores de la ficha de persona, en los 3 indicadores de la Carga Excel/CSV y en la tabla de Editar / eliminar. Se quitaron los recuadros «Fuente, significado e interpretación» de esta página.
- Textos en `vinculate/config/ayudas.py`, claves que empiezan con `personas.`. Las pruebas (`tests/test_ayudas.py`) revisan `personas.py` y `ficha.py`.
- Los formularios de Nueva vinculación y Editar no llevan ❓ porque no muestran cifras.

## Ayudas ❓ · Vacantes y empresas (2026-10-19)

- Textos en `vinculate/config/ayudas.py`, claves `vacantes.*` (33): KPIs de Análisis, Empresas, Carga y Vigencia; gráficas, mapa de calor, informe automático, tablas (Buscador, Empresas, Editar, Vigencia), captura de ubicación, editor de coordenadas, formulario de alta y umbral de vigencia.
- Se quitó el expander `ui.explicacion` de Análisis. Sin cambios de base de datos ni de permisos.
- `tests/test_ayudas.py` valida que cada clave usada tenga texto, que todo texto definido se use y que no aparezcan palabras de pendientes/revisión.

## Ayudas ❓ · Vinculaciones (2026-10-19)

- Textos en `vinculate/config/ayudas.py`, claves `vinculaciones.*` (23): 7 indicadores superiores, formulario de nuevo seguimiento, tabla de editar, gráficas y 4 indicadores de Estadísticas, tabla de personas, selector del historial y tabla de exportación. Las fichas del historial reutilizan las claves `personas.ficha_*`.
- Se quitó el expander `ui.explicacion` de la parte superior. Sin cambios de base de datos ni permisos.

## Administración: filtro por usuario y eliminar prioridades (2026-10-21)

- Computadoras y Auditoría tienen selector «Usuario» (como Permisos): por defecto el usuario en sesión, con la opción «Todos los usuarios». La auditoría filtra en la consulta (`RepoAdmin.auditoria(uid=…)`), así que cada usuario ve sus últimos 1,000 movimientos.
- Prioridades: se pueden eliminar una o todas las atendidas, con confirmación y auditoría (`priority_deleted`). Requiere el permiso `prioridades.delete`; la política RLS `priorities_delete` ya existía, no hay migración.

## Instituciones educativas en el mapa (2026-10-21)

- **Migración V011** (opcional, solo agrega): `tipo`, `municipio`, `direccion`, `codigo_postal`, `latitud`, `longitud`, `ubicacion_fuente`, `ubicacion_actualizada` en `catalogo_instituciones`. Reversión en `V011_rollback.sql`. Sin cambios de RLS.
- **Quién captura:** solo administración (`administracion.edit`, igual que la RLS del catálogo), en *Administración → Instituciones*: tipo (Universidad/Escuela), municipio y coordenadas, con pegado «lat, lon» de Google Maps.
- **Qué se lista:** solo instituciones que ya tienen al menos una persona asociada (la columna `Institución` de personas); «Personas» cuenta personas distintas y se informa cuántas fueron asignadas por balanceo. La fila del catálogo se crea al guardar si no existía.
- **Mapa:** casilla «Instituciones educativas» (apagada de inicio), filtro por tipo y por institución, «Acercar a», color propio por institución (paleta distinta a empresas) y contorno oscuro; clic abre el detalle con sus personas. Sin coordenadas no se dibuja y se lista aparte; nada se estima.
- Sin V011 la app sigue funcionando: la casilla avisa y *Estado del sistema* muestra V011 como pendiente.

## Empresas nuevas y empresas sin vacantes en el mapa (2026-10-29)

- **Alta de empresas:** Vacantes → Empresas → «Agregar una empresa nueva» (permiso `vacantes.create`, igual que la RLS del catálogo). Solo el nombre es obligatorio; sector, municipio, dirección, C.P. y coordenadas son opcionales. No permite duplicados (sin importar mayúsculas ni acentos), se audita (`empresa_creada`) y no requiere migración (usa las columnas de V004 solo si se captura ubicación).
- **Empresas sin vacantes:** el directorio (tabla de Empresas, editor de coordenadas y Mapa) ahora suma las empresas con vacantes, las del catálogo, la lista fija de la app y las que ya tienen seguimientos de vinculación. Antes solo salían las que tenían vacantes o fila en el catálogo, por eso faltaban. Nada se estima: sin coordenadas no se dibujan y se listan aparte.
- El editor de coordenadas ganó búsqueda por nombre y el interruptor «Solo sin coordenadas».
- Las empresas dadas de alta aparecen en los formularios de Nueva vacante, Editar vacante y Vinculaciones (`empresas.opciones`).

## Años de vinculaciones unificados (2026-10-29)

- **App:** ya no distingue año «registrado» y «estimado»: la gráfica de evolución anual tiene una sola serie «Vinculaciones», se quitó el filtro «Excluir registros con año estimado», el sufijo «(estimado)» y la etiqueta «Incluye año estimado» de la ficha, y la nota de barras rayadas. Funciona con o sin la migración.
- **Base (V012, opcional, con respaldo y reversión):** `anio_fuente` de `imputado` a `registrado`. El año en sí no se toca. La procedencia queda en `respaldo_v012_anio_fuente`. `institucion_fuente` (balanceo) queda igual.

## Explorador con filtros por columna y menú sin «Búsqueda»

- **Explorador:** cada base (Personas, Registros históricos, Vacantes, Seguimientos) tiene ahora filtros por columna, como en el Inicio ejecutivo (municipio, sexo, escolaridad, carrera, institución, año, estatus, etc.). Cada filtro revisa solo su columna, así que filtrar «HUAMANTLA» ya no trae filas que lo mencionan en otra columna. Varias opciones de un mismo filtro se combinan con «o»; filtros distintos, con «y». Lógica en `vinculate/core/explorador.py` (pura, con pruebas).
- La búsqueda de texto del Explorador ahora mira solo nombres e identificadores (nombre, ID, teléfono, correo / empresa, puesto), no todo el renglón.
- **Menú:** «Búsqueda» ya no aparece en Consulta. La página de resultados sigue existiendo (oculta) porque el buscador global del lateral la usa; si la versión de Streamlit no soporta páginas ocultas, aparece en el menú sin otro efecto.
- Sin migraciones ni cambios en datos, permisos o RLS.
