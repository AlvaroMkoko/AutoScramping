"""Prueba end-to-end del generador de CV. Requiere Ollama corriendo con:
  - nomic-embed-text (ya lo tienes, del módulo de matching)
  - un modelo de chat (ver OLLAMA_CHAT_MODEL en config.py — default: llama3.1)
    Si no lo tienes: `ollama pull llama3.1`

Corre con: python demo_generar_cv.py
"""
from cv_generator import generar_cv

VACANTE_EJEMPLO = {
    "titulo_vacante": "Junior AI Engineer - RAG & LLMs",
    "empresa": "Startup IA Ejemplo",
    "descripcion_vacante": """
        Buscamos ingeniero junior en inteligencia artificial para unirse a
        nuestro equipo de R&D. Requisitos: Python, experiencia con LLMs y RAG,
        Git, Docker. Deseable: LangChain, embeddings, bases vectoriales.
        Aceptamos recién egresados o pasantes avanzados. Modalidad híbrida.
    """,
    "fit_razon": "Mentalidad end-to-end y Transformer desde cero son diferenciadores clave.",
}


def main():
    print("Generando CV personalizado (esto llama a Ollama, puede tardar unos segundos)...")
    resultado = generar_cv(**VACANTE_EJEMPLO)

    print(f"\nPDF generado en: {resultado.pdf_path}")
    print(f"Fuente .tex en:  {resultado.tex_path}")

    if resultado.advertencias:
        print("\n⚠️  Advertencias durante la generación (revisar):")
        for a in resultado.advertencias:
            print(f"  - {a}")
    else:
        print("\nSin advertencias — el LLM se mantuvo dentro del banco de contenido verídico.")

    print("\nIMPORTANTE: revisa manualmente el PDF antes de postular. El título y el "
          "resumen son generados por el LLM y, aunque están acotados a tu perfil real, "
          "tú tienes la última palabra sobre cómo se lee.")


if __name__ == "__main__":
    main()
