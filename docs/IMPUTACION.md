# Imputación proporcional de datos faltantes

Instrucción de la dependencia: reducir los datos nulos («Indefinido») que aparecen en las estadísticas. Esta es la forma en que se hizo y cómo justificarla.

## Qué hace

Para las columnas `sexo`, `edad`, `escolaridad`, `carrera`, `Institución`, `grupo_prioritario` y `area_carrera`, a cada persona que no tiene el dato se le asigna un valor siguiendo la **distribución de las personas que sí lo tienen** (probabilidad frecuencial o empírica):

    proporción del valor A = personas con el valor A ÷ personas con dato conocido
    personas que reciben A = proporción de A × personas sin dato

Ejemplo: 100 personas con carrera conocida (60 Derecho, 40 Contaduría) y 10 sin carrera → 6 reciben Derecho y 4 Contaduría.

Reglas del método:

1. Cuenta personas, no registros: una persona con varios registros cuenta una sola vez.
2. Si la persona tiene el dato en otro de sus registros, se usa ese dato real y no se imputa nada.
3. Es determinista: con los mismos datos siempre da el mismo resultado (se ordena a las personas sin dato con un código estable derivado de su ID, no con azar), y no depende del orden en que se capturaron.
4. El reparto es exacto: cada valor recibe su proporción con diferencia máxima de una persona.
5. La edad (numérica) se completa con valores tomados de la distribución de edades conocidas.
6. `municipio` NO se imputa: el mapa y el RIDET dependen de dónde vive realmente la persona.

## Qué NO hace

- No escribe nada en la base de datos. Se calcula al consultar; el dato original sigue intacto.
- Los formularios (alta, edición) usan siempre los datos capturados, nunca los imputados, para que un valor imputado no se guarde como real.
- Para ver los datos como se capturaron: `IMPUTAR_DATOS_FALTANTES = False` en `vinculate/core/constantes.py`.

## Cómo se ve en la app

- Inicio y Personas: plegable «Datos faltantes completados» con el método y la tabla de cuántas personas se completaron por columna.
- Ficha de la persona: el valor aparece como «(imputado)» y cuenta como dato incompleto en «Calidad de datos».
- Directorio y Explorador: columna «Datos completados» (también en las exportaciones).

## Limitaciones (para decirlo con honestidad en el informe)

- La imputación proporcional conserva la distribución del conjunto, así que sirve para totales, porcentajes y gráficas.
- El valor que recibe una persona en particular no es un hecho sobre ella; su acierto individual es modesto (parecido a adivinar con la misma distribución).
- Si falta mucho de una misma columna, las gráficas se parecerán cada vez más a la distribución de las personas con dato.

## Evidencia para el informe

`python scripts/evaluar_imputacion.py ARCHIVO.csv` esconde al azar una parte de los datos conocidos, los imputa y mide el acierto individual y cuánto cambia la distribución del conjunto (ver el encabezado del script). Se corre en la computadora de quien lo use; no escribe en la base.

## Texto de justificación (borrador, en primera persona)

Para completar los datos faltantes usamos una distribución proporcional basada en la probabilidad frecuencial. Como no sabemos la carrera o la institución de las personas que no la registraron, supusimos que se comportan igual que el resto del grupo que sí respondió. Calculamos la proporción de cada valor entre las personas con dato conocido y repartimos a las personas sin dato en esa misma proporción. Si una persona tenía el dato en otro de sus registros, usamos ese dato real. El resultado conserva la distribución original del grupo, por eso es adecuado para totales y gráficas, aunque el valor asignado a una persona en concreto no es un dato confirmado. Cada valor imputado queda marcado, no se guarda en la base de datos y el proceso se puede apagar para volver a ver los datos tal como se capturaron.
