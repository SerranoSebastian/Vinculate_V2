# Decisiones, cambios respecto a la v5 y pendientes

## 1. Decisiones adoptadas (D1–D6)

| # | Decisión | Cómo quedó |
|---|---|---|
| D1 | Aplicar V001 (cierre de brechas) | Entregada como archivo. Se prueba primero en un proyecto de **prueba** y luego en el real; la ejecuta una persona, nunca la app. |
| D2 | Servidor compartido (Streamlit Cloud) | El identificador de equipo vive en una **cookie del navegador** y se valida en RLS (V002, opcional y apagado por defecto). Control suave. |
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
6. **Equipos:** cookie del navegador en vez de archivo local (ver DESPLIEGUE.md §6). Un navegador nuevo de un colaborador queda «pendiente» hasta que un administrador lo autoriza.
7. **Bloqueo de login:** 5 intentos fallidos → 60 s de espera (por sesión de navegador).
8. **Interfaz:** navegación lateral por secciones, búsqueda global, centro de avisos, componentes unificados. Mismos módulos y mismos nombres de tablas/columnas.

## 3. Lo que NO se hizo y por qué

- **V006 (vistas SQL):** diferida; ver MIGRACIONES.md.
- **Mapa dibujado:** requiere la geometría oficial de INEGI, que no se pudo descargar desde el entorno donde se construyó el proyecto. Está **todo listo**
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
5. **Geometría de INEGI** para activar el mapa dibujado (`geo/LEEME.md`).
6. **Versión de Streamlit en producción:** el proyecto declara `streamlit>=1.52,<2` (probado en 1.52 y 1.65).
