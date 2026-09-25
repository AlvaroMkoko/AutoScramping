"""Proveedores de embeddings: Ollama (local, preferido) con fallback a TF-IDF.

La idea: todo lo demás en el pipeline habla con `EmbeddingProvider.embed(texto) -> vector`
sin saber si por debajo hay Ollama o el fallback. Así puedes correr y probar el matcher
aunque `ollama serve` no esté corriendo en este momento.
"""
from __future__ import annotations
import math
from typing import List, Optional, Protocol

import requests

from config import OLLAMA_HOST, OLLAMA_EMBEDDING_MODEL


def cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> List[float]: ...


class OllamaEmbeddingProvider:
    """Usa el endpoint local de Ollama.
    Requiere: `ollama pull nomic-embed-text` y `ollama serve` corriendo."""

    def __init__(self, host: str = OLLAMA_HOST, model: str = OLLAMA_EMBEDDING_MODEL):
        self.host = host
        self.model = model

    def embed(self, text: str) -> List[float]:
        resp = requests.post(
            f"{self.host}/api/embeddings",
            json={"model": self.model, "prompt": text},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]

    def prepare(self, textos: List[str]) -> None:
        """No-op para Ollama: cada texto se embebe de forma independiente."""
        pass


class TfidfEmbeddingProvider:
    """Fallback sin dependencia de red. Útil para probar el pipeline sin Ollama
    corriendo, o como respaldo si Ollama falla. Es menos preciso semánticamente
    (compara palabras, no significado) pero mantiene el pipeline funcional.

    IMPORTANTE: requiere fit_corpus() una sola vez con TODOS los textos que se
    van a comparar entre sí (perfil, ancla histórica, vacante), porque TF-IDF
    necesita un vocabulario compartido para que los vectores sean comparables.
    """

    def __init__(self):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self._vectorizer_cls = TfidfVectorizer
        self._vectorizer = None

    def fit_corpus(self, textos: List[str]):
        self._vectorizer = self._vectorizer_cls().fit(textos)

    def prepare(self, textos: List[str]) -> None:
        """Re-ajusta el vocabulario incluyendo los textos dados (p. ej. perfil +
        ancla histórica + la vacante actual). Debe llamarse antes de cada embed()
        nuevo, o las palabras exclusivas de la vacante quedarán fuera del vocabulario."""
        self.fit_corpus(textos)

    def embed(self, text: str) -> List[float]:
        if self._vectorizer is None:
            raise RuntimeError("Llama fit_corpus() antes de embed() con TfidfEmbeddingProvider.")
        vec = self._vectorizer.transform([text])
        return vec.toarray()[0].tolist()


def get_default_provider(sample_texts: Optional[List[str]] = None) -> EmbeddingProvider:
    """Intenta usar Ollama; si no está disponible, cae a TF-IDF.
    `sample_texts` (perfil + ancla histórica) se usa solo si cae al fallback,
    para poder ajustar el vocabulario de TF-IDF."""
    try:
        provider = OllamaEmbeddingProvider()
        provider.embed("prueba de conexión")
        print(f"[embeddings] Usando Ollama en {provider.host} (modelo: {provider.model})")
        return provider
    except Exception as e:
        print(f"[embeddings] Ollama no disponible ({e}). Usando fallback TF-IDF.")
        print("[embeddings] Para usar embeddings semánticos reales: "
              "`ollama pull nomic-embed-text` y `ollama serve`.")
        provider = TfidfEmbeddingProvider()
        if sample_texts:
            provider.fit_corpus(sample_texts)
        return provider
