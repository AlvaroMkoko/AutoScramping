"""Banco de contenido VERÍDICO para la generación de CVs.

Todo lo que vive aquí son hechos reales, sacados literalmente de
cv_alvaro.tex y de los CVs que ya generaste antes. El LLM (Ollama) NUNCA
escribe estos bullets desde cero — solo elige, reordena y prioriza cuáles
usar según la vacante. Esto convierte el riesgo de "alucinación" en un
problema de selección, no de generación libre.

Si agregas un proyecto o logro nuevo a tu carrera, edítalo aquí — no le
pidas al LLM que lo invente en el prompt.
"""

SKILLS_CATALOG = {
    "Lenguajes": ["Python", "JavaScript", "Java", "C", "Rust"],
    "IA y Deep Learning": ["Transformer (desde cero)", "PyTorch", "scikit-learn",
                           "tiktoken", "HuggingFace datasets"],
    "Interpretabilidad": ["VisPy + OpenGL", "Proyección R$^n\\!\\to\\!$R$^3$ en GPU", "PCA",
                          "Visualización de atención en tiempo real"],
    "MLOps": ["MLflow", "DVC", "Docker", "FastAPI", "Evidently", "TensorBoard"],
    "Cloud e infra": ["Azure (VMs Linux · SSH/PuTTY)", "Render", "Netlify", "Linux (Ubuntu)"],
    "Ingeniería SW": ["MVVM (PySide6/QML)", "pytest + pytest-qt", "black", "ruff",
                      "Git / GitHub", "Scrum", "Kanban"],
    "LLMs y GenAI": ["APIs Claude y ChatGPT en el flujo diario", "Prompt engineering",
                     "LangChain (en adopción)"],
    "Backend y APIs": ["FastAPI", "Java + Maven", "APIs REST", "microservicios", "Pydantic"],
    "Front-end": ["HTML", "CSS", "JavaScript", "Angular", "TypeScript (en adopción)"],
    "Bases de datos": ["SQL", "PostgreSQL / SQLite (en adopción)", "gestión de datasets estructurados"],
    "Automatización": ["Pipelines de datos (DVC)", "procesamiento por lotes",
                       "scripts de Python para flujos repetitivos", "Docker"],
    "Análisis y procesos": ["Levantamiento de requerimientos", "mapeo de procesos",
                            "identificación de oportunidades de mejora", "KPIs y métricas"],
    "Documentación": ["README técnicos detallados", "reportes de métricas",
                      "manuales de uso", "comparativas de resultados"],
}

# Cada proyecto: id estable, título canónico, línea de tecnologías, y el banco
# de bullets ya redactados (el LLM solo elige un subconjunto y los reordena).
PROJECTS = [
    {
        "id": "transformer_lab",
        "titulo": "Herramienta de Visualización y Exploración Interactiva de Transformer",
        "tech_line": "PyTorch · VisPy · PySide6 · QML · MVVM",
        "peso_portfolio": "muy alto",
        "bullets": [
            "Arquitectura Transformer completamente configurable desde cero: d\\_model, "
            "cabezas, capas, activaciones (relu/gelu/swish) y máscara causal, con "
            "estimación de parámetros y memoria en tiempo real.",

            "Interpretabilidad GPU: proyección R$^n\\!\\to\\!$R$^3$ de embeddings durante "
            "el entrenamiento con PCA o dimensiones por head de atención, usando VisPy "
            "+ OpenGL — la fracción de varianza conservada se muestra en pantalla.",

            "Pipeline de datos propio: ingesta de JSONL, JSON, CSV, TXT y PDF en un "
            "corpus unificado, con análisis de tokens, vocabulario y categorías por dataset.",

            "Arquitectura MVVM (PyTorch / QML / PySide6), pytest-qt, CLI y formato "
            "portable .tvismodel con SHA-256; inferencia con temperatura/top-k/top-p "
            "y comparación de 2 arquitecturas simultáneas.",
        ],
    },
    {
        "id": "chess_ml",
        "titulo": "Chess-ML — Pipeline Completo de ML en Producción",
        "tech_line": "PyTorch · MLflow · DVC · FastAPI · Docker · Evidently",
        "peso_portfolio": "muy alto",
        "bullets": [
            "Red neuronal PyTorch estadísticamente equivalente a Random Forest "
            "(McNemar p\\,=\\,0.887); regularización con Dropout, Weight Decay y "
            "BatchNorm diagnosticada con TensorBoard.",

            "Grid search de 16 configuraciones en MLflow; análisis factorial $2^4$ "
            "con semillas; accuracy 66.22\\% con la mejor configuración del grid search.",

            "Microservicio REST con FastAPI contenerizado en Docker; validación de "
            "inputs (Pydantic), logging automático de requests, documentación "
            "interactiva /docs.",

            "Pipeline reproducible con DVC y monitoreo de drift en producción con Evidently.",
        ],
    },
    {
        "id": "voice_classification",
        "titulo": "Clasificación de Voz + Full-Stack",
        "tech_line": "DSP · ML · APIs · Hackathon",
        "peso_portfolio": "alto",
        "bullets": [
            "FFT Cooley-Tukey implementada desde cero; 161 features acústicas (MFCC, "
            "formantes, descriptores espectrales).",

            "Random Forest, SVM y MLP con validación cruzada 5-fold; 3 tareas de "
            "clasificación (género, tipo de sonido, vocal); inferencia en tiempo real "
            "desde micrófono.",

            "Angular + Java + API OpenPayments; despliegue en plataforma cloud; "
            "1er lugar hackathon ESCOM 2025 (48h).",
        ],
    },
    {
        "id": "rust_teoria_computacion",
        "titulo": "Proyectos en Rust — Teoría de la Computación",
        "tech_line": "Rust · plotters · num-bigint · rand",
        "peso_portfolio": "medio (diferenciador)",
        "bullets": [
            "Generador del universo $\\Sigma^*$ con enteros de precisión arbitraria "
            "(num-bigint); gráficas de distribución lineal y logarítmica con plotters; "
            "diseño modular con múltiples crates.",
        ],
    },
]

