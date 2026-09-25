"""Búsqueda de vacantes vía la API de Adzuna (México).

Por qué Adzuna y no scraping: LinkedIn/Indeed prohíben el scraping automatizado
en sus ToS y tienen anti-bot agresivo (riesgo real de que te bloqueen la
cuenta). Adzuna es una API pública, legítima, con cobertura real de México
(adzuna.com.mx) y un tier gratuito razonable para uso personal.

Límite del tier gratuito: ~1,000 llamadas/mes (~33/día). Este módulo hace
UNA llamada por keyword (no por página), así que con la lista default de 5
keywords usas ~5 llamadas por corrida — puedes correrlo varias veces al día
sin preocuparte, pero no lo pongas en un loop.
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass, asdict
from typing import List, Optional, Set

import requests

from config import (
    ADZUNA_APP_ID, ADZUNA_APP_KEY, ADZUNA_COUNTRY, ADZUNA_BASE_URL,
    ADZUNA_RESULTS_PER_PAGE, ADZUNA_MAX_PAGINAS_POR_KEYWORD,
    ADZUNA_KEYWORDS, ADZUNA_WHERE, SEEN_JOBS_PATH,
)


class CredencialesFaltantesError(Exception):
    """Se lanza si no hay app_id/app_key configurados."""
    pass


@dataclass
class VacanteAdzuna:
    id: str
    titulo: str
    empresa: str
    ubicacion: str
    descripcion: str  # NOTA: Adzuna trunca las descripciones, no son el texto completo
    salario_min: Optional[float]
    salario_max: Optional[float]
    salario_es_estimado: bool
    url: str
    fecha_publicacion: str
    keyword_origen: str


def _check_credenciales():
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        raise CredencialesFaltantesError(
            "Faltan credenciales de Adzuna. Regístrate gratis en "
            "https://developer.adzuna.com/signup y pon tu app_id/app_key en "
            "data/secrets.json (copia data/secrets.example.json) o en las "
            "variables de entorno ADZUNA_APP_ID / ADZUNA_APP_KEY."
        )


def _normalizar(raw: dict, keyword_origen: str) -> VacanteAdzuna:
    return VacanteAdzuna(
        id=str(raw.get("id", "")),
        titulo=raw.get("title", "").strip(),
        empresa=(raw.get("company") or {}).get("display_name", "No especificada"),
        ubicacion=(raw.get("location") or {}).get("display_name", "No especificada"),
        descripcion=raw.get("description", "").strip(),
        salario_min=raw.get("salary_min"),
        salario_max=raw.get("salary_max"),
        salario_es_estimado=bool(raw.get("salary_is_predicted", "0") not in ("0", 0, False)),
        url=raw.get("redirect_url", ""),
        fecha_publicacion=raw.get("created", ""),
        keyword_origen=keyword_origen,
    )


def _buscar_una_keyword(keyword: str, where: str, pagina: int) -> List[dict]:
    url = f"{ADZUNA_BASE_URL}/{ADZUNA_COUNTRY}/search/{pagina}"
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "results_per_page": ADZUNA_RESULTS_PER_PAGE,
        "what": keyword,
        "content-type": "application/json",
    }
    if where:
        params["where"] = where
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("results", [])


def _clave_duplicado(vac: VacanteAdzuna) -> str:
    """Normaliza título+empresa+ubicación para detectar reposts EXACTOS del
    mismo puesto con distinto id de Adzuna. Incluir la ubicación es
    deliberado: la misma empresa puede publicar el mismo título de puesto
    para sedes distintas (ej. Corning en Reynosa vs. Corning en CDMX) — esas
    son oportunidades reales y NO deben colapsarse en una sola."""
    def normalizar(s: str) -> str:
        s = s.lower()
        s = re.sub(r"[^\w\s]", " ", s)  # quita puntuación (-, /, etc.)
        s = re.sub(r"\s+", " ", s).strip()
        return s
    return f"{normalizar(vac.titulo)}::{normalizar(vac.empresa)}::{normalizar(vac.ubicacion)}"


def buscar_vacantes(keywords: Optional[List[str]] = None,
                    where: Optional[str] = None,
                    max_paginas: Optional[int] = None) -> List[VacanteAdzuna]:
    """Busca vacantes para cada keyword y deduplica por id de Adzuna Y por
    título+empresa normalizados (para colapsar reposts del mismo puesto).

    Cada keyword cuenta como 1 llamada a la API por página (default 1 página).
    """
    _check_credenciales()
    keywords = keywords if keywords is not None else ADZUNA_KEYWORDS
    where = where if where is not None else ADZUNA_WHERE
    max_paginas = max_paginas if max_paginas is not None else ADZUNA_MAX_PAGINAS_POR_KEYWORD

    ids_vistos: Set[str] = set()
    claves_vistas: Set[str] = set()
    resultados: List[VacanteAdzuna] = []

    for keyword in keywords:
        for pagina in range(1, max_paginas + 1):
            crudos = _buscar_una_keyword(keyword, where, pagina)
            if not crudos:
                break
            for raw in crudos:
                vac = _normalizar(raw, keyword)
                if not vac.id or vac.id in ids_vistos:
                    continue
                clave = _clave_duplicado(vac)
                if clave in claves_vistas:
                    continue
                ids_vistos.add(vac.id)
                claves_vistas.add(clave)
                resultados.append(vac)

    return resultados


# ─────────────────────────────────────────────────────────────────────────────
# Tracking de vacantes ya vistas (para no re-procesar/notificar lo mismo cada día)
# ─────────────────────────────────────────────────────────────────────────────

def cargar_vistas() -> Set[str]:
    if not SEEN_JOBS_PATH.exists():
        return set()
    with open(SEEN_JOBS_PATH, "r", encoding="utf-8") as f:
        return set(json.load(f))


def guardar_vistas(ids: Set[str]):
    SEEN_JOBS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SEEN_JOBS_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(ids), f, ensure_ascii=False, indent=2)


def filtrar_nuevas(vacantes: List[VacanteAdzuna]) -> List[VacanteAdzuna]:
    """Regresa solo las vacantes cuyo id no se ha visto en corridas anteriores.
    NO marca nada como visto — eso se hace explícitamente con marcar_como_vistas()
    una vez que ya procesaste el lote (así una corrida fallida no pierde vacantes)."""
    vistas = cargar_vistas()
    return [v for v in vacantes if v.id not in vistas]


def marcar_como_vistas(vacantes: List[VacanteAdzuna]):
    vistas = cargar_vistas()
    vistas.update(v.id for v in vacantes)
    guardar_vistas(vistas)
