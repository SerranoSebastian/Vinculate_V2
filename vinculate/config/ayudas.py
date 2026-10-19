"""TEXTOS DE AYUDA (el signo ❓ que aparece junto a cada indicador y gráfica).

Este es el ÚNICO archivo que hay que editar para cambiar una explicación. No contiene código de la
aplicación, solo textos. Cada texto tiene la forma:

    "nombre.interno": \"\"\"Texto que se verá al pasar el mouse sobre el ❓.\"\"\",

Reglas para editar:
- No cambies el nombre interno (lo que está antes de los dos puntos): la página lo usa para encontrar el texto.
- Escribe el texto entre las comillas triples. Una línea en blanco separa un párrafo del siguiente.
- Usa siempre la palabra «vinculación» (no sinónimos) y lenguaje que entienda alguien ajeno al programa.
- Para agregar una ayuda nueva: añade una línea con su nombre interno y, en la vista, pásalo al indicador o gráfica.

Las pruebas automáticas (tests/test_ayudas.py) revisan que cada ❓ de la página tenga su texto aquí.
"""
from __future__ import annotations

AYUDAS: dict[str, str] = {
    # ------------------------------------------------------------------ INICIO · Personas (indicadores)
    "inicio.personas_unicas": """Es el número de personas distintas que han tenido al menos una vinculación con el programa.

Cada persona se cuenta una sola vez, aunque haya tenido varias vinculaciones o aparezca en varios años.

Los datos vienen de la base de personas de Vincúlate, que incluye los registros capturados en el sistema y los históricos cargados de años anteriores. El número cambia según los filtros que se elijan arriba.""",

    "inicio.vinculaciones_historicas": """Es el total de vinculaciones realizadas desde que existe el registro.

Si una misma persona tuvo 2 vinculaciones, aquí suma 2. Por eso este número es mayor que el de personas únicas.

Los datos vienen del historial de vinculaciones.""",

    "inicio.personas_recurrentes": """Son las personas que han tenido 2 o más vinculaciones.

Se obtienen contando cuántas vinculaciones tiene cada persona y quedándose con quienes tienen más de una. Muestra cuánta gente vuelve a utilizar el programa.""",

    "inicio.vinculaciones_por_persona": """Es el promedio de vinculaciones que tiene cada persona.

Se calcula dividiendo el total de vinculaciones entre las personas únicas. Un valor cercano a 1 indica que la mayoría de las personas tuvo una sola vinculación.""",

    "inicio.registros_sin_anio": """Son vinculaciones históricas cuya fecha original no indica el año.

Por eso no se pueden ubicar en un periodo específico y no aparecen en las gráficas por año. Sí se incluyen en los totales generales.""",

    # ------------------------------------------------------------------ INICIO · Vacantes y empresas (indicadores)
    "inicio.vacantes_registradas": """Es el total de puestos de trabajo que las empresas han ofrecido y que están registrados en el sistema, sin importar si siguen abiertos o ya cerraron.

Cada puesto cuenta como una vacante: una empresa con 3 puestos ofrecidos aporta 3.""",

    "inicio.vacantes_vigentes": """Son las vacantes que hoy siguen abiertas.

Una vacante es vigente cuando su estado es «Activa» y su fecha de cierre, si la tiene, aún no ha llegado.""",

    "inicio.vacantes_activas": """Son las vacantes cuyo estado es «Activa».

Cada puesto cuenta como una vacante: una empresa con 3 puestos activos aporta 3.""",

    "inicio.empresas_con_vacantes": """Es el número de empresas distintas que han ofrecido al menos una vacante.

Cada empresa se cuenta una sola vez, aunque tenga muchos puestos. Los nombres se unifican para que una misma empresa escrita de varias formas no se cuente dos veces.""",

    "inicio.puestos_distintos": """Es el número de tipos de puesto diferentes dentro de las vacantes.

Los puestos se agrupan con un catálogo, así que escribir «Operador de producción» o «OPERADOR DE PRODUCCION» cuenta como un solo puesto. Muestra qué tan variada es la oferta de empleo.""",

    "inicio.sin_fecha_de_cierre": """Es el número de vacantes que no tienen una fecha límite registrada.

Estas vacantes se consideran abiertas mientras su estado sea «Activa».""",

    # ------------------------------------------------------------------ INICIO · Seguimiento con empresas (indicadores)
    "inicio.seguimientos": """Es el número de acciones registradas en las que una persona fue vinculada con una empresa.

Cada acción es un seguimiento y muestra en qué etapa va esa vinculación.""",

    "inicio.personas_colocadas": """Es el número de personas que ya consiguieron empleo gracias a una vinculación.

Cada persona se cuenta una sola vez, aunque haya sido contratada más de una vez.""",

    "inicio.empresas_con_seguimiento": """Es el número de empresas distintas con las que se ha registrado al menos una vinculación.

Muestra con cuántas empresas se está trabajando.""",

    "inicio.no_vinculados": """Es el número de seguimientos que no terminaron en una vinculación, por ejemplo porque la persona no avanzó en el proceso con la empresa.""",

    # ------------------------------------------------------------------ INICIO · pestaña Personas (gráficas)
    "inicio.grafica_evolucion_anual": """Muestra cómo ha crecido el programa año con año.

Las barras indican cuántas vinculaciones hubo en cada año. Se suma una por cada vinculación, según el año en que ocurrió.

La línea indica cuántas personas distintas fueron vinculadas ese año. Cada persona se cuenta una sola vez dentro del año.

Si la línea sube de un año a otro, significa que el programa llegó a más personas.

Barra roja: vinculaciones cuyo año viene registrado en el dato original.
Barra rayada: vinculaciones cuyo año fue estimado al organizar la información histórica. Se muestran con otro patrón para distinguirlas de las registradas.""",

    "inicio.grafica_tipo_vinculacion": """Muestra qué parte del total de vinculaciones corresponde a cada tipo. El porcentaje de cada sección se calcula dividiendo las vinculaciones de ese tipo entre el total.

Inserción laboral reúne las vinculaciones de atención e inserción laboral.
Inserción Educativa reúne las vinculaciones de prácticas profesionales y servicio social.

Cada tipo se muestra por separado en las tablas de datos. Las vinculaciones que no tienen tipo registrado aparecen como «Indefinido».""",

    "inicio.grafica_municipio": """Muestra en qué municipios viven las personas vinculadas.

Cada barra es un municipio y su número es la cantidad de personas distintas que viven ahí. Cada persona se cuenta una sola vez. Se muestran los 15 municipios con más personas; si alguien vive fuera de Tlaxcala, aparece su estado.

Los datos vienen del municipio registrado en la base de personas. Quienes no tienen ese dato aparecen como «Indefinido».

Al hacer clic en una barra se abre la lista de las personas de ese municipio.""",

    "inicio.grafica_institucion": """Muestra de qué instituciones educativas vienen las personas vinculadas.

Cada barra es una institución y su número es la cantidad de personas distintas de esa institución. Cada persona se cuenta una sola vez. Se muestran las 12 instituciones con más personas.

Los datos vienen de la institución registrada en la base de personas. Quienes no tienen ese dato aparecen como «Indefinido».

Al hacer clic en una barra se abre la lista de las personas de esa institución.""",

    "inicio.grafica_carrera": """Muestra qué carreras estudian o estudiaron las personas vinculadas.

Cada barra es una carrera y su número es la cantidad de personas distintas de esa carrera. Cada persona se cuenta una sola vez. Se muestran las 12 carreras con más personas.

Los datos vienen de la carrera registrada en la base de personas. Quienes no tienen ese dato aparecen como «Indefinido».

Al hacer clic en una barra se abre la lista de las personas de esa carrera.""",

    "inicio.grafica_sexo": """Muestra qué porcentaje de las personas vinculadas son mujeres y qué porcentaje son hombres.

Cada persona se cuenta una sola vez. Los datos vienen del sexo registrado en la base de personas. Si un mismo valor está escrito de varias formas (por ejemplo «MASCULINO» y «Masculino»), se cuenta junto.

Quienes no tienen ese dato aparecen como «Indefinido».""",

    # ------------------------------------------------------------------ INICIO · pestaña Vacantes (gráficas)
    "inicio.grafica_vacantes_por_mes": """Muestra cuántas vacantes se registraron cada mes.

Cada punto es un mes y su altura es el número de vacantes cuya fecha de registro cae en ese mes. Los picos son los meses en que las empresas ofrecieron más puestos.

Solo se cuentan las vacantes que tienen fecha de registro.""",

    "inicio.grafica_situacion_vacantes": """Muestra cuántas vacantes siguen abiertas y cuántas ya no. El porcentaje de cada sección se calcula dividiendo sus vacantes entre el total.

Vigente: el estado es «Activa» y su fecha de cierre, si la tiene, aún no ha llegado.
Activa con cierre vencido: el estado es «Activa», pero su fecha de cierre ya pasó.
Inactiva: la vacante ya no está activa.""",

    "inicio.grafica_empresas_con_mas_vacantes": """Muestra las 12 empresas que han ofrecido más vacantes.

Cada barra es una empresa y su número es la cantidad de puestos que registró. Una empresa con 3 puestos cuenta 3. Los nombres se unifican para que una misma empresa escrita de varias formas no se cuente dos veces.

Al hacer clic en una barra se abre la lista de vacantes de esa empresa.""",

    # ------------------------------------------------------------------ INICIO · pestaña Seguimiento (gráficas)
    "inicio.grafica_seguimientos_por_estatus": """Muestra en qué situación se encuentran los seguimientos. El porcentaje de cada sección se calcula dividiendo sus seguimientos entre el total.

Vinculado: la persona fue vinculada con la empresa.
Colocado: la persona consiguió empleo con la empresa.
No vinculado: el seguimiento no terminó en una vinculación.""",

    "inicio.grafica_seguimientos_por_empresa": """Muestra con qué empresas se han registrado seguimientos. Se muestran las 12 empresas con más seguimientos.

Cada barra es una empresa y su número es la cantidad de seguimientos que tiene, es decir, las veces que una persona fue vinculada con ella.""",

    # ------------------------------------------------------------------ MAPA TERRITORIAL · casillas y opciones
    "mapa.casilla_personas": """Colorea cada municipio de Tlaxcala según la cantidad que tiene. Mientras más oscuro el color, más personas (o vinculaciones, o vacantes, según lo que elijas en «Opciones del mapa»).""",

    "mapa.casilla_empresas": """Muestra un punto por cada empresa, en la ubicación exacta que tiene registrada. Cada empresa tiene su propio color y su punto es más grande mientras más vacantes tiene.""",

    "mapa.separar_empresas": """Si dos empresas tienen exactamente la misma ubicación, sus puntos se separan unos metros en círculo para que ninguno tape a otro. Es solo un efecto visual: al pasar el cursor sobre un punto siempre se ven sus coordenadas reales.""",

    # ------------------------------------------------------------------ MAPA TERRITORIAL · indicadores de personas
    "mapa.con_municipio": """Es la cantidad que se pinta en el mapa dentro de los 60 municipios de Tlaxcala. Lo que se cuenta depende de la opción «Colorear municipios por»: personas únicas, vinculaciones históricas o vacantes.

El porcentaje indica qué parte del total representa. Los datos vienen del municipio registrado en la base.""",

    "mapa.fuera_de_tlaxcala": """Es la cantidad cuyo lugar registrado está en otro estado. Se cuenta, pero no se dibuja en el mapa porque el mapa solo muestra los municipios de Tlaxcala.""",

    "mapa.sin_municipio": """Es la cantidad que no tiene un municipio registrado, por lo que no se puede ubicar en el mapa y no se dibuja. Se cuenta aparte para que el total siga completo.""",

    "mapa.municipios_con_registros": """Es el número de municipios, de los 60 que tiene Tlaxcala, que tienen al menos una persona, vinculación o vacante según lo elegido en «Colorear municipios por».

Un número bajo indica que la actividad se concentra en pocos municipios.""",

    # ------------------------------------------------------------------ MAPA TERRITORIAL · indicadores de empresas
    "mapa.empresas_en_mapa": """Es el número de empresas que se dibujan como punto porque tienen su ubicación exacta (latitud y longitud) registrada.

El número de abajo («de N registradas») es el total de empresas del catálogo. Si usas los filtros de «Opciones del mapa», aquí se ven solo las empresas que cumplen el filtro.""",

    "mapa.sin_coordenadas": """Son las empresas del catálogo que todavía no tienen su ubicación exacta registrada. No se dibujan, porque el mapa nunca estima ni inventa ubicaciones.

La lista con sus datos está debajo del mapa, en «Empresas sin coordenadas».""",

    "mapa.coordenadas_con_problema": """Son las empresas cuya ubicación registrada no es válida, por ejemplo porque cae fuera de México o porque la latitud y la longitud están invertidas. No se dibujan.

La lista con el motivo de cada una está debajo del mapa, en «Coordenadas con problema».""",

    "mapa.vacantes_vigentes_en_mapa": """Es la suma de las vacantes vigentes de las empresas que se dibujan en el mapa. Una vacante es vigente cuando su estado es «Activa» y su fecha de cierre, si la tiene, aún no ha llegado.

Cambia si se usan los filtros de «Opciones del mapa».""",

    # ------------------------------------------------------------------ MAPA TERRITORIAL · el mapa y las tablas
    "mapa.grafica_mapa": """Muestra en un solo mapa dónde están las personas y las empresas de Tlaxcala.

Municipios: cada uno se colorea según la cantidad elegida en «Colorear municipios por». Mientras más oscuro, mayor cantidad. Cada persona, vinculación o vacante se ubica por el municipio registrado en la base.

Empresas: cada punto es una empresa, colocada en su ubicación exacta. Cada empresa tiene su propio color para distinguirla de las demás y su punto es más grande mientras más vacantes tiene.

Se pueden mostrar las dos capas juntas o solo una con las casillas de arriba. Con la rueda del ratón se acerca, arrastrando se mueve y al hacer clic en un municipio o en una empresa se abre su detalle. En la leyenda, un clic oculta o muestra una empresa.""",

    "mapa.tabla_municipios": """Lista los 60 municipios de Tlaxcala con su cantidad, de mayor a menor. La columna «Total» es lo elegido en «Colorear municipios por» (personas únicas, vinculaciones históricas o vacantes).

La columna «Región RIDET» indica a qué región pertenece cada municipio.""",

    "mapa.tabla_sin_coordenadas": """Son las empresas que no se dibujan en el mapa porque no tienen su ubicación exacta registrada. La columna «Vacantes» es el total de puestos que han ofrecido.""",

    "mapa.tabla_con_problema": """Son las empresas que no se dibujan en el mapa porque su ubicación registrada no es válida. La columna «Problema» explica el motivo de cada una.""",

    # ------------------------------------------------------------------ RIDET · pestaña General
    "ridet.general_imagenes": """Son las páginas del documento oficial RIDET, que reúne las seis regiones económicas de Tlaxcala. Con los botones «Anterior» y «Siguiente» se pasa de una imagen a otra.

Son imágenes del documento oficial, no datos calculados por el sistema.""",

    "ridet.general_resumen": """Resume las seis regiones según el documento oficial RIDET.

Cabecera: el municipio principal de la región.
Municipios: cuántos municipios indica el encabezado de la región.
Sectores: sectores industriales que reporta el documento en la región.
Empresas: empresas que reporta el documento en la región.
Instituciones EMS: instituciones públicas de educación media superior de la región.

Son cifras del documento, no conteos de la base de vacantes ni de personas.""",

    # ------------------------------------------------------------------ RIDET · pestaña Regiones
    "ridet.region_municipios": """Es el número de municipios que el encabezado del documento oficial asigna a la región elegida. La lista de esos municipios aparece debajo.""",

    "ridet.region_empresas": """Es el número de empresas que el documento oficial reporta en la región elegida. Es una cifra del documento, no de la base de vacantes.""",

    "ridet.region_sectores": """Es el número de sectores industriales que el documento oficial reporta en la región elegida.""",

    "ridet.region_ems": """Es el número de instituciones públicas de educación media superior que el documento oficial reporta en la región elegida.""",

    "ridet.region_lista_empresas": """Lista las empresas que el documento oficial reporta en la región elegida, junto con la página del PDF donde aparece cada una.""",

    "ridet.region_imagenes": """Son las páginas del documento oficial RIDET que corresponden a la región elegida: su cabecera, sus municipios, sus empresas por sector y sus instituciones de educación media superior. Con «Anterior» y «Siguiente» se pasa de una imagen a otra.

Son imágenes del documento oficial, no datos calculados por el sistema.""",

    # ------------------------------------------------------------------ RIDET · pestaña Empresas y vacantes
    "ridet.emp_con_vacantes": """Es el número de empresas distintas que han ofrecido al menos una vacante. Cada empresa se cuenta una sola vez, aunque tenga muchos puestos.""",

    "ridet.emp_con_region": """Es el número de empresas con vacantes a las que el sistema pudo asignar una región del RIDET. El porcentaje indica qué parte del total de empresas con vacantes representa.

La región se asigna con el municipio registrado de la empresa o, si no lo tiene, con el nombre de la empresa tal como aparece en el documento RIDET.""",

    "ridet.emp_sin_region": """Es el número de empresas con vacantes a las que todavía no se les puede asignar una región. Sucede cuando su nombre no aparece en el documento RIDET, o aparece en varias regiones y la empresa no tiene municipio registrado.

Sus vacantes se muestran aparte, como «Pendiente de asignar».""",

    "ridet.emp_tabla": """Muestra la región RIDET de cada empresa que ha ofrecido vacantes y cómo se determinó.

Criterio, es decir, la forma en que se asignó la región:
Por municipio capturado: se usó el municipio registrado de la empresa.
Coincide con el RIDET: el nombre de la empresa es igual al que aparece en el documento.
Alias de la versión anterior: el nombre coincide con uno usado antes en el documento.
Coincidencia parcial: el nombre se parece al de una empresa del documento.
Ambigua: el nombre aparece en varias regiones, por eso no se asigna sola.
Sin coincidencia: el nombre no aparece en el documento.

Coincide con (RIDET): nombre o municipio con el que se encontró la coincidencia. Vacantes: número de vacantes de la empresa.""",

    "ridet.emp_vacantes_tabla": """Lista cada vacante junto con la región RIDET de su empresa. Con los filtros «Región» y «Empresa» se ve solo una parte de la lista.

Las vacantes de empresas sin región asignada aparecen como «Pendiente de asignar».""",

    # ------------------------------------------------------------------ RIDET · pestaña Estadísticas
    "ridet.est_regiones": """Es el número de regiones económicas que define el documento oficial RIDET.""",

    "ridet.est_empresas": """Es la suma de las empresas que el documento oficial reporta en cada una de sus regiones. Es una cifra del documento, no de la base de vacantes.""",

    "ridet.est_sectores": """Es la suma de los sectores industriales de cada región. Un mismo sector puede aparecer en varias regiones, por eso esta suma lo cuenta una vez por cada región donde aparece.""",

    "ridet.est_ems": """Es la suma de las instituciones públicas de educación media superior que el documento oficial reporta en cada región.""",

    "ridet.grafica_empresas_region": """Compara cuántas empresas reporta el documento oficial RIDET en cada región.

Cada barra es una región y su número es la cantidad de empresas reportadas. Una barra más larga indica una región con más empresas en el inventario del documento.

No mide empleo ni vacantes.""",

    "ridet.grafica_vacantes_region": """Muestra cuántas vacantes de la base corresponden a cada región.

Cada vacante se ubica según la región asignada a su empresa. «Pendiente de asignar» agrupa las vacantes de empresas a las que todavía no se les puede asignar región.

Refleja las vacantes registradas, no el empleo real de cada región.""",

    # ------------------------------------------------------------------ PERSONAS · Análisis · indicadores
    "personas.personas_unicas": """Es el número de personas distintas que han tenido al menos una vinculación con el programa.

Cada persona se cuenta una sola vez, aunque haya tenido varias vinculaciones o aparezca en varios años.

Los datos vienen de la base de personas de Vincúlate, que incluye los registros capturados en el sistema y los históricos cargados de años anteriores. El número cambia según los filtros que se elijan arriba.""",

    "personas.vinculaciones": """Es el total de vinculaciones que cumplen los filtros elegidos arriba. Cada vinculación cuenta una vez.

Si una misma persona tuvo 2 vinculaciones, aquí suma 2. Por eso este número es mayor que el de personas únicas.""",

    "personas.recurrentes": """Son las personas que han tenido 2 o más vinculaciones.

Se obtienen contando cuántas vinculaciones tiene cada persona y quedándose con quienes tienen más de una. Muestra cuánta gente vuelve a utilizar el programa.""",

    "personas.vinculaciones_por_persona": """Es el promedio de vinculaciones que tiene cada persona.

Se calcula dividiendo el total de vinculaciones entre las personas únicas. Un valor cercano a 1 indica que la mayoría de las personas tuvo una sola vinculación; un valor mayor indica que muchas regresan.""",

    "personas.maximo_por_persona": """Es el mayor número de vinculaciones que tiene una sola persona dentro de los filtros elegidos.

Por ejemplo, si dice 4, significa que al menos una persona ha tenido 4 vinculaciones.""",

    "personas.sin_anio": """Son vinculaciones históricas cuya fecha original no indica el año.

Por eso no se pueden ubicar en un periodo específico y no aparecen en las gráficas por año. Sí se incluyen en los totales generales.""",

    # ------------------------------------------------------------------ PERSONAS · Análisis · Resumen
    "personas.grafica_tipos": """Muestra cuántas vinculaciones hay de cada tipo. Cada barra es un tipo y su número es la cantidad de vinculaciones de ese tipo.

Inserción laboral reúne las vinculaciones de atención e inserción laboral.
Inserción Educativa reúne las vinculaciones de prácticas profesionales y servicio social.

Cada tipo se muestra por separado en las tablas de datos. Las vinculaciones que no tienen tipo registrado aparecen como «Indefinido».""",

    "personas.grafica_frecuencia": """Muestra cuántas personas han tenido 1, 2, 3 o más vinculaciones.

El número de abajo de cada barra es la cantidad de vinculaciones que tiene una persona. El número sobre la barra es cuántas personas están en ese grupo. La barra del 1 son quienes han tenido una sola vinculación; las demás son quienes han regresado al programa.""",

    "personas.tabla_top": """Lista, de mayor a menor, a las 15 personas con más vinculaciones.

ID: identificador de la persona en Vincúlate.
Nombre: nombre registrado.
Vinculaciones: cuántas vinculaciones tiene.""",

    # ------------------------------------------------------------------ PERSONAS · Análisis · Evolución anual
    "personas.grafica_evolucion": """Muestra cómo ha crecido el programa año con año.

Las barras indican cuántas vinculaciones hubo en cada año. Se suma una por cada vinculación, según el año en que ocurrió.

La línea indica cuántas personas distintas fueron vinculadas ese año. Cada persona se cuenta una sola vez dentro del año.

Si la línea sube de un año a otro, significa que el programa llegó a más personas.

Barra roja: vinculaciones cuyo año viene registrado en el dato original.
Barra rayada: vinculaciones cuyo año fue estimado al organizar la información histórica. Se muestran con otro patrón para distinguirlas de las registradas.""",

    "personas.tabla_anual": """Resume cada año con los mismos datos de la gráfica.

Año: año de la vinculación.
Personas únicas: personas distintas vinculadas ese año.
Vinculaciones: total de vinculaciones de ese año.
Promedio por persona: vinculaciones entre personas únicas de ese año.
Personas recurrentes: personas con 2 o más vinculaciones dentro de ese año.

Solo incluye las vinculaciones que tienen año.""",

    # ------------------------------------------------------------------ PERSONAS · Análisis · Recurrencia
    "personas.con_1_vinculacion": """Es el número de personas que han tenido una sola vinculación dentro de los filtros elegidos.""",

    "personas.con_2_o_mas": """Es el número de personas que han tenido 2 o más vinculaciones dentro de los filtros elegidos.""",

    "personas.porcentaje_recurrentes": """Es qué parte de las personas únicas ha tenido 2 o más vinculaciones. Se calcula dividiendo las personas con 2 o más vinculaciones entre el total de personas únicas.""",

    "personas.tabla_recurrentes": """Lista a las personas que han tenido 2 o más vinculaciones, de mayor a menor.

ID: identificador de la persona.
Vinculaciones: cuántas tiene.
Primera y Última: fecha de su primera y de su última vinculación. Si el registro histórico no tiene fecha, aparece «Indefinido».""",

    # ------------------------------------------------------------------ PERSONAS · Análisis · Perfil
    "personas.grafica_sexo": """Muestra qué porcentaje de las personas vinculadas son mujeres y qué porcentaje son hombres.

Cada persona se cuenta una sola vez. Los datos vienen del sexo registrado en la base de personas. Si un mismo valor está escrito de varias formas (por ejemplo «MASCULINO» y «Masculino»), se cuenta junto.

Quienes no tienen ese dato aparecen como «Indefinido».""",

    "personas.grafica_escolaridad": """Muestra el nivel de estudios de las personas vinculadas.

Cada barra es un nivel de escolaridad y su número es la cantidad de personas distintas en ese nivel. Cada persona se cuenta una sola vez. Quienes no tienen ese dato aparecen como «Indefinido».""",

    "personas.grafica_municipios": """Muestra los 60 municipios de Tlaxcala, incluidos los que no tienen personas.

Cada barra es un municipio y su número es la cantidad de personas distintas que viven ahí. Cada persona se cuenta una sola vez. Un cero significa que no hay personas registradas en ese municipio con los filtros elegidos.""",

    "personas.grafica_instituciones": """Muestra de qué instituciones educativas vienen las personas vinculadas.

Cada barra es una institución y su número es la cantidad de personas distintas de esa institución. Cada persona se cuenta una sola vez. Se muestran las 12 instituciones con más personas. Quienes no tienen ese dato aparecen como «Indefinido».""",

    "personas.grafica_carreras": """Muestra qué carreras estudian o estudiaron las personas vinculadas.

Cada barra es una carrera y su número es la cantidad de personas distintas de esa carrera. Cada persona se cuenta una sola vez. Se muestran las 12 carreras con más personas. Quienes no tienen ese dato aparecen como «Indefinido».""",

    # ------------------------------------------------------------------ PERSONAS · Directorio y ficha
    "personas.tabla_directorio": """Lista a las personas registradas, con una fila por persona y sus datos más recientes.

ID: identificador de la persona en Vincúlate.
Vinculaciones: cuántas vinculaciones tiene.
Última fecha: fecha de su vinculación más reciente.

Se pueden buscar por nombre, ID, correo o teléfono. Al elegir una fila se abre la ficha completa de la persona.""",

    "personas.ficha_vinculaciones": """Es el número de vinculaciones que tiene esta persona en su historial.""",

    "personas.ficha_tipos": """Es el número de tipos de vinculación distintos que ha tenido esta persona. Por ejemplo, si tuvo una de servicio social y otra de inserción laboral, son 2 tipos.""",

    "personas.ficha_primera_fecha": """Es la fecha de la vinculación más antigua de esta persona que tiene fecha registrada.""",

    "personas.ficha_ultima_fecha": """Es la fecha de la vinculación más reciente de esta persona que tiene fecha registrada.""",

    # ------------------------------------------------------------------ PERSONAS · Carga Excel/CSV
    "personas.carga_recibidas": """Es el total de filas que trae el archivo subido.""",

    "personas.carga_nuevas": """Es el número de filas que se agregarán como registros nuevos al presionar el botón de guardar.""",

    "personas.carga_omitidas": """Es el número de filas que no se guardarán porque su ID ya existe en la base o porque están repetidas en el archivo. Cargar un archivo nunca sobrescribe un registro existente.""",

    # ------------------------------------------------------------------ PERSONAS · Editar / eliminar
    "personas.tabla_editar": """Lista los registros que coinciden con la búsqueda (hasta 200). Cada fila es una vinculación.

ID de registro: identificador de esa vinculación.
ID persona: identificador de la persona a la que pertenece.
Tipo: tipo de vinculación.

Al elegir una fila se puede editar o eliminar ese registro.""",
}


def texto(clave: str) -> str | None:
    """Texto de ayuda de `clave`, o None si no existe (la página no muestra ❓ en ese caso)."""
    valor = AYUDAS.get(clave)
    return valor.strip() if valor and valor.strip() else None
