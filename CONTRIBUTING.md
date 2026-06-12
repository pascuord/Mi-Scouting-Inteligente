# 🤝 Guía de Contribución — ScoutingInteligente

¡Bienvenido al repositorio de **ScoutingInteligente**! Este documento detalla las directrices y estándares para colaborar en el proyecto de manera ordenada, limpia y cumpliendo con los estándares de control de versiones requeridos para la entrega académica.

---

## 🧭 Flujo de Trabajo en Git

Para mantener un histórico limpio y legible, seguimos la metodología de desarrollo basada en **Feature Branches** y Pull Requests.

### 1. Nomenclatura de Ramas
Crea ramas descriptivas a partir de `main` siguiendo este patrón:
* `feature/nombre-de-la-mejora` (para nuevas funcionalidades o componentes de documentación).
* `bugfix/descripcion-del-error` (para corrección de errores).
* `docs/detalles-documentacion` (para adición de guías, esquemas o especificaciones).

*Ejemplos:*
```bash
git checkout -b docs/add-architecture-guide
git checkout -b feature/optimize-rate-limiter
```

### 2. Mensajes de Commit Estructurados
Los mensajes de commit deben seguir la convención de **Conventional Commits** para facilitar la lectura del histórico y la generación automática de changelogs:

```text
<tipo>(<ámbito>): <descripción breve en imperativo>

[cuerpo opcional detallando el porqué del cambio]
```

* **Tipos comunes:**
  * `feat`: Nueva característica.
  * `fix`: Corrección de un error.
  * `docs`: Cambios únicamente en documentación.
  * `refactor`: Refactorización de código sin añadir lógica ni corregir fallos.
  * `test`: Adición o modificación de pruebas o evaluaciones.

*Ejemplo de commit de documentación:*
```bash
git commit -m "docs(readme): añadir especificación de fórmulas de score y RAG"
```

---

## 🎨 Estándares de Código y Calidad

Para asegurar la legibilidad del código (en caso de ampliación futura), se deben respetar las siguientes directrices:

### 🐍 Python (PEP 8)
* Utiliza **Type Hints** siempre que sea posible para documentar las firmas de las funciones.
* Los docstrings deben seguir la convención **NumPy style** o **Sphinx style** explicando entradas, salidas y excepciones lanzadas.
* Todas las importaciones deben estar ordenadas (estándar, terceros y locales).

### 📊 Gestión de Datos
* Evita el almacenamiento persistente dentro de la imagen Docker. Las bases de datos generadas deben escribirse siempre en los directorios mapeados (`/data` o `/data_local`).
* Las consultas y transformaciones de datos masivos se realizan utilizando **Polars** por rendimiento en lugar de Pandas.

---

## 🧪 Pruebas y Evaluaciones de Modelos (Promptfoo)

Cualquier cambio en los prompts de los agentes (`src/scouting/agents/`) o en la lógica de procesamiento debe ser validado con el framework de evaluación antes de un merge a la rama principal:

1. Asegúrate de configurar la API Key necesaria en tu `.env`.
2. Ejecuta la matriz de evaluación de Promptfoo:
   ```bash
   npx promptfoo@latest eval
   ```
3. Verifica la calidad y la latencia utilizando el visor interactivo:
   ```bash
   npx promptfoo@latest view
   ```
4. Asegúrate de que las aserciones (evaluaciones del LLM-as-judge) aprueben en al menos un **90%** de los casos antes de enviar el pull request.

---

## 📋 Lista de Verificación antes de Enviar un Pull Request (PR)

Antes de abrir un PR o solicitar una revisión de tu contribución, confirma los siguientes puntos:
- [ ] Tu rama parte de la versión más reciente de `main`.
- [ ] El archivo `.env.example` se encuentra actualizado si has añadido variables de entorno.
- [ ] Has verificado localmente que los contenedores compilan sin errores (`docker compose build`).
- [ ] Has ejecutado `npx promptfoo@latest eval` y los resultados del benchmark no muestran regresiones de rendimiento o coste excesivo.
- [ ] No se ha commiteado ningún archivo de base de datos `.json`, índice `.index` o credenciales en el archivo `.env`.
