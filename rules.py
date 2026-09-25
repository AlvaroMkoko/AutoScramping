"""Extracción de campos estructurados de una vacante en texto libre + motor de
reglas duras — implementa literalmente lo que ya definiste en
job_analysis_report.json -> instrucciones_para_agente.criterios_de_fit_automatico.
"""
import re
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class VacanteExtraida:
    salario_mensual_max: Optional[int]
    requiere_titulo_cedula: bool
    experiencia_años_min: Optional[float]
    nivel_ingles: str  # "no_requerido" | "intermedio" | "avanzado_b2_c1" | "avanzado_c1"
    acepta_pasante: bool
    stack_detectado: List[str]
    es_100_frontend: bool
    rol_no_tecnico: bool


STACK_KEYWORDS = [
    "python", "pytorch", "scikit-learn", "sklearn", "mlflow", "dvc", "fastapi",
    "docker", "evidently", "transformer", "java", "javascript", "rust", "git",
    "linux", "azure", "aws", "gcp", "sql", "postgresql", "mongodb", "langchain",
    "llamaindex", "rag", "faiss", "chromadb", "react", "vue", "node", "angular",
    "ci/cd", "github actions", "kubernetes",
]

# Términos de DOMINIO (no herramientas específicas) que indican que el puesto
# sí es de tech/IA aunque la descripción truncada de Adzuna no mencione una
# herramienta exacta. Son frases largas a propósito (no palabras sueltas como
# "ai" o "ml") para evitar falsos positivos por substring — por ejemplo "ai"
# suelto haría match dentro de "email".
DOMAIN_KEYWORDS = [
    "machine learning", "inteligencia artificial", "artificial intelligence",
    "data scientist", "data science", "mlops", "deep learning",
    "ai engineer", "ml engineer", "computer vision", "genai",
    "generative ai", "ia generativa", "llm", "nlp",
]

FRONTEND_ONLY_KEYWORDS = {"react", "vue", "css", "html", "angular", "frontend"}

# Roles que, aunque mencionen tecnología o "inteligencia artificial" de pasada,
# NO son puestos de ingeniería (ventas, preventa, marketing, diseño, RRHH).
# Se busca en el TÍTULO (no en la descripción completa) porque un puesto de
# ingeniería real puede mencionar "ventas" en la descripción sin ser de ventas,
# pero el título de un puesto de ventas casi siempre lo delata.
ROL_NO_TECNICO_PATRONES = [
    r"\bventas\b", r"\bsales\b", r"\bpreventa\b", r"\bpre-venta\b",
    r"\bpartner\b", r"\baccount (executive|manager)\b",
    r"\bmarketing\b", r"\bdise[ñn]ador(a)?\b", r"\bdesigner\b", r"\bcreative\b",
    r"\brecruiter\b", r"\breclutador(a)?\b", r"\brecursos humanos\b",
    r"\bcommerce intern\b", r"\bbusiness solutions\b",
]


def _detectar_salario(texto: str) -> Optional[int]:
    m = re.search(r"(\d{1,3}(?:[,.]\d{3})?)\s*k\b", texto, re.IGNORECASE)
    if m:
        return int(float(m.group(1).replace(",", "."))) * 1000
    m = re.search(r"\$?\s?(\d{2,3}[,.]\d{3})\s*(?:mxn|pesos)?", texto, re.IGNORECASE)
    if m:
        return int(m.group(1).replace(",", "").replace(".", ""))
    return None


def _detectar_titulo_cedula(texto: str) -> bool:
    patrones = ["título y cédula", "titulo y cedula", "cédula profesional",
                "título profesional obligatorio"]
    t = texto.lower()
    return any(p in t for p in patrones)


def _detectar_experiencia_min(texto: str) -> Optional[float]:
    m = re.search(r"(\d+)\s*\+?\s*años? de experiencia", texto, re.IGNORECASE)
    if m:
        return float(m.group(1))
    if "sin experiencia" in texto.lower() or "recién egresado" in texto.lower():
        return 0.0
    return None


def _detectar_nivel_ingles(texto: str) -> str:
    t = texto.lower()
    if "inglés" not in t and "ingles" not in t and "english" not in t:
        return "no_requerido"
    if "c1" in t or "fluido" in t or "nativo" in t:
        return "avanzado_c1"
    if "b2" in t:
        return "avanzado_b2_c1"
    if "intermedio" in t or "b1" in t:
        return "intermedio"
    return "intermedio"  # menciona inglés sin especificar nivel -> asumir conservador


def _detectar_pasante(texto: str) -> bool:
    t = texto.lower()
    return any(p in t for p in
               ["pasante", "junior", "jr.", "jr ", "recién egresado", "sin experiencia", "entry level"])


def _detectar_stack(texto: str) -> List[str]:
    t = texto.lower()
    encontrados = [kw for kw in STACK_KEYWORDS if kw in t]
    encontrados += [kw for kw in DOMAIN_KEYWORDS if kw in t]
    return encontrados


