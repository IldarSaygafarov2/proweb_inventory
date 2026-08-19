"""
agent.py — агент инвентаризации для Windows.

Что делает при каждом запуске:
  1. Собирает характеристики ПК (CPU, RAM, плата, диск, GPU).
  2. Сравнивает с последним успешно отправленным снимком (локальный кэш).
  3. Отправляет данные на Django-бэкенд (POST).
  4. Кэш обновляет только после успешной отправки — чтобы не потерять
     изменение, если в момент запуска не было сети.

Зависимости:
    pip install wmi pywin32 requests

Запуск:
    python agent.py
"""

import os
import sys
import json
import time
import logging
import datetime
import winreg

import wmi
import requests


# ============================================================
#  КОНФИГУРАЦИЯ
# ============================================================

BACKEND_URL = "https://test/api/inventory/"  # ← адрес твоего Django-эндпоинта
API_TOKEN = "token"                       # ← общий токен агентов
TIMEOUT = 15          # таймаут запроса, сек
SEND_RETRIES = 5      # попыток отправки (на случай, если сеть при загрузке ещё не поднялась)
RETRY_DELAY = 20      # пауза между попытками, сек

# Кэш и лог кладём в ProgramData — доступно всем пользователям и системной задаче
_BASE_DIR = os.path.join(os.environ.get("PROGRAMDATA", os.getcwd()), "PCInventory")
os.makedirs(_BASE_DIR, exist_ok=True)
CACHE_FILE = os.path.join(_BASE_DIR, "last_snapshot.json")
LOG_FILE = os.path.join(_BASE_DIR, "agent.log")

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    encoding="utf-8",
)


# ============================================================
#  СБОР ДАННЫХ
# ============================================================

def _bytes_to_gb(value) -> int:
    return round(int(value) / (1024 ** 3))


def get_machine_id() -> str:
    """Стабильный уникальный ID Windows-установки (первичный ключ в БД)."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
        ) as key:
            guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            return guid
    except OSError:
        # запасной вариант — UUID из WMI
        return wmi.WMI().Win32_ComputerSystemProduct()[0].UUID


def collect_specs() -> dict:
    """Возвращает только характеристики железа (то, что отслеживаем на изменения)."""
    c = wmi.WMI()

    cpu = c.Win32_Processor()[0].Name.strip()

    total_ram = sum(int(m.Capacity) for m in c.Win32_PhysicalMemory())
    ram = f"{_bytes_to_gb(total_ram)} GB"

    board = c.Win32_BaseBoard()[0]
    motherboard = f"{board.Manufacturer} {board.Product}".strip()

    disk = c.Win32_DiskDrive()[0]
    ssd = f"{disk.Model.strip()} {_bytes_to_gb(disk.Size)}GB"

    gpu = c.Win32_VideoController()[0].Name.strip()

    return {
        "cpu": cpu,
        "ram": ram,
        "motherboard": motherboard,
        "ssd": ssd,
        "gpu": gpu,
    }


def build_payload(specs: dict) -> dict:
    """Формирует тело запроса — плоский формат, как в исходном JSON."""
    payload = {"pc": wmi.WMI().Win32_ComputerSystem()[0].Name}
    payload.update(specs)  # cpu, ram, motherboard, ssd, gpu
    payload["last_update"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    return payload


# ============================================================
#  ЛОКАЛЬНЫЙ ДИФ
# ============================================================

def load_cache() -> dict:
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_cache(specs: dict) -> None:
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(specs, f, ensure_ascii=False, indent=2)


def diff_specs(old: dict, new: dict) -> dict:
    """Возвращает {поле: {'old': ..., 'new': ...}} по изменившимся полям."""
    changes = {}
    keys = set(old) | set(new)
    for key in keys:
        old_val = old.get(key)
        new_val = new.get(key)
        if old_val != new_val:
            changes[key] = {"old": old_val, "new": new_val}
    return changes


# ============================================================
#  ОТПРАВКА
# ============================================================

def send(payload: dict) -> bool:
    headers = {
        "Authorization": f"Token {API_TOKEN}",   # под DRF TokenAuthentication
        "Content-Type": "application/json",
    }
    for attempt in range(1, SEND_RETRIES + 1):
        try:
            resp = requests.post(
                BACKEND_URL, json=payload, headers=headers, timeout=TIMEOUT
            )
            resp.raise_for_status()
            logging.info("Отправлено успешно (HTTP %s)", resp.status_code)
            return True
        except requests.RequestException as e:
            logging.warning("Попытка %s/%s не удалась: %s", attempt, SEND_RETRIES, e)
            if attempt < SEND_RETRIES:
                time.sleep(RETRY_DELAY)
    logging.error("Не удалось отправить данные после %s попыток", SEND_RETRIES)
    return False


# ============================================================
#  ГЛАВНАЯ ЛОГИКА
# ============================================================

def main() -> int:
    try:
        specs = collect_specs()
    except Exception as e:
        logging.exception("Ошибка сбора данных: %s", e)
        return 1

    # Локальный диф — только для лога. В тело запроса он больше не входит:
    # изменения вычисляет сервер, сравнивая новые specs с тем, что в БД.
    previous = load_cache()
    changes = diff_specs(previous, specs)
    if changes:
        logging.info("Обнаружены изменения: %s", changes)
    else:
        logging.info("Изменений нет (heartbeat).")

    payload = build_payload(specs)

    if send(payload):
        # Кэш обновляем ТОЛЬКО после успешной отправки
        save_cache(specs)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
