# Vincúlate SEDECO v2

Plataforma Integral de Vinculación Laboral · Secretaría de Desarrollo Económico de Tlaxcala.
Rediseño completo de la v5 (Streamlit + Supabase) **sin cambiar la base de datos existente**: nada se borra ni se renombra,
todo lo nuevo son columnas/tablas opcionales y migraciones documentadas con su reversión.

- **Lenguaje y stack:** Python · Streamlit ≥ 1.52 · Supabase (Auth, PostgREST, RLS) · pandas · Plotly.
- **Fuente de verdad:** Supabase. CSV/XLSX solo para importar, exportar y respaldar.
- **Llave de Supabase:** solo la pública (`anon`/`publishable`). La app **se niega a arrancar** si le pones una `service_role` / `sb_secret_…`.

## Qué incluye

| Sección | Qué hace |
|---|---|
| **Inicio** | Tablero ejecutivo: indicadores, tendencias, avisos de prioridades. Muestra «Información no disponible» cuando falta un dato; no inventa nada. |
| **Mapa territorial** | Distribución por municipio (personas, históricos, vacantes, empresas). El mapa dibujado se activa al agregar la geometría oficial de INEGI (ver `geo/LEEME.md`); mientras tanto muestra el ranking con los mismos datos. |
| **RIDET** | Regiones, empresas del documento oficial (extraídas del PDF y validadas contra sus totales), clasificación de las empresas con vacantes y descarga del documento. |
| **Personas · Vacantes y empresas · Vinculaciones** | Análisis, directorio y ficha, alta, carga Excel/CSV (con vista previa y duplicados), edición/eliminación con confirmación. Modelo de persona maestra (`id_persona_maestro` vs `id_persona`). |
| **Explorador y Búsqueda** | Consulta libre sobre cualquier base con exportación; búsqueda global por persona, empresa o ID. |
| **Administración** | Estado del sistema (qué migraciones están aplicadas), usuarios, matriz de permisos, computadoras, prioridades, auditoría, respaldos. |
| **Centro de avisos** | Campana con prioridades vencidas y recordatorios. |

## Estructura del repositorio

```
streamlit_app.py            punto de entrada (login, navegación, barra lateral)
vinculate/
  vistas/                   pantallas (solo interfaz)
  components/               piezas reutilizables (tablas, KPIs, gráficas, filtros, avisos)
  services/                 reglas de negocio (reciben la sesión explícita)
  repositories/             único lugar que habla con Supabase
  core/                     Python puro, sin Streamlit ni Supabase (se prueba solo)
  auth/                     sesión, permisos, identificador de equipo
  config/                   secretos y tema
supabase/
  schema/                   esquema base (proyecto NUEVO) + script del primer administrador
  migrations/               V001–V008 con su rollback
scripts/                    herramientas de una sola vez (RIDET, geometría, V005)
referencia/                 lista de empresas del RIDET (sin datos personales)
assets/ · geo/ · docs/ · tests/
```

## Ejecutarlo en tu computadora

> Primero copia `RIDET.pdf` de tu ZIP de la v5 a `assets/documentos/RIDET.pdf` (no viene incluido por su tamaño; ver `assets/documentos/LEEME.md`).

```bash
python -m venv .venv && source .venv/bin/activate      # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # y pon tu URL y llave PÚBLICA de Supabase
streamlit run streamlit_app.py
```

## Desplegar en Streamlit Community Cloud

Guía completa, en orden y con comprobaciones: **[docs/DESPLIEGUE.md](docs/DESPLIEGUE.md)**.
Resumen: Supabase (proyecto de prueba → migraciones) → repositorio privado en GitHub → *New app* en Streamlit Cloud
con `Main file path = streamlit_app.py` y los **Secrets** `[supabase] url / key`.

## Documentación

- [docs/DESPLIEGUE.md](docs/DESPLIEGUE.md) — de cero a la app funcionando.
- [docs/MIGRACIONES.md](docs/MIGRACIONES.md) — qué hace cada migración, cómo verificarla y cómo revertirla.
- [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) — capas, permisos, equipos, caché, mapa.
- [docs/DECISIONES_Y_CAMBIOS.md](docs/DECISIONES_Y_CAMBIOS.md) — decisiones D1–D6, cambios de comportamiento respecto a la v5, límites conocidos y pendientes de revisión humana.

## Pruebas

```bash
pip install -r requirements-dev.txt
pytest tests/ --ignore=tests/test_sql_migraciones.py      # app: servicios, repositorios y páginas (AppTest)
```

Las pruebas SQL (`tests/test_sql_migraciones.py`) corren las migraciones contra un PostgreSQL **local** de verdad y
comprueban RLS, rollbacks e idempotencia con datos sintéticos; se activan con
`export VINCULATE_TEST_PG="host=localhost port=5432 user=postgres"`. Nunca tocan Supabase.

## Seguridad en una línea

Inicio de sesión con Supabase Auth · permisos módulo × acción aplicados **también en la base (RLS)** · solo llave pública ·
auditoría en servidor · datos personales **fuera** del repositorio (`.gitignore` bloquea CSV/XLSX, `data/`, `backups/` y `secrets.toml`).