def _detectar_rol_no_tecnico(titulo: str) -> bool:
    t = titulo.lower()
    return any(re.search(patron, t) for patron in ROL_NO_TECNICO_PATRONES)


def extraer_vacante(titulo: str, descripcion: str,
                    salario_conocido: Optional[float] = None) -> VacanteExtraida:
    texto_completo = f"{titulo}\n{descripcion}"
    stack = _detectar_stack(texto_completo)
    es_frontend = bool(stack) and set(stack).issubset(FRONTEND_ONLY_KEYWORDS)
    # Si ya tenemos un salario estructurado (ej. de la API de Adzuna), es más
    # confiable que adivinarlo con regex de una descripción truncada.
    salario = salario_conocido if salario_conocido is not None else _detectar_salario(texto_completo)
    return VacanteExtraida(
        salario_mensual_max=salario,
        requiere_titulo_cedula=_detectar_titulo_cedula(texto_completo),
        experiencia_años_min=_detectar_experiencia_min(texto_completo),
        nivel_ingles=_detectar_nivel_ingles(texto_completo),
        acepta_pasante=_detectar_pasante(texto_completo),
        stack_detectado=stack,
        es_100_frontend=es_frontend,
        rol_no_tecnico=_detectar_rol_no_tecnico(titulo),
    )


@dataclass
class VeredictoReglas:
    descartar: bool
    razones_descarte: List[str]
    revision_manual: bool
    razones_revision: List[str]
    score_reglas: float  # 0-100; solo tiene sentido si no se descarta


def evaluar_reglas(v: VacanteExtraida) -> VeredictoReglas:
    # --- descarte_automatico ---
    razones_descarte = []
    if v.salario_mensual_max is not None and v.salario_mensual_max < 15000:
        razones_descarte.append(f"Salario {v.salario_mensual_max} < 15,000 MXN")
    if v.requiere_titulo_cedula:
        razones_descarte.append("Requiere título y cédula (aún en trámite)")
    if v.experiencia_años_min is not None and v.experiencia_años_min >= 3:
        razones_descarte.append(f"Requiere {v.experiencia_años_min:g}+ años de experiencia formal")
    if v.nivel_ingles == "avanzado_c1":
        razones_descarte.append("Requiere inglés C1 fluido")
    if v.es_100_frontend:
        razones_descarte.append("Stack 100% frontend, sin componente de IA/backend")

    if razones_descarte:
        return VeredictoReglas(True, razones_descarte, False, [], 0.0)

    # --- requiere_revision_manual ---
    razones_revision = []
    if v.nivel_ingles == "avanzado_b2_c1":
        razones_revision.append("Requiere inglés B2 — evaluar si el puesto lo vale")
    if v.experiencia_años_min is not None and v.experiencia_años_min >= 2:
        razones_revision.append("Requiere 2+ años — evaluar equivalencia académica")

    # --- fit_alto_auto (score proporcional a cuántas señales positivas cumple) ---
    señales = [
        v.acepta_pasante,
        "python" in v.stack_detectado,
        ("docker" in v.stack_detectado) or ("git" in v.stack_detectado),
        v.nivel_ingles in ("no_requerido", "intermedio"),
        (v.salario_mensual_max is None) or (v.salario_mensual_max >= 18000),
    ]
    score_reglas = 100 * sum(señales) / len(señales)

    # PENALIZACIÓN POR AUSENCIA DE STACK: sin esto, cualquier puesto que
    # mencione "Jr." o "junior" en el título (reclutamiento, ventas, diseño,
    # lo que sea) saca un score alto solo por esa palabra, aunque no tenga
    # NADA que ver con tecnología. Si no se detectó ni un solo término del
    # stack técnico, el puesto casi seguro no es relevante — se capa el
    # score. IMPORTANTE: esto NO se agrega a razones_revision a propósito —
    # esa lista fuerza la decisión a "revisar" sin importar el score final
    # (ver matcher.py). Queremos que un score bajo caiga a "descartar" de
    # forma natural, no que se fuerce una revisión manual para cada puesto
    # sin stack detectado (eso fue justo el bug: infló "revisar" en vez de
    # reducir el ruido).
    if not v.stack_detectado:
        score_reglas = min(score_reglas, 20.0)

    # Rol claramente no técnico (ventas, preventa, marketing, diseño, RRHH)
    # detectado en el TÍTULO: penalización más fuerte que la de "sin stack",
    # porque aquí SÍ puede haber keywords de dominio (ej. "Google Cloud",
    # "IA") que de otro modo inflarían el score de un puesto de ventas.
    if v.rol_no_tecnico:
        score_reglas = min(score_reglas, 10.0)

    return VeredictoReglas(False, [], bool(razones_revision), razones_revision, score_reglas)
