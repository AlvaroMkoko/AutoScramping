"""Notificaciones por Telegram — la última pieza del pipeline.

Filosofía (semi-manual, como se acordó desde el inicio): el bot te avisa y
te manda el CV ya generado para las vacantes de match_fuerte. NUNCA aplica
por ti — la postulación sigue siendo 100% manual, tú decides con qué
vacantes seguir. Para "revisar" solo manda un resumen (sin generar CV para
30 vacantes de las que probablemente ni apliques a la mitad).

Usa texto plano (sin Markdown) para evitar errores de parseo por caracteres
especiales en títulos/empresas — Telegram auto-detecta y hace clickeables
las URLs de todas formas.
"""
from __future__ import annotations
from pathlib import Path
from typing import List

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_MAX_REVISAR_EN_MENSAJE

TELEGRAM_LIMITE_CARACTERES = 4096


class CredencialesTelegramFaltantesError(Exception):
    pass


def _check_credenciales():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise CredencialesTelegramFaltantesError(
            "Faltan credenciales de Telegram. Sigue las instrucciones en "
            "get_telegram_chat_id.py para crear tu bot y obtener tu chat_id, "
            "y ponlos en data/secrets.json."
        )


def enviar_mensaje(texto: str):
    """Manda un mensaje de texto. Si excede el límite de Telegram, lo parte
    en varios mensajes en vez de fallar."""
    _check_credenciales()
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    for i in range(0, len(texto), TELEGRAM_LIMITE_CARACTERES):
        pedazo = texto[i:i + TELEGRAM_LIMITE_CARACTERES]
        resp = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": pedazo}, timeout=15)
        resp.raise_for_status()


def enviar_documento(ruta_archivo: Path, caption: str = ""):
    """Manda un archivo (ej. el PDF del CV) con un texto opcional."""
    _check_credenciales()
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    with open(ruta_archivo, "rb") as f:
        files = {"document": (ruta_archivo.name, f)}
        data = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption[:1024]}  # Telegram limita el caption
        resp = requests.post(url, data=data, files=files, timeout=60)
    resp.raise_for_status()


def _formatear_item(item: dict) -> str:
    return (
        f"{item['titulo']}\n"
        f"{item['empresa']} — {item.get('ubicacion', '')}\n"
        f"Score: {item['score_final']:.0f}\n"
        f"{item['url']}"
    )


def construir_mensaje_resumen(reporte: dict) -> str:
    """Mensaje de texto con el resumen de la corrida (sin generar CVs).
    Se manda SIEMPRE, incluso si no hay match_fuerte, para que sepas que
    el bot sí corrió."""
    n_fuerte = len(reporte["match_fuerte"])
    n_revisar = len(reporte["revisar"])
    n_descartar = len(reporte["descartar"])

    lineas = [
        f"🔎 Corrida completada: {n_fuerte} match fuerte, {n_revisar} para revisar, "
        f"{n_descartar} descartadas.",
    ]

    if n_fuerte:
        lineas.append("\n🟢 MATCH FUERTE (CV generado y adjunto abajo):")
        for item in reporte["match_fuerte"]:
            lineas.append("\n" + _formatear_item(item))

    if n_revisar:
        lineas.append(f"\n🟡 REVISAR (top {min(n_revisar, TELEGRAM_MAX_REVISAR_EN_MENSAJE)} de {n_revisar}):")
        for item in reporte["revisar"][:TELEGRAM_MAX_REVISAR_EN_MENSAJE]:
            lineas.append("\n" + _formatear_item(item))
        restantes = n_revisar - TELEGRAM_MAX_REVISAR_EN_MENSAJE
        if restantes > 0:
            lineas.append(f"\n(+{restantes} más — revisa el reporte JSON completo)")

    return "\n".join(lineas)


def notificar_reporte(reporte: dict, generador_cv_callback=None):
    """Manda el resumen por Telegram. Si se pasa `generador_cv_callback`
    (función que recibe un item de match_fuerte y regresa la ruta del PDF
    generado), también genera y adjunta el CV de cada match_fuerte.

    Los errores al generar un CV individual NO detienen la notificación de
    los demás — se avisa por texto que ese CV falló y hay que revisarlo
    manualmente.
    """
    mensaje = construir_mensaje_resumen(reporte)
    enviar_mensaje(mensaje)

    if generador_cv_callback is None:
        return

    for item in reporte["match_fuerte"]:
        try:
            pdf_path = generador_cv_callback(item)
            enviar_documento(pdf_path, caption=f"{item['titulo']} — {item['empresa']}")
        except Exception as e:
            enviar_mensaje(
                f"⚠️ No pude generar/enviar el CV para \"{item['titulo']}\" "
                f"({item['empresa']}): {e}\nGenéralo manualmente si te interesa esta vacante."
            )
