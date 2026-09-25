"""Módulo principal de matching: combina similitud semántica (embeddings) con
el motor de reglas duras para producir un veredicto por vacante.

Uso típico (una vez que el módulo de scraping traiga vacantes):

    matcher = JobMatcher()
    resultado = matcher.evaluar_vacante(
        titulo="Junior AI Engineer",
        empresa="Empresa X",
        descripcion="texto completo de la vacante...",
    )
    if resultado.decision == "match_fuerte":
        # -> disparar generación de CV + notificación Telegram
        ...
"""
from dataclasses import dataclass, asdict
from typing import List, Optional

from config import (
    UMBRAL_FIT_ALTO, UMBRAL_REVISION_MANUAL,
    PESO_SEMANTICO_PERFIL, PESO_SEMANTICO_HISTORICO, PESO_REGLAS,
    FIT_HISTORICO_MINIMO,
)
from candidate_profile import load_candidate_profile, texto_ancla_historica
from embeddings import get_default_provider, cosine_similarity
from rules import extraer_vacante, evaluar_reglas


@dataclass
class ResultadoMatch:
    titulo: str
    empresa: str
    decision: str  # "match_fuerte" | "revisar" | "descartar"
    score_final: float
    score_semantico_perfil: float
    score_semantico_historico: float
    score_reglas: float
    razones: List[str]

    def to_dict(self):
        return asdict(self)


class JobMatcher:
    def __init__(self):
        self.perfil = load_candidate_profile()
        self.texto_perfil = self.perfil.texto_perfil()
        self.texto_ancla = texto_ancla_historica(min_fit=FIT_HISTORICO_MINIMO)
        # Se resuelve una sola vez: intenta Ollama, cae a TF-IDF si no responde.
        self.provider = get_default_provider(sample_texts=[self.texto_perfil, self.texto_ancla])

    def evaluar_vacante(self, titulo: str, empresa: str, descripcion: str,
                       salario_conocido: Optional[float] = None) -> ResultadoMatch:
        texto_vacante = f"{titulo}. {descripcion}"

        # 1. Señales duras primero (son gratis computacionalmente y descartan rápido)
        extraida = extraer_vacante(titulo, descripcion, salario_conocido=salario_conocido)
        veredicto = evaluar_reglas(extraida)

        if veredicto.descartar:
            return ResultadoMatch(
                titulo=titulo, empresa=empresa, decision="descartar",
                score_final=0.0, score_semantico_perfil=0.0,
                score_semantico_historico=0.0, score_reglas=0.0,
                razones=veredicto.razones_descarte,
            )

        # 2. Señales semánticas (solo si no fue descartada por reglas)
        self.provider.prepare([self.texto_perfil, self.texto_ancla, texto_vacante])
        emb_perfil = self.provider.embed(self.texto_perfil)
        emb_ancla = self.provider.embed(self.texto_ancla)
        emb_vacante = self.provider.embed(texto_vacante)

        sim_perfil = cosine_similarity(emb_vacante, emb_perfil) * 100
        sim_historico = cosine_similarity(emb_vacante, emb_ancla) * 100

        # 3. Score combinado
        score_final = (
            PESO_SEMANTICO_PERFIL * sim_perfil
            + PESO_SEMANTICO_HISTORICO * sim_historico
            + PESO_REGLAS * veredicto.score_reglas
        )

        if score_final >= UMBRAL_FIT_ALTO:
            decision = "match_fuerte"
        elif score_final >= UMBRAL_REVISION_MANUAL or veredicto.revision_manual:
            decision = "revisar"
        else:
            decision = "descartar"

        razones = list(veredicto.razones_revision)
        if extraida.stack_detectado:
            razones.append("Stack detectado: " + ", ".join(extraida.stack_detectado))

        return ResultadoMatch(
            titulo=titulo, empresa=empresa, decision=decision,
            score_final=round(score_final, 1),
            score_semantico_perfil=round(sim_perfil, 1),
            score_semantico_historico=round(sim_historico, 1),
            score_reglas=round(veredicto.score_reglas, 1),
            razones=razones,
        )
