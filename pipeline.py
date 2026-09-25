"""Corrida diaria: busca vacantes nuevas en Adzuna y las evalúa con el matcher.

Uso: python pipeline.py

Qué hace:
  1. Busca vacantes para tus keywords configuradas (config.ADZUNA_KEYWORDS).
  2. Descarta las que ya viste en corridas anteriores (data/vacantes_vistas.json).
  3. Evalúa cada vacante NUEVA con JobMatcher (reglas + semántica).
  4. Imprime un resumen agrupado por decisión y guarda un reporte JSON.
  5. Marca todas las vacantes de esta corrida como "vistas" (para no
     reprocesarlas mañana), sin importar si hicieron match o no.
  6. Si hay credenciales de Telegram configuradas: manda el resumen por
     Telegram, y para cada match_fuerte genera su CV personalizado y lo
     adjunta. Si no hay credenciales, este paso se salta con un aviso (el
     resto del pipeline funciona igual).

La postulación sigue siendo 100% manual — el bot avisa y adjunta el CV,
tú decides a cuáles aplicar y lo haces tú mismo.
"""
import json
from datetime import datetime
from pathlib import Path

from job_search import buscar_vacantes, filtrar_nuevas, marcar_como_vistas, CredencialesFaltantesError
from matcher import JobMatcher
from config import BASE_DIR


def _generar_cv_para_item(item: dict) -> Path:
    """Callback que telegram_bot.notificar_reporte usa para generar el CV
    de cada match_fuerte bajo demanda (import perezoso: cv_generator hace
    una llamada de red a Ollama en el import de candidate_profile, mejor
    no pagar ese costo si no hay ningún match_fuerte esta corrida)."""
    from cv_generator import generar_cv
    resultado = generar_cv(
        titulo_vacante=item["titulo"],
        empresa=item["empresa"],
        descripcion_vacante=item.get("descripcion", item["titulo"]),
    )
    return resultado.pdf_path


def main():
    print("Buscando vacantes en Adzuna...")
    try:
        vacantes = buscar_vacantes()
    except CredencialesFaltantesError as e:
        print(f"\n❌ {e}")
        return

    print(f"Encontradas {len(vacantes)} vacantes (antes de filtrar vistas).")
    nuevas = filtrar_nuevas(vacantes)
    print(f"De esas, {len(nuevas)} son nuevas (no vistas en corridas anteriores).\n")

    if not nuevas:
        print("Nada nuevo que evaluar hoy.")
        return

    print("Evaluando con el matcher (esto puede tardar si usas Ollama)...")
    matcher = JobMatcher()

    reporte = {"match_fuerte": [], "revisar": [], "descartar": []}
    for vac in nuevas:
        salario_conocido = vac.salario_max or vac.salario_min
        resultado = matcher.evaluar_vacante(
            titulo=vac.titulo, empresa=vac.empresa, descripcion=vac.descripcion,
            salario_conocido=salario_conocido,
        )
        entrada = resultado.to_dict()
        entrada["url"] = vac.url
        entrada["ubicacion"] = vac.ubicacion
        entrada["fecha_publicacion"] = vac.fecha_publicacion
        entrada["adzuna_id"] = vac.id
        entrada["descripcion"] = vac.descripcion  # necesaria si luego se genera el CV
        reporte[resultado.decision].append(entrada)

    # --- Resumen en consola ---
    print("\n" + "=" * 70)
    for decision, emoji in [("match_fuerte", "🟢"), ("revisar", "🟡"), ("descartar", "⚪")]:
        items = reporte[decision]
        print(f"\n{emoji} {decision.upper()} ({len(items)})")
        for it in items:
            print(f"   [{it['score_final']:.0f}] {it['titulo']} — {it['empresa']} ({it['ubicacion']})")
            print(f"        {it['url']}")

    # --- Guardar reporte ---
    fecha = datetime.now().strftime("%Y-%m-%d_%H%M")
    reporte_path = BASE_DIR / "reportes" / f"reporte_{fecha}.json"
    reporte_path.parent.mkdir(parents=True, exist_ok=True)
    with open(reporte_path, "w", encoding="utf-8") as f:
        json.dump(reporte, f, ensure_ascii=False, indent=2)
    print(f"\nReporte guardado en: {reporte_path}")

    # --- Marcar todas (match o no) como vistas para no repetirlas mañana ---
    marcar_como_vistas(nuevas)
    print(f"{len(nuevas)} vacantes marcadas como vistas.")

    # --- Notificar por Telegram (si hay credenciales configuradas) ---
    try:
        from telegram_bot import notificar_reporte, CredencialesTelegramFaltantesError
        try:
            print("\nEnviando notificación por Telegram...")
            notificar_reporte(reporte, generador_cv_callback=_generar_cv_para_item)
            print("Notificación enviada.")
        except CredencialesTelegramFaltantesError as e:
            print(f"\n(Sin notificar por Telegram: {e})")
    except ImportError:
        pass


if __name__ == "__main__":
    main()
