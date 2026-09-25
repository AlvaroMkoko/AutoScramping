"""Demo del módulo de matching con vacantes de ejemplo (simulan lo que traería
el futuro módulo de scraping). Corre con: python demo.py
"""
import json
from matcher import JobMatcher

VACANTES_EJEMPLO = [
    {
        "titulo": "Junior AI Engineer - RAG & LLMs",
        "empresa": "Startup IA Ejemplo",
        "descripcion": """
            Buscamos ingeniero junior en inteligencia artificial para unirse a
            nuestro equipo de R&D. Requisitos: Python, experiencia con LLMs y RAG,
            Git, Docker. Deseable: LangChain, embeddings, bases vectoriales.
            Aceptamos recién egresados o pasantes avanzados. Sueldo 28,000 - 35,000
            MXN mensuales. Modalidad híbrida, inglés intermedio.
        """,
    },
    {
        "titulo": "Frontend Developer React Senior",
        "empresa": "Agencia Web Ejemplo",
        "descripcion": """
            Se busca desarrollador Frontend Senior con 5+ años de experiencia en
            React, Vue y CSS avanzado. Título profesional y cédula obligatorios.
            Inglés C1 fluido indispensable para llamadas diarias con clientes en EU.
        """,
    },
    {
        "titulo": "Auxiliar Administrativo",
        "empresa": "Empresa Ejemplo",
        "descripcion": """
            Puesto de auxiliar administrativo, manejo de Excel y atención a
            clientes. Sueldo 12,000 MXN mensuales. No se requiere experiencia.
        """,
    },
    {
        "titulo": "AI/ML Engineer - MLOps",
        "empresa": "Scaleup Ejemplo",
        "descripcion": """
            Ingeniero de ML para robustecer nuestro pipeline de producción:
            MLflow, Docker, FastAPI, monitoreo de drift. Python avanzado
            indispensable. 1-2 años de experiencia o proyectos equivalentes.
            Sueldo hasta 32,000 MXN. Inglés B2 para documentación técnica.
        """,
    },
]


def main():
    matcher = JobMatcher()
    print("\n" + "=" * 70)
    resultados = []
    for vac in VACANTES_EJEMPLO:
        r = matcher.evaluar_vacante(vac["titulo"], vac["empresa"], vac["descripcion"])
        resultados.append(r)
        print(f"\n📋 {r.titulo}  —  {r.empresa}")
        print(f"   Decisión: {r.decision.upper()}  |  Score final: {r.score_final}")
        print(f"   Semántico (perfil): {r.score_semantico_perfil}  |  "
              f"Semántico (histórico): {r.score_semantico_historico}  |  "
              f"Reglas: {r.score_reglas}")
        if r.razones:
            print("   Notas: " + " / ".join(r.razones))
    print("\n" + "=" * 70)

    with open("resultados_demo.json", "w", encoding="utf-8") as f:
        json.dump([r.to_dict() for r in resultados], f, ensure_ascii=False, indent=2)
    print("\nResultados guardados en resultados_demo.json")


if __name__ == "__main__":
    main()
