# Geometría de los municipios (para el mapa dibujado)

Aquí va **un solo archivo**: `tlaxcala_municipios.geojson` (los 60 municipios de Tlaxcala, entidad 29 de INEGI).
(Ya incluido: generado del archivo AGEM 2026 de INEGI, 60 municipios.) Si no existiera, el Mapa territorial muestra el ranking por municipio con los mismos datos y las instrucciones
para activarlo; nada se rompe.

Cómo generarlo (una sola vez):

1. Descarga la capa de **municipios** del Marco Geoestadístico de INEGI (https://www.inegi.org.mx/temas/mg/) y
   conviértela a GeoJSON (QGIS «Exportar → GeoJSON», o arrastra el .shp a https://mapshaper.org y exporta GeoJSON;
   ahí mismo puedes simplificar al 10 %).
2. `python scripts/preparar_geometria.py ARCHIVO.geojson`
   - Si el archivo viene en metros (proyección Lambert de INEGI), lo convierte a grados.
   - Se queda solo con la entidad 29, exige **exactamente 60 municipios** y compara cada nombre con el catálogo de la app.
   - Si algo no coincide, lista los problemas y **no escribe nada**.
   - Si todo coincide escribe `geo/tlaxcala_municipios.geojson` y `geo/cve_mun_municipios.sql`.
3. Opcional: ejecuta `geo/cve_mun_municipios.sql` en el SQL Editor de Supabase (después de V004) para guardar la clave
   INEGI de cada municipio en el catálogo.
4. Sube `geo/tlaxcala_municipios.geojson` (y el `.sql` si quieres) al repositorio: es geometría pública, sin datos personales. Vuelve a desplegar.
