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
}


def texto(clave: str) -> str | None:
    """Texto de ayuda de `clave`, o None si no existe (la página no muestra ❓ en ese caso)."""
    valor = AYUDAS.get(clave)
    return valor.strip() if valor and valor.strip() else None
