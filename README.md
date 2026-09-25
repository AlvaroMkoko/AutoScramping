# Módulo de matching — automatización de búsqueda de empleo

Primera pieza del pipeline: recibe una vacante (título + descripción) y decide
si es `match_fuerte`, `revisar` o `descartar`, comparándola contra tu perfil
(`data/job_analysis_report.json`).

## Cómo funciona

1. **Reglas duras** (`rules.py`) — replica exactamente los criterios que ya
   definiste en tu JSON (`criterios_de_fit_automatico`): salario mínimo, título
   y cédula, años de experiencia, nivel de inglés, stack. Si una vacante cae en
   `descarte_automatico`, se corta ahí — no gasta cómputo en embeddings.
2. **Similitud semántica** (`embeddings.py` + `candidate_profile.py`) — compara
   el texto de la vacante contra (a) tus habilidades/diferenciadores y (b) el
   patrón de tus puestos históricos con `fit_score >= 8`. Usa Ollama en local
   por default; si Ollama no responde, cae a TF-IDF (menos preciso, solo para
   pruebas — ver advertencia abajo).
3. **Score combinado** (`matcher.py`) — mezcla ambas señales con los pesos de
   `config.py` y aplica los umbrales para decidir.

## Fuentes de datos (`data/`)

- **`perfil_profesional.json`** — tu perfil rico y actualizado: identidad, stack
  técnico con niveles de confianza (0-1), proyectos con `peso_portfolio`, gaps
  a mencionar honestamente, objetivo profesional, y el mapeo de qué proyectos
  priorizar por categoría de vacante. **Es la fuente principal** — `candidate_profile.py`
  lo lee para casi todo.
- **`job_analysis_report.json`** — se conserva SOLO por su `catalogo_puestos`
  histórico (las 21 vacantes que ya evaluaste), usado como "ancla" semántica
  de qué tipo de puesto te ha hecho match en el pasado. Nada más de este
  archivo se usa ya.

Cuando actualices tu perfil (nuevas habilidades, nuevos proyectos, cambios en
tu nivel de inglés, etc.), edita `perfil_profesional.json` — no hace falta
tocar código.

### ⚠️ Datos personales — repo público

`perfil_profesional.json` y `job_analysis_report.json` contienen tu nombre,
teléfono, correo y tu historial real de vacantes/empresas, así que **no se
suben a git** (están en `.gitignore`). Lo que sí se sube es una plantilla sin
datos reales:

```bash
cp data/perfil_profesional.example.json data/perfil_profesional.json
cp data/job_analysis_report.example.json data/job_analysis_report.json
```

Edita esas dos copias locales con tu información real — el pipeline las lee
de ahí, y git las va a ignorar siempre.

## Setup

```bash
pip install -r requirements.txt

# Para embeddings semánticos reales (recomendado, no el fallback):
ollama pull nomic-embed-text
ollama serve
```

## Probarlo

```bash
python demo.py
```

Corre 4 vacantes de ejemplo y guarda los resultados en `resultados_demo.json`.

## ⚠️ Sobre el fallback TF-IDF

Si `ollama serve` no está corriendo, el matcher sigue funcionando pero usando
TF-IDF (comparación de palabras, no de significado). Con vocabularios chicos
esto puede **subestimar matches obvios** — lo vimos en las pruebas: una
vacante de RAG/LLMs que por reglas sacó 100/100 quedó descartada por el score
semántico aplastado del fallback. Para uso real, siempre corre esto con Ollama
activo.

## Ajustar el comportamiento

Todo lo que normalmente querrás tocar está en `config.py`:
- `UMBRAL_FIT_ALTO` / `UMBRAL_REVISION_MANUAL`: qué tan estricto es el filtro.
- `PESO_SEMANTICO_PERFIL` / `PESO_SEMANTICO_HISTORICO` / `PESO_REGLAS`: cuánto
  pesa cada señal (deben sumar 1.0).
- `FIT_HISTORICO_MINIMO`: desde qué fit_score histórico se usa una vacante
  pasada como "ancla" de referencia.

---

## Módulo de generación de CV (`cv_generator.py`)

Toma una vacante y genera un PDF personalizado a partir de tu plantilla real
(`templates/cv_template.tex.jinja`, derivada de tu `cv_alvaro.tex`).

### Cómo evita alucinaciones

`content_bank.py` contiene tus proyectos, logros y categorías de habilidades
**verídicos**, extraídos literalmente de tu plantilla y tus CVs ya generados.
Ollama (modelo de chat) solo puede **elegir, reordenar y priorizar** contenido
de ese banco — nunca escribir bullets, proyectos o logros nuevos. Cualquier
id, categoría o ítem que el modelo invente se descarta en `_validar_respuesta_llm`
y se registra como advertencia. Las únicas partes libremente generadas son
`title_line` y el `summary` (resumen de 4-5 líneas) — por diseño, y por eso
son las que debes revisar tú antes de aplicar (coincide con tu flujo semi-manual).

El prompt también incluye, tomados de `perfil_profesional.json`:
- **Gaps a mencionar honestamente**: si la vacante pide algo que tienes como
  gap (LLMs/RAG, SQL avanzado, CI/CD, AWS/GCP, inglés avanzado), el LLM puede
  reconocerlo en el summary con la frase exacta que tú definiste — nunca
  ocultarlo ni inventar experiencia que no tienes.
- **Pista de proyectos por categoría**: tu propio historial de qué proyecto
  priorizar según el tipo de vacante (GenAI/LLM, ML Engineering, Full-Stack,
  etc.), pasada como orientación, no como regla dura.
