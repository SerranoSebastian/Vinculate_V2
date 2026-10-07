# Despliegue paso a paso

Tiempo estimado: 1–2 horas la primera vez. Orden recomendado: **primero un proyecto de PRUEBA, luego el real**.
Las migraciones las ejecutas tú en el SQL Editor de Supabase; la app y este repositorio nunca ejecutan SQL por su cuenta.

> **Antes de empezar**
> - Supabase → *Project Settings → API*: necesitas la **Project URL** y la llave **anon / publishable**.
>   La llave `service_role` o `secret` **no se usa en ningún lado** de este proyecto.
> - El ZIP de la v5 (`Vinculate_SEDECO_ESTABLE_v6_…zip`) trae llaves de Supabase y datos personales (CSV, respaldos).
>   **No lo subas a GitHub.** Este repositorio es otra carpeta, ya limpia; no copies archivos del ZIP viejo a él.

---

## 1. Proyecto Supabase de prueba

Crea un proyecto nuevo en https://supabase.com (llámalo, por ejemplo, `vinculate-prueba`). Elige uno de los dos caminos:

**Camino A — copia fiel de los datos actuales (recomendado para probar).**
En *SQL Editor → New query* pega y ejecuta `supabase/00_SQL_MAESTRO_NUEVO_SUPABASE_20260921.sql` **del ZIP viejo**
(crea las tablas y carga las 697 personas, 167 vacantes y 4 vinculaciones). Es un archivo con datos personales: úsalo desde tu
computadora, no lo copies al repositorio.

**Camino B — proyecto limpio, sin datos.**
Ejecuta `supabase/schema/00_esquema_base.sql` de este repositorio (mismas tablas y funciones, sin datos). Los datos los cargas después
desde la app (Personas → Carga Excel/CSV).

### 1.1 Autenticación (una vez por proyecto)

*Authentication → Providers → Email*: debe estar **habilitado** y *Allow new users to sign up* **encendido**
(la app da de alta a los colaboradores con ese mecanismo y luego completa el perfil con un RPC protegido; ese RPC también
confirma el correo, así que *Confirm email* puede quedarse como esté).

### 1.2 Migraciones, en este orden

En *SQL Editor* ejecuta cada archivo de `supabase/migrations/`, uno por uno, esperando el mensaje de éxito:

| Orden | Archivo | Qué hace (resumen) |
|---|---|---|
| 1 | `V001_cierre_brechas.sql` | Quita a `anon` el acceso a los datos, endurece los RPC de administración y los equipos. |
| 2 | `V002_rls_por_permiso.sql` | La base aplica la matriz módulo × acción (RLS). Deja **apagada** la validación de equipo. |
| 3 | `V003_auditoria_servidor.sql` | Auditoría en la base y marca de actualización (`actualizado_en`). |
| 4 | `V004_ubicacion_empresas.sql` | Columnas opcionales de ubicación (empresa/vacante) y clave INEGI en municipios. |
| 5 | `V005_origen_del_dato.sql` | Etiqueta como «imputado»/«balanceado» los 534 años y 259 instituciones asignados por procesos de limpieza (Camino A). En Camino B no cambia nada. |
| 6 | `V007_vigencia_vacantes.sql` | Columna `fecha_cierre` en vacantes. |
| 7 | `V008_disponibilidad_personas.sql` | Tabla de disponibilidad manual por persona. |

(No existe V006: se difirió a propósito; ver `docs/DECISIONES_Y_CAMBIOS.md`.)
Detalle, verificación y rollback de cada una: [MIGRACIONES.md](MIGRACIONES.md).

### 1.3 Primer administrador (solo Camino B)

En el Camino A ya existen los administradores del sistema anterior. En el Camino B:
1. *Authentication → Users → Add user* (correo + contraseña, «Auto Confirm User»).
2. Abre `supabase/schema/01_primer_administrador.sql`, cambia **solo** el correo marcado, pégalo en el SQL Editor y ejecútalo.

---

