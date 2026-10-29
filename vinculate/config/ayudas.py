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

    "mapa.casilla_instituciones": """Muestra un punto por cada universidad o escuela que ya tiene personas asociadas, en la ubicación exacta que administración registró. Cada institución tiene su propio color y un contorno oscuro que la distingue de las empresas; su punto es más grande mientras más personas tiene.""",

    "mapa.tipos_institucion": """Permite mostrar solo universidades, solo escuelas, o ambas. El tipo de cada institución lo registra administración.""",

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

    # ------------------------------------------------------------------ MAPA TERRITORIAL · indicadores de instituciones
    "mapa.instituciones_en_mapa": """Es el número de instituciones educativas dibujadas en el mapa. Se cuentan solo las que ya tienen personas asociadas y cuya ubicación exacta está registrada. La cifra de abajo indica cuántas instituciones con personas hay en total.""",

    "mapa.inst_sin_coordenadas": """Son las instituciones con personas asociadas que no se dibujan porque todavía no tienen su ubicación exacta registrada. Administración la registra en Administración → Instituciones.""",

    "mapa.inst_con_problema": """Son las instituciones cuyas coordenadas registradas no son válidas (por ejemplo, tienen la latitud y la longitud invertidas o caen fuera de México). Estas instituciones no se dibujan hasta que se corrijan.""",

    "mapa.inst_personas_en_mapa": """Es la suma de personas asociadas a las instituciones que aparecen en el mapa con los filtros elegidos. Cada persona se cuenta una sola vez en su institución.""",

    # ------------------------------------------------------------------ MAPA TERRITORIAL · el mapa y las tablas
    "mapa.grafica_mapa": """Muestra en un solo mapa dónde están las personas, las empresas y las instituciones educativas de Tlaxcala.

Municipios: cada uno se colorea según la cantidad elegida en «Colorear municipios por». Mientras más oscuro, mayor cantidad. Cada persona, vinculación o vacante se ubica por el municipio registrado en la base.

Empresas: cada punto es una empresa, colocada en su ubicación exacta. Cada empresa tiene su propio color para distinguirla de las demás y su punto es más grande mientras más vacantes tiene.

Instituciones educativas: cada punto con contorno oscuro es una universidad o escuela que ya tiene personas asociadas. Cada una tiene su propio color y su punto es más grande mientras más personas tiene.

Se pueden mostrar las capas juntas o solo una con las casillas de arriba. Con la rueda del ratón se acerca, arrastrando se mueve y al hacer clic en un municipio, una empresa o una institución se abre su detalle. En la leyenda, un clic oculta o muestra un punto.""",

    "mapa.tabla_municipios": """Lista los 60 municipios de Tlaxcala con su cantidad, de mayor a menor. La columna «Total» es lo elegido en «Colorear municipios por» (personas únicas, vinculaciones históricas o vacantes).

La columna «Región RIDET» indica a qué región pertenece cada municipio.""",

    "mapa.tabla_inst_sin_coordenadas": """Son las instituciones que no se dibujan en el mapa porque no tienen su ubicación exacta registrada. La columna «Personas» es el número de personas asociadas a cada una.""",

    "mapa.tabla_inst_con_problema": """Son las instituciones cuyas coordenadas registradas no son válidas. La columna «Problema» explica qué tiene mal cada una.""",

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

    # ------------------------------------------------------------------ VACANTES · Análisis (indicadores)
    "vacantes.kpi_vacantes": """Es el número de puestos de trabajo registrados que cumplen los filtros elegidos. Cada registro es un puesto publicado por una empresa.

Una vacante no es una contratación: es una oferta de empleo.""",

    "vacantes.kpi_vigentes": """Son las vacantes que, con los filtros elegidos, siguen abiertas.

Se cuenta una vacante como vigente cuando su estado es «Activa» y su fecha de cierre todavía no ha pasado (o no tiene fecha de cierre).""",

    "vacantes.kpi_activas": """Son las vacantes cuyo estado es «Activa» con los filtros elegidos.

El estado lo captura el equipo al registrar o editar la vacante. Como estas vacantes no tienen fecha de cierre, no se puede confirmar si siguen abiertas hoy.""",

    "vacantes.kpi_empresas": """Es el número de empresas distintas que tienen al menos una vacante con los filtros elegidos. Una empresa con muchas vacantes se cuenta una sola vez.""",

    "vacantes.kpi_puestos": """Es el número de tipos de puesto diferentes entre las vacantes filtradas. Los nombres escritos de distintas maneras se agrupan en un puesto normalizado para contarlos como uno solo.""",

    "vacantes.kpi_meses": """Es el número de meses distintos en los que se publicó al menos una vacante, según la fecha de publicación. Las vacantes sin fecha no se consideran.""",

    # ------------------------------------------------------------------ VACANTES · Análisis (gráficas)
    "vacantes.grafica_empresas": """Muestra las 12 empresas que tienen más vacantes registradas con los filtros elegidos. Cada barra es una empresa y su largo es el número de vacantes.

Sirve para ver qué empresas concentran la oferta de empleo.""",

    "vacantes.grafica_puestos": """Muestra los 12 puestos que más se repiten entre las vacantes filtradas. Los nombres originales se agrupan en un puesto normalizado para poder compararlos.

Sirve para saber qué perfiles piden más las empresas.""",

    "vacantes.grafica_situacion": """Reparte las vacantes filtradas según su situación:

Vigente: estado «Activa» y fecha de cierre vigente o sin fecha de cierre.
Activa con cierre vencido: estado «Activa», pero su fecha de cierre ya pasó.
Inactiva: vacante que ya no está abierta.

Cada porción es el porcentaje del total de vacantes.""",

    "vacantes.grafica_categorias": """Muestra las 10 categorías de puesto con más vacantes. Una categoría es un grupo amplio de puestos parecidos (por ejemplo, operativos o administrativos).

Sirve para ver en qué tipo de trabajo se concentra la oferta.""",

    "vacantes.grafica_fecha": """Muestra cuántas vacantes se publicaron cada día, según la fecha de publicación registrada.

Sirve para ver los días con más movimiento. Solo se incluyen vacantes que tienen fecha.""",

    "vacantes.grafica_mes": """Muestra cuántas vacantes se registraron en cada mes, según su fecha de publicación.

Sirve para comparar la oferta de un mes con otro. Solo se incluyen vacantes que tienen fecha.""",

    "vacantes.grafica_calor": """Cruza empresas (filas) con meses (columnas). El número de cada cuadro es la cantidad de vacantes que esa empresa publicó en ese mes, y los colores más intensos indican más vacantes.

Incluye las 12 empresas con más vacantes. Solo se consideran vacantes con fecha.""",

    "vacantes.grafica_concentracion": """Muestra qué porcentaje del total de vacantes filtradas tiene cada una de las 10 empresas con más vacantes.

Si pocas empresas suman un porcentaje alto, la oferta depende de ellas. El porcentaje se calcula contra todas las vacantes del filtro, no solo contra las 10 mostradas.""",

    "vacantes.informe": """Es un resumen escrito que se genera solo con los filtros elegidos: cuántas vacantes y empresas hay, la empresa con más vacantes, el puesto más frecuente y la fecha con más publicaciones.

Describe lo registrado; no explica las causas ni representa todo el mercado laboral.""",

    "vacantes.tabla_buscador": """Lista las vacantes que cumplen los filtros y la búsqueda escrita. La búsqueda encuentra palabras en la empresa, el puesto, los requisitos, los beneficios, la descripción y el ID, sin importar acentos ni mayúsculas.

ID Vacante: identificador de la vacante.
Fecha: día en que se publicó.
Tipo de Vacante: puesto normalizado.
Estado: Activa o Inactiva.
Cierre: fecha en que la vacante termina, si se registró.

Se ordena de la más reciente a la más antigua.""",

    # ------------------------------------------------------------------ VACANTES · Empresas
    "vacantes.emp_total": """Es el número de empresas distintas registradas en el sistema: las que tienen vacantes, las que ya tienen seguimientos con personas y las que se dieron de alta aunque no tengan vacantes. Debajo se indica cuántas de ellas tienen al menos una vacante.""",

    "vacantes.emp_con_municipio": """Es el número de empresas de la tabla que ya tienen un municipio registrado. El municipio se captura a mano en este mismo apartado.""",

    "vacantes.emp_sin_municipio": """Es el número de empresas de la tabla que todavía no tienen municipio registrado. Estas empresas aparecen como «Indefinido» en el mapa por municipio.""",

    "vacantes.emp_sectores": """Es el número de sectores económicos distintos a los que pertenecen las empresas de la tabla (por ejemplo, textil o comercio).""",

    "vacantes.tabla_empresas": """Tiene una fila por empresa registrada, tenga o no vacantes.

Vacantes: total de vacantes de la empresa (0 si no ha ofrecido ninguna).
Vigentes: vacantes que siguen abiertas.
Puestos distintos: tipos de puesto diferentes que ha ofrecido.
Municipio: municipio donde se ubica, si se capturó.
Fuente de ubicación: de dónde viene el dato del municipio.""",

    "vacantes.emp_nueva": """Sirve para dar de alta una empresa que todavía no está en la lista. Solo el nombre es obligatorio; el sector, el municipio, la dirección y las coordenadas son opcionales y se pueden completar después.

Si se capturan coordenadas, la empresa aparece enseguida en el Mapa territorial aunque no tenga vacantes. Después de guardarla también se puede elegir al registrar una vacante o un seguimiento.

No se permite repetir una empresa que ya existe, aunque cambien las mayúsculas o los acentos.""",

    "vacantes.captura_ubicacion": """Sirve para registrar en qué municipio está una empresa, y opcionalmente su dirección y código postal.

Las empresas sin municipio aparecen primero en la lista. El dato se guarda tal como se captura, sin buscarlo ni estimarlo de forma automática.""",

    "vacantes.editor_coordenadas": """Sirve para registrar la ubicación exacta de cada empresa, con latitud y longitud, y así dibujarla en el Mapa territorial. Incluye todas las empresas registradas, tengan o no vacantes.

Se puede buscar una empresa por nombre y mostrar solo las que todavía no tienen coordenadas. Las coordenadas se pueden copiar desde Google Maps (clic derecho sobre el lugar) y pegarse en la columna «Pegar (lat, lon)», o escribirse por separado. En Tlaxcala, la latitud ronda 19.3 y la longitud ronda −98.2 (con signo menos).

Si no se conoce la ubicación se deja vacío; ningún dato se calcula ni se estima. Solo se guardan las filas que cambiaron.""",

    # ------------------------------------------------------------------ VACANTES · Nueva vacante
    "vacantes.alta_formulario": """Sirve para registrar una vacante nueva. Los campos marcados con * son obligatorios.

Cada registro corresponde a un solo puesto. El nombre del puesto se elige de un catálogo para que se agrupe igual que el resto de las vacantes, y se conserva también el texto original capturado. La vacante queda registrada con un ID nuevo.""",

    # ------------------------------------------------------------------ VACANTES · Carga Excel/CSV
    "vacantes.carga_recibidas": """Es el total de filas que trae el archivo subido.""",

    "vacantes.carga_nuevas": """Es el número de filas que se agregarán como vacantes nuevas al presionar el botón de guardar.""",

    "vacantes.carga_omitidas": """Es el número de filas que no se guardarán porque su ID ya existe en la base o porque están repetidas en el archivo. Cargar un archivo nunca sobrescribe una vacante existente.""",

    # ------------------------------------------------------------------ VACANTES · Editar / eliminar
    "vacantes.tabla_editar": """Lista las vacantes que coinciden con la búsqueda por empresa, puesto o ID (hasta 200).

ID Vacante: identificador de la vacante.
Fecha: día en que se publicó.
Tipo de Vacante: puesto normalizado.
Estado: Activa o Inactiva.

Al elegir una fila se puede editar o eliminar esa vacante.""",

    # ------------------------------------------------------------------ VACANTES · Vigencia
    "vacantes.vigencia_umbral": """Define cuántos días de antigüedad debe tener una vacante activa para aparecer en la lista. Por ejemplo, con 180 días se muestran las vacantes activas publicadas hace más de 180 días.

Solo cambia lo que se muestra; no modifica ninguna vacante.""",

    "vacantes.vigencia_activas": """Es el total de vacantes cuyo estado es «Activa», sin importar cuánto tiempo llevan publicadas.""",

    "vacantes.vigencia_vencidas": """Son las vacantes activas publicadas hace más días que el valor elegido arriba y que no tienen una fecha de cierre vigente. Se consideran posiblemente vencidas porque es probable que ya no estén abiertas, pero el sistema no lo confirma.

También se incluyen las activas que no tienen fecha de publicación.""",

    "vacantes.vigencia_con_cierre": """Es el número de vacantes que tienen registrada una fecha de cierre, es decir, el día en que la oferta termina.""",

    "vacantes.tabla_vigencia": """Lista las vacantes posiblemente vencidas, de la más antigua a la más reciente.

ID Vacante: identificador de la vacante.
Fecha: día en que se publicó.
Estado: Activa o Inactiva.

Desde aquí se pueden marcar como Inactivas, con confirmación previa. No se elimina ninguna vacante.""",

    # ------------------------------------------------------------------ VINCULACIONES · Indicadores superiores
    "vinculaciones.kpi_personas": """Es el número de personas distintas registradas en el sistema. Cada persona se cuenta una sola vez, aunque tenga varias vinculaciones.""",

    "vinculaciones.kpi_historicas": """Es el total de vinculaciones históricas registradas, sumando las de todas las personas. Una persona puede tener más de una.

Son los registros de vinculación de las personas; no son contrataciones.""",

    "vinculaciones.kpi_vinculados": """Es el número de personas cuyo estatus actual es «Vinculado».

El estatus de cada persona sale de su seguimiento más reciente con una empresa. Una persona sin seguimientos figura como «Vinculado» porque su registro histórico ya es una vinculación.""",

    "vinculaciones.kpi_colocados": """Es el número de personas cuyo estatus actual es «Colocado», es decir, que consiguieron un empleo. Si una persona tiene alguna colocación registrada, se toma la más reciente para definir su estatus.""",

    "vinculaciones.kpi_no_vinculados": """Es el número de personas cuyo estatus actual es «No vinculado», es decir, que no lograron una vinculación en su seguimiento más reciente.""",

    "vinculaciones.kpi_seguimientos": """Es el total de seguimientos registrados. Un seguimiento es el registro de una persona con una empresa y un puesto concretos, con su estatus, fecha y responsable.

Mide la actividad de vinculación con las empresas; por sí solo no equivale a una contratación.""",

    "vinculaciones.kpi_empresas": """Es el número de empresas distintas que aparecen en los seguimientos. Una empresa con varios seguimientos se cuenta una sola vez.""",

    # ------------------------------------------------------------------ VINCULACIONES · Nuevo seguimiento
    "vinculaciones.nuevo_formulario": """Sirve para registrar un seguimiento nuevo: una persona con una empresa y un puesto.

Primero se elige a la persona. La empresa y el puesto se escogen de los catálogos o de una vacante vigente (abierta); en ese caso se toman de la vacante. El sector se asigna según la empresa.

La vinculación histórica de origen es opcional y sirve para relacionar el seguimiento con un registro anterior de la persona.

La fecha de vinculación solo se guarda cuando el estatus es «Vinculado».""",

    # ------------------------------------------------------------------ VINCULACIONES · Editar / eliminar
    "vinculaciones.tabla_editar": """Lista los seguimientos que coinciden con la búsqueda por persona, empresa o ID (hasta 200), de los modificados más recientemente a los más antiguos.

ID: identificador del seguimiento.
Persona: nombre de la persona.
Empresa: empresa con la que se dio seguimiento.
Estatus: situación del seguimiento.
Vinculación: fecha de vinculación.

Al elegir una fila se puede editar o eliminar ese seguimiento.""",

    # ------------------------------------------------------------------ VINCULACIONES · Estadísticas
    "vinculaciones.grafica_estatus": """Reparte a las personas según su estatus actual (por ejemplo, Vinculado, Colocado o No vinculado). Cada porción es el porcentaje de personas con ese estatus.

El estatus sale del seguimiento más reciente de cada persona.""",

    "vinculaciones.grafica_historicas": """Muestra cuántas personas tienen 1, 2, 3 o más vinculaciones históricas. Cada barra es un número de vinculaciones y su altura es la cantidad de personas.

Sirve para saber cuántas personas se han vinculado más de una vez.""",

    "vinculaciones.grafica_anual": """Muestra cuántos seguimientos hay en cada año, separados por estatus con colores distintos. El año sale de la fecha de vinculación.

Solo se incluyen los seguimientos que tienen fecha de vinculación.""",

    "vinculaciones.grafica_empresas": """Muestra las 15 empresas con más seguimientos. Cada barra es una empresa y su largo es el número de seguimientos.

Sirve para ver con qué empresas se trabaja más.""",

    "vinculaciones.grafica_puestos": """Muestra los 15 puestos con más seguimientos. Cada barra es un puesto y su largo es el número de seguimientos.

Sirve para ver qué puestos se ocupan más en las vinculaciones.""",

    "vinculaciones.kpi_col_personas": """Es el número de personas cuyo estatus actual es «Colocado».""",

    "vinculaciones.kpi_col_registros": """Es el número de seguimientos con estatus «Colocado». Puede ser mayor que el de personas colocadas si una persona tiene más de un seguimiento con ese estatus.""",

    "vinculaciones.kpi_col_empresas": """Es el número de empresas distintas en las que hay al menos un seguimiento con estatus «Colocado».""",

    "vinculaciones.kpi_col_tasa": """Es el porcentaje de personas colocadas respecto a las personas vinculadas.

Se calcula dividiendo las personas con estatus «Colocado» entre las personas con estatus «Vinculado» o «Colocado».""",

    "vinculaciones.grafica_col_sexo": """Reparte a las personas colocadas según su sexo. Cada porción es el porcentaje del total de personas colocadas.""",

    "vinculaciones.grafica_col_municipio": """Muestra los 15 municipios donde viven más personas colocadas. Cada barra es un municipio y su largo es el número de personas colocadas.""",

    "vinculaciones.tabla_personas": """Tiene una fila por persona.

ID: identificador de la persona.
Vinculaciones: número de vinculaciones históricas que tiene.
Estatus: estatus actual, según su seguimiento más reciente.
Seguimientos: número de seguimientos que tiene con empresas.
Empresas: número de empresas distintas con las que se le dio seguimiento.
Empresa actual: empresa de su seguimiento más reciente.""",

    # ------------------------------------------------------------------ VINCULACIONES · Historial de una persona
    "vinculaciones.historial_persona": """Sirve para elegir a una persona y ver todo su historial: sus datos, sus vinculaciones, sus seguimientos con empresas y la calidad de su información.

La lista muestra el nombre, el identificador y el número de vinculaciones históricas de cada persona.""",

    # ------------------------------------------------------------------ VINCULACIONES · Exportar
    "vinculaciones.tabla_exportar": """Muestra los seguimientos que se descargarán, con persona, empresa, puesto, estatus, fechas de vinculación y colocación, y responsable.

El botón de descarga genera un archivo con todos los seguimientos.""",

    # ------------------------------------------------------------------ ADMINISTRACIÓN · Instituciones
    "instituciones.kpi_total": """Es el número de instituciones educativas (universidades y escuelas) que ya tienen al menos una persona asociada en la base. Solo se listan estas.""",

    "instituciones.kpi_con_coordenadas": """Es el número de instituciones que ya tienen su ubicación exacta registrada. Estas son las que aparecen en el Mapa territorial.""",

    "instituciones.kpi_sin_coordenadas": """Es el número de instituciones que todavía no tienen su ubicación exacta registrada. No aparecen en el Mapa territorial hasta que se registre.""",

    "instituciones.kpi_sin_tipo": """Es el número de instituciones a las que todavía no se les ha indicado si son universidad o escuela.""",

    "instituciones.editor": """Sirve para registrar el tipo (Universidad o Escuela), el municipio y la ubicación exacta de cada institución que ya tiene personas asociadas. Con esos datos se dibujan en el Mapa territorial.

Las coordenadas se pueden copiar desde Google Maps (clic derecho sobre el lugar) y pegarse en la columna «Pegar (lat, lon)», o escribirse por separado. En Tlaxcala, la latitud ronda 19.3 y la longitud ronda −98.2 (con signo menos).

Si no se conoce la ubicación se deja vacío; ningún dato se calcula ni se estima. Solo se guardan las filas que cambiaron. La columna «Personas» es el número de personas distintas asociadas a la institución.""",

    "instituciones.solo_sin_coordenadas": """Muestra únicamente las instituciones que todavía no tienen su ubicación exacta registrada, para capturarlas más rápido.""",
}


def texto(clave: str) -> str | None:
    """Texto de ayuda de `clave`, o None si no existe (la página no muestra ❓ en ese caso)."""
    valor = AYUDAS.get(clave)
    return valor.strip() if valor and valor.strip() else None
