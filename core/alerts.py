"""Envío de alertas a Telegram / WhatsApp / Discord con lógica de cobro."""

import json
import logging
import threading
import time

import config

log = logging.getLogger(__name__)

_lock = threading.Lock()


def _send_chat(method, targets, payload):
    """Envía a una plataforma. `targets` es una lista; `payload` depende de method.

    En la demo (SEND_FOR_REAL=False) se imprime/registra, sin efecto real.
    """
    if not targets:
        return False
    if not config.SEND_FOR_REAL:
        log.info("[%s] targets=%s", method, targets)
        return False

    if method == "telegram":
        try:
            from telegram import Bot

            bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
            for cid in targets:
                bot.send_message(cid, payload, parse_mode="Markdown")
            return True
        except Exception as e:
            log.error("Telegram error: %s", e)
            return False
    if method == "whatsapp":
        log.info("WhatsApp -> %s: %s", targets, payload["text"])
        return True
    if method == "discord":
        import httpx

        for hook in targets:
            try:
                httpx.post(hook, json={"content": payload["text"]}, timeout=10)
            except Exception as e:
                log.error("Discord error: %s", e)
        return True
    return False


class Alerts:
    """Gestiona el envío de alertas de alta (nueva detección) y baja (cobro)."""

    def __init__(self):
        self._low_sent = {}  # pk -> timestamp Unix (última alerta de cobro enviada)

    def send_high_priority(self, pk, zone, plaque, confidence):
        """Un coche se detetce en una zona nueva; avisar (alta prioridad)."""
        msg = (
            f":car: *{zone} — Nueva detección* — placa `{plaque}` "
            f"(confianza {confidence:.0%}). "
            f"¡Sigue estacionado! :dollar:"
        )
        return _send_chat(
            "telegram",
            config.telegram_chat_ids(),
            msg,
        ) or _send_chat(
            "whatsapp",
            config.whatsapp_destinations(),
            {"text": msg},
        ) or _send_chat(
            "discord",
            config.discord_webhooks(),
            {"text": msg},
        )

    def send_low_priority(self, pk, zone, plaque, cost, hours):
        """Alerta de cobro: el coche lleva más de GRACE_MINUTES; le avisamos.

        Devuelve True solo si (y cuando) la alerta es **necesaria**: si ya enviamos
        una reciente y la ventana LOW_PRIORITY_TTL_MINUTES aún no pasó, no se repite.
        """
        with _lock:
            last = self._low_sent.get(pk)
            if last is None:
                last = 0
            elapsed = time.time() - last
            if elapsed < config.LOW_PRIORITY_TTL_MINUTES * 60:
                return False  # ya avisamos hace poco, no es necesario ahora

            hours_str = f"{hours:.1f}"
            unit = "hora" if hours == 1 else "horas"
            msg = (
                f":warning: *{zone} — Alerta de cobro* — placa `{plaque}` "
                f"lleva **{hours_str} {unit}**; tiempo excedido: **${cost}**. "
                "Debe pagar. :moneybag:"
            )

            # Marca de cuándo enviamos esta alerta (sin envió real, es un no-op).
            self._low_sent[pk] = time.time()
            return (
                _send_chat("telegram", config.telegram_chat_ids(), msg, parse_mode="Markdown")
                or _send_chat("whatsapp", config.whatsapp_destinations(), {"text": msg})
                or _send_chat("discord", config.discord_webhooks(), {"text": msg})
            )

    def reset_low_priority(self, pk):
        """El coche se detectó de nuevo / sigue vigente: resetea el contador de alerta."""
        with _lock:
            self._low_sent[pk] = 0
