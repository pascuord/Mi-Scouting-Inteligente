# Probar el framework con OpenAI

Como me has pedido no modificar ningún archivo de código ni de configuración, la forma de probar el modelo de OpenAI (actualmente configurado en el archivo `promptfooconfig.yaml` bajo el nombre `gpt-4o-mini`, que es la versión equivalente de la que hablas) es ejecutando la evaluación estándar.

El archivo de configuración ya incluye el proveedor de OpenAI, por lo que Promptfoo lo evaluará automáticamente junto a las preguntas definidas.

## Pasos para ejecutar la prueba

**1. Ejecuta el comando de evaluación**
Abre tu terminal en la raíz del proyecto (donde se encuentra `promptfooconfig.yaml`) y ejecuta:

```bash
npx promptfoo@latest eval
```

Este comando leerá el archivo YAML y lanzará las consultas hacia el pipeline utilizando tu modelo de OpenAI de forma automatizada (también evaluará el modelo de Groq para que puedas comparar).

**2. Visualiza los resultados**
Una vez finalizado el proceso en la terminal, puedes levantar la interfaz web interactiva ejecutando:

```bash
npx promptfoo@latest view
```

Esto abrirá una página en tu navegador (generalmente en `http://localhost:15500`). En esa interfaz podrás ver una tabla comparativa; simplemente fíjate en la columna que corresponde a **"OpenAI gpt-4o-mini"** para revisar las respuestas y latencias de este modelo en concreto.

## Notas adicionales

- Promptfoo leerá tu clave API `OPENAI_API_KEY` directamente del archivo `.env` que ya tienes configurado en la raíz del proyecto.
- Si en un futuro necesitas que el comando *únicamente* evalúe el modelo de OpenAI ignorando a los demás (sin modificar el código), puedes hacerlo filtrando por el id del proveedor si tuvieran IDs únicos, pero con la configuración actual lo más sencillo es ejecutar la evaluación completa y ver la columna de OpenAI en el visor web.
