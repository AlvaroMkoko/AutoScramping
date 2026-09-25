"""Generador de CV personalizado por vacante.

Flujo:
  1. Construye un prompt para Ollama (modelo de CHAT) con: tu perfil, la
     vacante, y el banco de contenido verídico (content_bank.py).
  2. Le pide que devuelva JSON: qué título usar, qué resumen escribir, qué
     categorías de skills mostrar (y en qué orden), qué proyectos incluir
     (y qué bullets de cada uno), y en qué orden los logros.
  3. VALIDA esa respuesta contra el banco: cualquier bullet, categoría o id
     que el modelo invente y no exista en content_bank.py se descarta. El
     título y el resumen son la única parte libremente generada — por
     diseño, y por eso son los que debes revisar tú antes de aplicar.
  4. Renderiza la plantilla Jinja2 y compila con xelatex.
"""
from __future__ import annotations
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from jinja2 import Environment, FileSystemLoader

from config import (
    OLLAMA_HOST, OLLAMA_CHAT_MODEL, CV_TEMPLATE_PATH, CV_OUTPUT_DIR,
    MAX_PROYECTOS_EN_CV,
)
from content_bank import SKILLS_CATALOG, PROJECTS, LOGROS, DATOS_FIJOS, PROJECT_ID_ALIASES
from candidate_profile import load_candidate_profile

PROJECTS_BY_ID = {p["id"]: p for p in PROJECTS}
LOGROS_BY_ID = {l["id"]: l for l in LOGROS}


# Caracteres especiales de LaTeX que DEBEN escaparse en cualquier texto libre
# (title_line, summary) generado por el LLM. Si no se escapan, un simple "R&D"
# o "50%" en el texto rompe la compilación (o peor, se interpreta como código).
_LATEX_ESCAPES = [
    ("\\", r"\textbackslash{}"),
    ("&", r"\&"),
    ("%", r"\%"),
    ("$", r"\$"),
    ("#", r"\#"),
    ("_", r"\_"),
    ("{", r"\{"),
    ("}", r"\}"),
    ("~", r"\textasciitilde{}"),
    ("^", r"\textasciicircum{}"),
]


def _escape_latex(texto: str) -> str:
    """Escapa caracteres especiales de LaTeX en texto libre (NO usar en contenido
    que ya viene de content_bank.py — ese ya está escapado a mano correctamente)."""
    for char, escapado in _LATEX_ESCAPES:
        texto = texto.replace(char, escapado)
    return texto


def _construir_pista_categorias(proyectos_por_categoria: Dict[str, List[str]]) -> str:
    """Traduce instrucciones_para_agente.proyectos_a_incluir_por_categoria (con
    los ids abreviados del perfil, ej. 'P1-Transformer') a nombres de proyecto
    reales, para dárselo al LLM como PISTA orientativa (no como regla dura)."""
    lineas = []
    for categoria, ids_abreviados in proyectos_por_categoria.items():
        nombres = []
        for pid in ids_abreviados:
            real_id = PROJECT_ID_ALIASES.get(pid, pid if pid in PROJECTS_BY_ID else None)
            if real_id and real_id in PROJECTS_BY_ID:
                titulo = PROJECTS_BY_ID[real_id]["titulo"]
                if titulo not in nombres:
                    nombres.append(titulo)
        if nombres:
            lineas.append(f'- Para vacantes tipo "{categoria}": ' + " > ".join(nombres))
    return "\n".join(lineas)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Prompt a Ollama
# ─────────────────────────────────────────────────────────────────────────────