## 2. Probar la app contra el proyecto de prueba (en tu computadora)

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml     # edítalo: URL y llave PÚBLICA del proyecto de prueba
streamlit run streamlit_app.py
```

Entra con un administrador y revisa **Administración → 🩺 Estado del sistema**: debe mostrar la conexión y las migraciones
V002, V004, V005, V007 y V008 como «Aplicada». V001 y V003 aparecen como «No verificable» (con la llave pública la app no puede inspeccionar privilegios ni disparadores):
compruébalas con las consultas de [MIGRACIONES.md](MIGRACIONES.md). Si otra aparece «Pendiente», esa pantalla indica qué falta; la app sigue funcionando sin ella.

Lista de comprobación mínima:
- [ ] Un colaborador **sin** permisos de Personas no ve ni por la API directa (RLS) datos de personas.
- [ ] Crear/editar/eliminar una persona de prueba pide confirmación y queda en *Auditoría*.
- [ ] *Inicio* muestra cifras que coinciden con la v5 (697 históricos · 593 personas maestras · 167 vacantes · 4 vinculaciones en el Camino A).
- [ ] *RIDET* → «Empresas con vacantes»: las 5 empresas pendientes de municipio aparecen como «Pendiente de revisión», no asignadas.

## 3. Repositorio en GitHub

Antes de nada, copia **`RIDET.pdf`** (está en `assets/documentos/` de tu ZIP de la v5, ~45 MB) a `assets/documentos/RIDET.pdf` de este proyecto:
no viene incluido en la entrega por su tamaño. Sin él la app funciona igual y solo avisa en *RIDET → Documento oficial*.

El proyecto ya trae `.gitignore` que impide subir secretos y datos personales. En la carpeta del proyecto:

```bash
git init -b main                  # el ZIP no trae historial de git: esto lo crea
git add -A
git status                        # revisa: NO debe aparecer secrets.toml, ningún .csv (salvo referencia/ridet_empresas.csv), data/ ni backups/
git commit -m "Vincúlate SEDECO v2"
git remote add origin https://github.com/TU_USUARIO/vinculate-sedeco-v2.git     # repositorio PRIVADO, vacío
git push -u origin main
```

Crea el repositorio como **Private**. `RIDET.pdf` pesa ~45 MB (GitHub avisa desde 50 MB y bloquea desde 100 MB; está debajo).

## 4. Streamlit Community Cloud

1. https://share.streamlit.io → *New app* → elige el repositorio, rama `main`, **Main file path: `streamlit_app.py`**.
2. *Advanced settings → Python version*: 3.12 o 3.13. *Secrets*:
   ```toml
   [supabase]
   url = "https://TU-PROYECTO.supabase.co"
   key = "TU_LLAVE_PUBLICA_ANON_O_PUBLISHABLE"
   ```
3. *Deploy*. Si Streamlit Cloud muestra «La llave configurada es una llave SECRETA…», pegaste la llave equivocada: es la medida de seguridad funcionando.
4. Si la app es privada (recomendado), en *Settings → Sharing* limita quién puede abrir la URL; además de eso siempre hace falta usuario y contraseña de Vincúlate.

## 5. Pasar al proyecto real

Cuando todo lo anterior esté probado:
1. **Respaldo previo** del proyecto real (la app: Administración → Respaldos; o *Database → Backups* de Supabase).
2. Ejecuta en el proyecto real las mismas migraciones, **en el mismo orden**, de V001 a V008 (no ejecutes el SQL maestro ni el esquema base: ya existen las tablas).
3. Cambia los *Secrets* de Streamlit Cloud a la URL/llave del proyecto real y reinicia la app.
4. Si algo sale mal: cada migración tiene su `_rollback.sql` (ver MIGRACIONES.md; se ejecutan en orden inverso: V008 → V001).

## 6. Equipos (computadoras): cómo funciona

Igual que en la v5, **cada colaborador** (los administradores no) necesita que su equipo esté autorizado. Como en Streamlit Cloud el
servidor es uno solo, el identificador del equipo ya no es un archivo del servidor sino una **cookie del navegador**
(`vinculate_device`, aleatoria, ~5 años). Consecuencias prácticas:

- La primera vez que un colaborador entra desde un navegador nuevo, el equipo queda **registrado como pendiente** y la app le avisa;
  un administrador lo habilita en *Administración → 💻 Computadoras*. Otro navegador o borrar cookies = equipo nuevo.
- La **app** siempre exige esa autorización. Además hay un candado **opcional en la base** (apagado por defecto, ver V002): con él
  encendido, Supabase rechaza lecturas y escrituras de equipos no autorizados incluso si alguien usa la API directamente.
  Se enciende en *Administración → Estado del sistema* **después** de autorizar tu equipo y los de tus colaboradores.
- Es un control **suave**: identifica un navegador, no lo autentica. La defensa principal es el inicio de sesión + permisos + RLS.
