"""Carga el perfil del candidato desde DOS fuentes:

  - perfil_profesional.json: perfil rico y actualizado (identidad, stack con
    niveles de confianza, proyectos con peso_portfolio, gaps a mencionar
    honestamente, objetivo profesional). Es la fuente principal.
  - job_analysis_report.json: se mantiene SOLO por su catálogo histórico de
    vacantes ya evaluadas (catalogo_puestos), usado como "ancla" semántica de
    qué tipo de puesto te ha hecho match en el pasado. No se usa nada más
    de este archivo — perfil_profesional.json lo reemplaza en todo lo demás.

Este módulo NO decide nada — solo transforma esas fuentes en texto listo
para generar embeddings y en estructuras que el resto del pipeline consuma.
"""
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any

from config import JOB_ANALYSIS_PATH, PERFIL_PROFESIONAL_PATH, FIT_HISTORICO_MINIMO


@dataclass
class CandidateProfile:
    habilidades_confirmadas: List[str]
    habilidades_en_adopcion: List[str]
    diferenciadores_unicos: List[str]
    gaps_criticos: List[str]
    nivel: str
    ingles: str
    gaps_a_mencionar_honestamente: Dict[str, str] = field(default_factory=dict)
    objetivo_profesional: Dict[str, Any] = field(default_factory=dict)
    proyectos_por_categoria: Dict[str, List[str]] = field(default_factory=dict)
    diferenciadores_siempre: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(repr=False, default_factory=dict)

    def texto_perfil(self) -> str:
        """Construye un texto en lenguaje natural del perfil, listo para un embedding."""
        partes = [
            f"Candidato nivel {self.nivel}.",
            "Habilidades confirmadas: " + ", ".join(self.habilidades_confirmadas) + ".",
            "Habilidades en adopción: " + ", ".join(self.habilidades_en_adopcion) + ".",
            "Diferenciadores: " + ", ".join(self.diferenciadores_unicos) + ".",
            f"Inglés: {self.ingles}.",
        ]
        if self.objetivo_profesional.get("descripcion"):
            partes.append(f"Objetivo: {self.objetivo_profesional['descripcion']}")
        return " ".join(partes)


def _load_perfil_profesional() -> Dict[str, Any]:
    with open(PERFIL_PROFESIONAL_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_job_analysis_report() -> Dict[str, Any]:
    with open(JOB_ANALYSIS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _extraer_habilidades_confirmadas(stack: Dict[str, Any], umbral: float = 0.55) -> List[str]:
    """Aplana stack_tecnico.* tomando solo ítems con confianza >= umbral,
    tal como lo indica el propio JSON en campos_json_referencia_rapida."""
    nombres = []
    for categoria, items in stack.items():
        if categoria == "en_adopcion_activa":
            continue  # esas van aparte, no son "confirmadas"
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and item.get("confianza", 0) >= umbral:
                nombres.append(item["nombre"])
    return nombres


def _extraer_diferenciadores(stack: Dict[str, Any]) -> List[str]:
    """Junta todo ítem marcado explícitamente como diferenciador=true."""
    diffs = []
    for categoria, items in stack.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and item.get("diferenciador"):
                nota = item.get("nota", "")
                diffs.append(f"{item['nombre']}" + (f" ({nota})" if nota else ""))
    return diffs


def _extraer_gaps_criticos(perfil: Dict[str, Any]) -> List[str]:
    gaps = []
    ingles_nota = perfil.get("idiomas", {}).get("inglés", {}).get("nota")
    if ingles_nota:
        gaps.append(ingles_nota)
    for area in perfil.get("competencias_blandas", {}).get("areas_de_desarrollo", []):
        gaps.append(area)
    for f_academica in perfil.get("formacion_academica", []):
        if not f_academica.get("titulo_disponible", True) and f_academica.get("estado") == "En curso":
            gaps.append(f"Título y cédula de {f_academica['carrera']}: en trámite")
    return gaps


def load_candidate_profile() -> CandidateProfile:
    perfil = _load_perfil_profesional()
    stack = perfil["stack_tecnico"]
    ingles = perfil["idiomas"]["inglés"]
    instrucciones = perfil.get("instrucciones_para_agente", {}).get("al_generar_cv", {})

    return CandidateProfile(
        habilidades_confirmadas=_extraer_habilidades_confirmadas(stack),
        habilidades_en_adopcion=stack.get("en_adopcion_activa", []),
        diferenciadores_unicos=_extraer_diferenciadores(stack),
        gaps_criticos=_extraer_gaps_criticos(perfil),
        nivel=perfil.get("objetivo_profesional", {}).get("nivel", "Junior"),
        ingles=f"{ingles['nivel']} ({ingles['codigo_CEFR']}) — {ingles.get('nota', '')}",
        gaps_a_mencionar_honestamente=instrucciones.get("gaps_a_mencionar_honestamente", {}),
        objetivo_profesional=perfil.get("objetivo_profesional", {}),
        proyectos_por_categoria=instrucciones.get("proyectos_a_incluir_por_categoria", {}),
        diferenciadores_siempre=instrucciones.get("diferenciadores_a_mencionar_siempre", []),
        raw=perfil,
    )


def load_historical_high_fit_jobs(min_fit: int = FIT_HISTORICO_MINIMO) -> List[Dict[str, Any]]:
    """Puestos del catálogo histórico (job_analysis_report.json) con
    fit_score >= min_fit: representan 'lo que sí te ha hecho match' y sirven
    de ancla semántica para nuevas vacantes."""
    data = _load_job_analysis_report()
    catalogo = data["catalogo_puestos"]
    return [p for p in catalogo if p.get("fit_score", 0) >= min_fit]


def texto_ancla_historica(min_fit: int = FIT_HISTORICO_MINIMO) -> str:
    """Texto que representa el patrón de tus puestos de mejor fit histórico."""
    puestos = load_historical_high_fit_jobs(min_fit)
    fragmentos = []
    for p in puestos:
        stack = ", ".join(p.get("stack_requerido", []) + p.get("stack_deseable", []))
        fragmentos.append(f"{p['titulo']} ({p['categoria']}): {stack}")
    return " | ".join(fragmentos)
