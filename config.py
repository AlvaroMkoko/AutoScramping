"""Configuración central del pipeline de automatización de búsqueda de empleo."""
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
JOB_ANALYSIS_PATH = DATA_DIR / "job_analysis_report.json"
PERFIL_PROFESIONAL_PATH = DATA_DIR / "perfil_profesional.json"
SEEN_JOBS_PATH = DATA_DIR / "vacantes_vistas.json"
SECRETS_PATH = DATA_DIR / "secrets.json"  # NUNCA subir este archivo a git


def _load_secrets() -> dict:
    if SECRETS_PATH.exists():
        with open(SECRETS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


_secrets = _load_secrets()

# --- Adzuna (búsqueda de vacantes) ---
# Regístrate gratis en https://developer.adzuna.com/signup para obtener
# app_id y app_key. Ponlos en data/secrets.json (ver data/secrets.example.json)
# o como variables de entorno ADZUNA_APP_ID / ADZUNA_APP_KEY.
import os
ADZUNA_APP_ID = os.environ.get("ADZUNA_APP_ID") or _secrets.get("adzuna_app_id", "")
ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY") or _secrets.get("adzuna_app_key", "")
ADZUNA_COUNTRY = "mx"
ADZUNA_BASE_URL = "https://api.adzuna.com/v1/api/jobs"
ADZUNA_RESULTS_PER_PAGE = 20
ADZUNA_MAX_PAGINAS_POR_KEYWORD = 1  # sube esto con cuidado: la cuota gratis es ~33 llamadas/día

# Términos de búsqueda por defecto. Ajusta según lo que quieras cubrir.
ADZUNA_KEYWORDS = [
    "ingeniero inteligencia artificial",
    "AI engineer",
    "machine learning engineer",
    "GenAI",
    "MLOps",
]
ADZUNA_WHERE = ""  # vacío = todo México; puedes poner "Ciudad de México" para acotar

# --- Telegram (notificaciones semi-manuales) ---
# 1. Habla con @BotFather en Telegram, manda /newbot, sigue las instrucciones.
#    Te da un token como "123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx".
# 2. Pon ese token en data/secrets.json (telegram_bot_token) o en la variable
#    de entorno TELEGRAM_BOT_TOKEN.
# 3. Corre `python get_telegram_chat_id.py` para obtener tu chat_id (ver ese
#    archivo para instrucciones exactas) y ponlo también en secrets.json.
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or _secrets.get("telegram_bot_token", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID") or _secrets.get("telegram_chat_id", "")
TELEGRAM_MAX_REVISAR_EN_MENSAJE = 15  # cuántos ítems de "revisar" listar antes de truncar

# --- Ollama (embeddings locales) ---
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_EMBEDDING_MODEL = "nomic-embed-text"  # requiere: ollama pull nomic-embed-text

# --- Ollama (generación de texto para el CV) ---
# Necesitas un modelo de CHAT además del de embeddings. Con GPU de 16GB VRAM
# (ej. RTX 5070 Ti), qwen3:14b es un buen punto medio: denso, ~9-11GB a Q4,
# fuerte instruction-following multilingüe (mejor en español que llama3.1:8b).
# `ollama pull qwen3:14b` y ajusta este valor si usas otro.
# NOTA: qwen3 usa "modo de pensamiento" por default — cv_generator.py ya
# manda "think": False en la llamada para desactivarlo (si no, antepone un
# bloque <think>...</think> que rompe el parseo de JSON).
OLLAMA_CHAT_MODEL = "qwen3:14b"

# --- Generación de CV ---
CV_TEMPLATE_PATH = BASE_DIR / "templates" / "cv_template.tex.jinja"
CV_OUTPUT_DIR = BASE_DIR / "cv_generados"
MAX_PROYECTOS_EN_CV = 3  # cuántos proyectos incluir (de los 4 disponibles en el banco)

# --- Umbrales de decisión (ajustables según cuántas notificaciones quieras recibir) ---
UMBRAL_FIT_ALTO = 75         # score >= esto -> "match_fuerte" (dispara generación de CV)
UMBRAL_REVISION_MANUAL = 55  # entre este y el de arriba -> "revisar" (se notifica, no se genera CV aún)
# por debajo de UMBRAL_REVISION_MANUAL -> "descartar" (no se notifica)

# --- Pesos del score final (deben sumar 1.0) ---
PESO_SEMANTICO_PERFIL = 0.35     # similitud contra tus habilidades/diferenciadores
PESO_SEMANTICO_HISTORICO = 0.25  # similitud contra los puestos donde tuviste fit_score 8-9
PESO_REGLAS = 0.40                # señales duras: salario, título, idioma, experiencia, stack

FIT_HISTORICO_MINIMO = 8  # qué tan alto debe ser fit_score para usarse como "ancla" de referencia
