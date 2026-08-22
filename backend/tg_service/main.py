import logging
import os

import requests

logger = logging.getLogger(__name__)

# .env уже загружен в окружение процесса на старте Django (config/settings.py
# вызывает load_dotenv до импорта любых view/этого модуля) — здесь просто
# читаем os.environ.
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def _format_message(machine, created: bool, changes: dict) -> str:
    role = "Учительский" if machine.is_teacher else "Ученический"
    cabinet = machine.cabinet or "?"

    lines = [
        f"{'🆕 Новый компьютер' if created else '♻️ Изменение конфигурации'}: {machine.pc}",
        f"Кабинет {cabinet} · {role}",
    ]
    if changes:
        lines.append("")
        for field, diff in changes.items():
            lines.append(f"{field}: {diff['old']!r} → {diff['new']!r}")

    return "\n".join(lines)


def send_specs_to_channel(machine, created: bool, changes: dict) -> None:
    """Отправляет уведомление в телеграм-группу о новом ПК или изменении
    его характеристик. Вызывается из InventoryView только когда есть что
    сообщить (created=True или changes непустой) — обычные heartbeat без
    изменений группу не спамят."""
    if not TELEGRAM_BOT_TOKEN or not CHANNEL_ID:
        logger.warning(
            "TELEGRAM_BOT_TOKEN/CHANNEL_ID не заданы — уведомление в Telegram пропущено"
        )
        return

    text = _format_message(machine, created, changes)
    try:
        resp = requests.post(
            API_URL.format(token=TELEGRAM_BOT_TOKEN),
            json={"chat_id": CHANNEL_ID, "text": text},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException:
        logger.exception("Не удалось отправить уведомление в Telegram")