def _construir_prompt(titulo_vacante: str, empresa: str, descripcion_vacante: str,
                       fit_razon: Optional[str] = None, categoria: Optional[str] = None) -> str:
    perfil = load_candidate_profile()

    catalogo_skills_txt = "\n".join(
        f'- "{cat}": {items}' for cat, items in SKILLS_CATALOG.items()
    )
    catalogo_proyectos_txt = "\n".join(
        f'- id="{p["id"]}" ({p["titulo"]}, peso_portfolio={p["peso_portfolio"]}): '
        f'{len(p["bullets"])} bullets disponibles (índices 0 a {len(p["bullets"]) - 1})'
        for p in PROJECTS
    )
    catalogo_logros_txt = "\n".join(f'- id="{l["id"]}"' for l in LOGROS)

    gaps_txt = "\n".join(f'- {k}: "{v}"' for k, v in perfil.gaps_a_mencionar_honestamente.items())

    pista_categorias = _construir_pista_categorias(perfil.proyectos_por_categoria)
    pista_categoria_actual = ""
    if categoria:
        pista_categoria_actual = f'\nCategoría de esta vacante (según quien la clasificó): "{categoria}"\n'

    objetivo = perfil.objetivo_profesional

    return f"""Eres un asistente que personaliza un CV para una vacante específica.

REGLA MÁS IMPORTANTE: NO inventes habilidades, proyectos, logros ni cifras que
no estén en los catálogos de abajo. Tu única libertad creativa es en
"title_line" y "summary" — y ahí también debes basarte SOLO en los hechos del
perfil que te doy, sin inventar experiencia profesional, tecnologías nuevas o
resultados que no existan.

REGLA DE HONESTIDAD: si el stack de la vacante pide algo de la lista de
"gaps a mencionar honestamente" de abajo, está BIEN reconocerlo brevemente en
el summary usando esa frase (o una muy cercana) — NO lo ocultes ni finjas
experiencia que no tienes. Un summary honesto sobre gaps es mejor que uno que
oculta información.

REGLA DE VOZ: el summary y el title_line se escriben en PRIMERA PERSONA
implícita, como en un CV real ("Ingeniero de IA con experiencia en...",
NUNCA "El candidato es un ingeniero..."). No uses la palabra "candidato" en
ningún campo — esa palabra es solo una etiqueta interna de este sistema, no
texto para el CV.

REGLA DE DENSIDAD: este CV debe verse completo, no escueto. Para cada
proyecto que elijas, incluye la MAYORÍA de sus bullets disponibles (no solo
1) salvo que claramente no apliquen a esta vacante. Igual con skills_rows:
selecciona varios ítems por categoría, no solo uno.

## Perfil del candidato (información de referencia — NO la copies literalmente, redacta el summary con tus propias palabras en primera persona)
{perfil.texto_perfil()}

## Qué busca el candidato (para que el summary lo refleje, sin inventar)
Tipo de puesto: {objetivo.get('tipo_puesto_buscado', '')}
Descripción de objetivo: {objetivo.get('descripcion', '')}

## Gaps a mencionar honestamente si la vacante los requiere
Las claves de la izquierda (LLMs_RAG, SQL_avanzado, etc.) son etiquetas
INTERNAS de este sistema — NUNCA las escribas literalmente en el summary.
Usa solo el texto de la derecha, tejido de forma natural en la prosa (ej. en
vez de "Reconocimiento honesto: LLMs_RAG en adopción activa", escribe algo
como "actualmente profundizando en RAG y LLMs como parte de un proyecto en
curso"). Si ningún gap de la lista aplica a esta vacante, no menciones nada.
{gaps_txt}

## Vacante a la que se postula
Título: {titulo_vacante}
Empresa: {empresa}
Descripción: {descripcion_vacante}
{f"Nota de fit previo: {fit_razon}" if fit_razon else ""}
{pista_categoria_actual}
## Pistas de qué proyectos priorizar según el tipo de vacante (orientativas, basadas en tu propio historial — no obligatorias si la descripción sugiere otra cosa)
{pista_categorias}

## Catálogo de categorías de habilidades (elige y ordena EXACTAMENTE 7, usando
   SOLO estas categorías e ítems, verbatim):
{catalogo_skills_txt}

## Catálogo de proyectos disponibles (elige {MAX_PROYECTOS_EN_CV}, ordénalos
   por relevancia a la vacante, y elige qué bullets de cada uno incluir por
   índice — puedes usar todos o un subconjunto, en el orden que prefieras):
{catalogo_proyectos_txt}

## Catálogo de logros (ordénalos por relevancia, incluye ambos ids):
{catalogo_logros_txt}

Responde ÚNICAMENTE con este JSON (sin texto antes ni después, sin markdown):
{{
  "title_line": "subtítulo corto bajo el nombre, adaptado al rol",
  "summary": "resumen de 4-5 líneas: quién es, en qué es bueno, qué busca — grounded en el perfil real, reconociendo gaps relevantes si aplica",
  "skills_rows": [
    {{"category": "nombre exacto de una categoría del catálogo", "items_selected": ["ítems exactos de esa categoría"]}}
  ],
  "projects": [
    {{"id": "id exacto del catálogo de proyectos", "bullet_indices": [0, 1, 2]}}
  ],
  "logros_order": ["id1", "id2"]
}}"""