LOGROS = [
    {
        "id": "talent_land_2026",
        "texto": "\\textbf{Finalista — Genius Arena Hackathon, Talent Land México 2026}: "
                 "Track Grupo Salinas / Banco Azteca; Expo Santa Fe, CDMX.",
    },
    {
        "id": "interledger_2025",
        "texto": "\\textbf{1er Lugar — Interledger Student Hackathon ESCOM 2025}: "
                 "Solución web con integración de API de pagos internacionales.",
    },
]

# perfil_profesional.json usa sus propios ids abreviados (P1-Transformer,
# P2-ChessML-API, etc.) en instrucciones_para_agente.proyectos_a_incluir_por_categoria.
# Este mapa traduce esos ids a los ids reales de PROJECTS de arriba, solo para
# poder construir una PISTA legible en el prompt (no se usa para validar).
PROJECT_ID_ALIASES = {
    "P1-Transformer": "transformer_lab",
    "P2-ChessML": "chess_ml",
    "P2-ChessML-API": "chess_ml",
    "P2-ChessML-Evaluacion": "chess_ml",
    "P2-ChessML-Docker": "chess_ml",
    "P2-ChessML-MLOps": "chess_ml",
    "P2-ChessML-factorial": "chess_ml",
    "P3-Voz": "voice_classification",
    "P3-Voz-batch": "voice_classification",
    "P5-FullStack": "voice_classification",  # el bullet full-stack vive dentro de este proyecto
    # Sin equivalente en PROJECTS (no son "proyectos" sino skills/infra/formación):
    "Azure-VMs": None,
    "CECyT-background": None,
}

# Datos fijos que NO se personalizan por vacante (contacto, educación, certificaciones)
DATOS_FIJOS = {
    "nombre": "ÁLVARO ALEXANDER VELÁZQUEZ MATUS",
    "telefono": "(55) 1071-3057",
    "email": "velazquez.matus.alvaro@gmail.com",
    "github": "github.com/AlvaroMkoko",
    "educacion": [
        ("Escuela Superior de Cómputo (IPN)", "2023 – 2026",
         "Ingeniería en Inteligencia Artificial — 8vo semestre"),
        ("Centro de Estudios Científicos y Tecnológicos No. 9 (INP)", "2019 – 2022",
         "Técnico en Sistemas Digitales — Finalizado"),
    ],
    "certificaciones": "Ciberseguridad Básica — CISCO — ABR/2024 $\\cdot$ "
                        "Certificado 1er Lugar — Interledger Student Hackathon ESCOM 2025",
    "idiomas": "Español (nativo) $\\cdot$ Inglés (Intermedio técnico)",
}
