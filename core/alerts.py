"""Alertas de deteccion y cobro por Telegram, WhatsApp Cloud y Discord."""

import logging
import threading
import time

import httpx

import config

log = logging.getLogger(__name__)
_lock = threading.Lock()


def _post_json(url, payload, headers=None):
    response = httpx.post(url, json=payload, headers=headers, timeout=15)
    response.raise_for_status()


def _send_chat(method, targets, text):
    """Envia un mensaje o lo registra en consola durante la demo."""
    if not targets:
        return False
    if not config.SEND_FOR_REAL:
        log.info("[%s] destinatarios=%s\n%s", method, targets, text)
        return False

    try:
        if method == "telegram":
            if not config.TELEGRAM_BOT_TOKEN:
                log.error("Falta TELEGRAM_BOT_TOKEN")
                return False
            url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
            for chat_id in targets:
                _post_json(url, {"chat_id": chat_id, "text": text})
            return True

        if method == "whatsapp":
            if not config.WHATSAPP_TOKEN or not config.WHATSAPP_PHONE_NUMBER_ID:
                log.error("Faltan WHATSAPP_TOKEN o WHATSAPP_PHONE_NUMBER_ID")
                return False
            url = (
                f"https://graph.facebook.com/{config.WHATSAPP_API_VERSION}/"
                f"{config.WHATSAPP_PHONE_NUMBER_ID}/messages"
            )
            headers = {"Authorization": f"Bearer {config.WHATSAPP_TOKEN}"}
            for destination in targets:
                _post_json(
                    url,
                    {
                        "messaging_product": "whatsapp",
                        "to": destination,
                        "type": "text",
                        "text": {"body": text},
                    },
                    headers=headers,
                )
            return True

        if method == "discord":
            for webhook in targets:
                _post_json(webhook, {"content": text})
            return True
    except httpx.HTTPError as exc:
        log.error("Error enviando alerta por %s: %s", method, exc)
    return False


def _deliver(text):
    """Usa el primer canal configurado que complete el envio."""
    return (
        _send_chat("telegram", config.telegram_chat_ids(), text)
        or _send_chat("whatsapp", config.whatsapp_destinations(), text)
        or _send_chat("discord", config.discord_webhooks(), text)
    )


class Alerts:
    """Gestiona avisos de entrada y alertas periodicas de cobro."""

    def __init__(self):
        self._low_sent = {}

    def send_high_priority(self, pk, zone, plaque, confidence):
        msg = (
            f"🚗 {zone} — Nueva deteccion\nPlaca: {plaque}\nConfianza: {confidence:.0%}"
        )
        return _deliver(msg)

    def send_low_priority(self, pk, zone, plaque, cost, hours):
        """Avisa del importe MXN respetando la ventana entre alertas."""
        with _lock:
            now = time.time()
            last = self._low_sent.get(pk, 0)
            if now - last < config.LOW_PRIORITY_TTL_MINUTES * 60:
                return False

            msg = (
                f"⚠️ {zone} — Alerta de cobro\n"
                f"Placa: {plaque}\n"
                f"Tiempo estacionado: {hours:.1f} horas\n"
                f"Importe: {config.format_mxn(cost)}\n"
                "Presentate en caja para pagar."
            )
            # Tambien se marca en demo para no repetir el mismo aviso cada ciclo.
            self._low_sent[pk] = now
            return _deliver(msg)

    def reset_low_priority(self, pk):
        with _lock:
            self._low_sent.pop(pk, None)