- **Objetivo profesional**: para que el summary refleje qué buscas realmente,
  no una genérica "busco crecer profesionalmente".

### Setup adicional

```bash
pip install -r requirements.txt   # ya incluye jinja2

# Necesitas un modelo de CHAT además de nomic-embed-text:
ollama pull llama3.1        # o el que prefieras — ajusta OLLAMA_CHAT_MODEL en config.py

# Necesitas xelatex instalado (el mismo compilador de tu plantilla original)
```

### Probarlo

```bash
python demo_generar_cv.py
```

Genera un PDF de ejemplo en `cv_generados/` y te avisa si hubo advertencias
de validación (contenido descartado por no estar en el banco).

### Ajustar tu banco de contenido

Cuando tengas un proyecto o logro nuevo, agrégalo directamente en
`content_bank.py` (no le pidas al LLM que lo invente). Igual si cambias tu
plantilla `.tex` — actualiza `templates/cv_template.tex.jinja` manteniendo
las etiquetas `\VAR{...}` y `\BLOCK{...}` en las secciones personalizables.

## Módulo de búsqueda de vacantes (`job_search.py` + `pipeline.py`)

Busca vacantes vía la **API de Adzuna** (no scraping — evita los problemas de
ToS/anti-bot de LinkedIn e Indeed que discutimos al inicio). Cobertura real
de México en `adzuna.com.mx`.

### Setup

1. Regístrate gratis en https://developer.adzuna.com/signup (instantáneo, solo
   confirmar email).
2. Copia `data/secrets.example.json` a `data/secrets.json` y pon tu `app_id`
   y `app_key` ahí. **Nunca subas `secrets.json` a git.**
3. Ajusta `ADZUNA_KEYWORDS` y `ADZUNA_WHERE` en `config.py` si quieres buscar
   otros términos o acotar por ciudad.

### Límite del tier gratuito

~1,000 llamadas/mes (~33/día). El módulo hace **1 llamada por keyword** (no
por página), así que con las 5 keywords default gastas ~5 llamadas por
corrida — puedes correrlo varias veces al día sin preocuparte, pero no lo
metas en un loop automático sin control.

### Cómo evita re-procesar lo mismo cada día

`data/vacantes_vistas.json` guarda los ids de Adzuna ya procesados. Cada
corrida de `pipeline.py` solo evalúa vacantes nuevas y marca el lote completo
como visto al final (match o no) — así no se repite el trabajo ni las
notificaciones día a día.

### Salario estructurado en vez de adivinado

Adzuna regresa `salary_min`/`salary_max` como campos ya parseados (aunque a
veces son estimados, no declarados por el empleador). `rules.py` y
`matcher.py` ahora aceptan ese valor directamente (`salario_conocido`) en vez
de depender solo del regex sobre la descripción truncada que da la API —
más confiable para el criterio de descarte por salario.

### Correr la búsqueda + matching

```bash
python pipeline.py
```

Imprime un resumen agrupado por `match_fuerte` / `revisar` / `descartar` y
guarda un reporte en `reportes/reporte_<fecha>.json`.

## Módulo de notificación por Telegram (`telegram_bot.py`)

Cierra el pipeline: `pipeline.py` manda un resumen por Telegram al terminar
cada corrida, y genera + adjunta el CV automáticamente para cada
`match_fuerte`. Para `revisar` solo manda la lista (título, empresa, score,
link) — no genera CV para las ~30 vacantes de "revisar" de cada corrida,
eso sería desperdiciar cómputo en vacantes de las que probablemente ni
apliques a la mitad. Si quieres el CV de una de "revisar", ya sabes generarlo
a mano con `generar_cv()` (ver `demo_generar_cv.py`).

**La postulación sigue siendo 100% manual.** El bot avisa y adjunta el PDF;
tú decides a cuáles aplicar y lo haces tú mismo, fuera de este sistema.

### Setup (2 minutos)

1. En Telegram, busca **@BotFather**, mándale `/newbot` y sigue las
   instrucciones. Te da un **token**.
2. Ponlo en `data/secrets.json` (copia `data/secrets.example.json`) como
   `"telegram_bot_token"`.
3. Busca a TU bot recién creado en Telegram y mándale cualquier mensaje
   (ej. "hola").
4. Corre:
   ```bash
   python get_telegram_chat_id.py
   ```
   Te imprime tu `chat_id` — cópialo a `data/secrets.json` como
   `"telegram_chat_id"`.
5. Ya está. La próxima vez que corras `python pipeline.py`, te llega la
   notificación.

### Si no configuras Telegram

`pipeline.py` sigue funcionando igual (búsqueda + matching + reporte JSON) —
simplemente imprime un aviso de que se saltó la notificación, en vez de
fallar.

## Estado del pipeline

Las 4 piezas ya están conectadas de punta a punta:

```
job_search.py (Adzuna) → matcher.py (reglas + semántica) → cv_generator.py (LaTeX + Ollama) → telegram_bot.py (aviso + CV adjunto)
                                    orquestado por pipeline.py
```

Lo que queda como trabajo futuro, si quieres seguir afinando:
- Calibrar más los umbrales/pesos de `config.py` con más corridas reales.
- Filtro adicional para roles "casi técnicos" que aún se cuelan en "revisar"
  (ej. preventa/consultoría que sí mencionan herramientas técnicas de verdad).
- Automatizar la corrida diaria (Task Scheduler en Windows) en vez de correr
  `python pipeline.py` a mano.