def _llamar_ollama_chat(prompt: str) -> str:
    resp = requests.post(
        f"{OLLAMA_HOST}/api/chat",
        json={
            "model": OLLAMA_CHAT_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "format": "json",
            "stream": False,
            "think": False,  # crítico para modelos "thinking" (qwen3, etc.):
                              # sin esto anteponen un bloque <think>...</think>
                              # antes del JSON y rompen el parseo. Se ignora sin
                              # error en modelos que no soportan pensamiento.
            "options": {"temperature": 0.2},
        },
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


# ─────────────────────────────────────────────────────────────────────────────
# 2. Validación estricta contra el banco (aquí se evita la alucinación)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ContenidoValidado:
    title_line: str
    summary: str
    skills_rows: List[Dict[str, Any]]
    proyectos: List[Dict[str, Any]]
    logros: List[str]
    advertencias: List[str]


def _validar_respuesta_llm(raw_json: str) -> ContenidoValidado:
    advertencias: List[str] = []
    # Red de seguridad: si el modelo antepuso un bloque <think>...</think>
    # pese a think=False (puede pasar según versión de Ollama/modelo), lo
    # quitamos antes de intentar parsear JSON.
    raw_json = re.sub(r"<think>.*?</think>\s*", "", raw_json, flags=re.DOTALL)
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        advertencias.append("El LLM no devolvió JSON válido — usando contenido por defecto.")
        return _contenido_por_defecto(advertencias)

    # --- title_line / summary: libres, pero con longitud saneada y ESCAPADAS ---
    title_line = str(data.get("title_line", "")).strip() or "Ingeniero de Inteligencia Artificial"
    summary = str(data.get("summary", "")).strip()
    if not summary:
        advertencias.append("El LLM no generó summary — usando uno genérico del perfil.")
        summary = ("Ingeniero de IA en formación con experiencia construyendo sistemas de "
                   "ML de extremo a extremo. Busco un rol donde aplicar mi stack de MLOps "
                   "y mi capacidad de entrega bajo presión.")
    title_line = _escape_latex(title_line)
    summary = _escape_latex(summary)

    # --- skills_rows: whitelist estricta contra SKILLS_CATALOG, con relleno ---
    skills_rows = []
    categorias_usadas = set()
    for fila in data.get("skills_rows", []):
        cat = fila.get("category")
        if cat not in SKILLS_CATALOG:
            advertencias.append(f"Categoría de skills inventada descartada: {cat!r}")
            continue
        if cat in categorias_usadas:
            continue  # evita categorías duplicadas
        items_validos = [it for it in fila.get("items_selected", []) if it in SKILLS_CATALOG[cat]]
        if not items_validos:
            items_validos = SKILLS_CATALOG[cat]  # si no seleccionó nada válido, usa todos
        skills_rows.append({"label": cat, "valores": " $\\cdot$ ".join(items_validos)})
        categorias_usadas.add(cat)

    if len(skills_rows) < 5:
        # En vez de tirar las selecciones válidas que sí haya, se RELLENA con
        # categorías por default no usadas aún, preservando lo que el LLM
        # eligió bien.
        advertencias.append(
            f"Solo {len(skills_rows)} categorías de skills válidas — rellenando con el catálogo por defecto."
        )
        for fila_default in _default_skills_rows():
            if len(skills_rows) >= 7:
                break
            if fila_default["label"] not in categorias_usadas:
                skills_rows.append(fila_default)
                categorias_usadas.add(fila_default["label"])
    skills_rows = skills_rows[:7]

    # --- proyectos: whitelist estricta contra PROJECTS, con relleno ---
    proyectos = []
    ids_usados = set()
    for proy in data.get("projects", []):
        pid = proy.get("id")
        if pid not in PROJECTS_BY_ID:
            advertencias.append(f"Proyecto inventado descartado: {pid!r}")
            continue
        if pid in ids_usados:
            continue  # evita proyectos duplicados
        banco = PROJECTS_BY_ID[pid]
        indices = [i for i in proy.get("bullet_indices", []) if isinstance(i, int) and 0 <= i < len(banco["bullets"])]
        if not indices:
            indices = list(range(len(banco["bullets"])))
        proyectos.append({
            "titulo": banco["titulo"],
            "tech_line": banco["tech_line"],
            "bullets": [banco["bullets"][i] for i in indices],
        })
        ids_usados.add(pid)

    if len(proyectos) < MAX_PROYECTOS_EN_CV:
        # RELLENA con proyectos no usados aún, en orden de peso_portfolio,
        # en vez de dejar el CV con menos proyectos de los que debería tener.
        advertencias.append(
            f"Solo {len(proyectos)} proyecto(s) válido(s) devuelto(s) — rellenando por peso_portfolio."
        )
        for banco in _proyectos_por_prioridad():
            if len(proyectos) >= MAX_PROYECTOS_EN_CV:
                break
            if banco["id"] not in ids_usados:
                proyectos.append({
                    "titulo": banco["titulo"],
                    "tech_line": banco["tech_line"],
                    "bullets": banco["bullets"],
                })
                ids_usados.add(banco["id"])
    proyectos = proyectos[:MAX_PROYECTOS_EN_CV]

    # --- logros: whitelist estricta, deben ser exactamente los ids conocidos ---
    logros_ids = [lid for lid in data.get("logros_order", []) if lid in LOGROS_BY_ID]
    faltantes = [lid for lid in LOGROS_BY_ID if lid not in logros_ids]
    logros_ids.extend(faltantes)  # asegura que los 2 logros siempre aparezcan
    logros = [LOGROS_BY_ID[lid]["texto"] for lid in logros_ids]

    # --- chequeo de voz: la palabra "candidato" nunca debe aparecer en texto libre ---
    if re.search(r"\bcandidat[oa]\b", title_line, re.IGNORECASE) or \
       re.search(r"\bcandidat[oa]\b", summary, re.IGNORECASE):
        advertencias.append(
            "El LLM usó la palabra 'candidato' en tercera persona (debía ser primera "
            "persona) — REVISA Y EDITA el title_line/summary manualmente antes de aplicar."
        )

    return ContenidoValidado(title_line, summary, skills_rows, proyectos, logros, advertencias)


_PESO_ORDEN = {"muy alto": 0, "alto": 1, "medio-alto": 2, "medio": 3, "bajo-medio": 4, "bajo": 5}


def _proyectos_por_prioridad() -> List[Dict[str, Any]]:
    """PROJECTS ordenado por peso_portfolio (más alto primero), para usarse
    al rellenar huecos si el LLM no devolvió suficientes proyectos válidos."""
    def peso(p):
        texto = p.get("peso_portfolio", "medio").split(" (")[0]
        return _PESO_ORDEN.get(texto, 3)
    return sorted(PROJECTS, key=peso)


def _default_skills_rows() -> List[Dict[str, str]]:
    orden_default = ["Lenguajes", "IA y Deep Learning", "MLOps", "Cloud e infra",
                     "Ingeniería SW", "LLMs y GenAI", "Interpretabilidad"]
    return [{"label": cat, "valores": " $\\cdot$ ".join(SKILLS_CATALOG[cat])} for cat in orden_default]


def _contenido_por_defecto(advertencias: List[str]) -> ContenidoValidado:
    proyectos = [
        {"titulo": p["titulo"], "tech_line": p["tech_line"], "bullets": p["bullets"]}
        for p in PROJECTS[:MAX_PROYECTOS_EN_CV]
    ]
    logros = [l["texto"] for l in LOGROS]
    return ContenidoValidado(
        title_line="Ingeniero de Inteligencia Artificial",
        summary=("Ingeniero de IA en formación con experiencia construyendo sistemas de "
                 "ML de extremo a extremo: Transformers desde cero, MLOps completo y "
                 "despliegue en producción."),
        skills_rows=_default_skills_rows(),
        proyectos=proyectos,
        logros=logros,
        advertencias=advertencias,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. Render + compilación
# ─────────────────────────────────────────────────────────────────────────────

def _render_tex(contenido: ContenidoValidado) -> str:
    env = Environment(
        loader=FileSystemLoader(str(CV_TEMPLATE_PATH.parent)),
        block_start_string=r"\BLOCK{", block_end_string="}",
        variable_start_string=r"\VAR{", variable_end_string="}",
        comment_start_string=r"\#{", comment_end_string="}",
        line_statement_prefix="%%",
        line_comment_prefix="%#",
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
    )
    template = env.get_template(CV_TEMPLATE_PATH.name)
    return template.render(
        nombre=DATOS_FIJOS["nombre"],
        telefono=DATOS_FIJOS["telefono"],
        email=DATOS_FIJOS["email"],
        github=DATOS_FIJOS["github"],
        educacion=DATOS_FIJOS["educacion"],
        certificaciones=DATOS_FIJOS["certificaciones"],
        idiomas=DATOS_FIJOS["idiomas"],
        title_line=contenido.title_line,
        summary=contenido.summary,
        skills_rows=contenido.skills_rows,
        proyectos=contenido.proyectos,
        logros=contenido.logros,
    )


def _slug(texto: str) -> str:
    s = re.sub(r"[^\w\s-]", "", texto).strip().lower()
    return re.sub(r"[\s_-]+", "_", s)[:40]


def _compilar_pdf(tex_path: Path) -> Path:
    for _ in range(2):  # 2 pasadas por si hyperref necesita resolver referencias
        result = subprocess.run(
            ["xelatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
            cwd=tex_path.parent, capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"xelatex falló compilando {tex_path.name}:\n{result.stdout[-3000:]}"
            )
    return tex_path.with_suffix(".pdf")


# ─────────────────────────────────────────────────────────────────────────────
# 4. Función pública
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CVGenerado:
    pdf_path: Path
    tex_path: Path
    advertencias: List[str]


def generar_cv(titulo_vacante: str, empresa: str, descripcion_vacante: str,
               fit_razon: Optional[str] = None, categoria: Optional[str] = None) -> CVGenerado:
    prompt = _construir_prompt(titulo_vacante, empresa, descripcion_vacante, fit_razon, categoria)
    raw = _llamar_ollama_chat(prompt)
    contenido = _validar_respuesta_llm(raw)

    tex_source = _render_tex(contenido)

    CV_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    nombre_archivo = f"CV_{_slug(empresa)}_{_slug(titulo_vacante)}"
    tex_path = CV_OUTPUT_DIR / f"{nombre_archivo}.tex"
    tex_path.write_text(tex_source, encoding="utf-8")

    pdf_path = _compilar_pdf(tex_path)
    return CVGenerado(pdf_path=pdf_path, tex_path=tex_path, advertencias=contenido.advertencias)
