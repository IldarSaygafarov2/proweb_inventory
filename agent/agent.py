import os
import sys
import json
import time
import logging
import datetime
import winreg

import wmi
import requests

BACKEND_URL = "http://189.74.96.120/api/inventory/"
API_TOKEN = "b5472803d87544ac1b43f8e08a78e37dadb95cb7"
TIMEOUT = 15
SEND_RETRIES = 5
RETRY_DELAY = 20

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


def _bytes_to_gb(value) -> int:
    return round(int(value) / (1024 ** 3))


def get_machine_id() -> str:
    try:
        with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
        ) as key:
            guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            return guid
    except OSError:
        return wmi.WMI().Win32_ComputerSystemProduct()[0].UUID


def collect_specs() -> dict:
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
    payload = {"pc": wmi.WMI().Win32_ComputerSystem()[0].Name}
    payload.update(specs)
    payload["last_update"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    return payload


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
    changes = {}
    keys = set(old) | set(new)
    for key in keys:
        old_val = old.get(key)
        new_val = new.get(key)
        if old_val != new_val:
            changes[key] = {"old": old_val, "new": new_val}
    return changes


def send(payload: dict) -> bool:
    headers = {
        "Authorization": f"Token {API_TOKEN}",
        "Content-Type": "application/json",
    }
    for attempt in range(1, SEND_RETRIES + 1):
        try:
            resp = requests.post(
                BACKEND_URL, json=payload, headers=headers, timeout=TIMEOUT
            )
            resp.raise_for_status()
            logging.info("Отправлено успешно (HTTP %s) На ссылку (%s)", resp.status_code, BACKEND_URL)
            return True
        except requests.RequestException as e:
            logging.warning("Попытка %s/%s не удалась: %s", attempt, SEND_RETRIES, e)
            if attempt < SEND_RETRIES:
                time.sleep(RETRY_DELAY)
    logging.error("Не удалось отправить данные после %s попыток", SEND_RETRIES)
    return False


def main() -> int:
    try:
        specs = collect_specs()
    except Exception as e:
        logging.exception("Ошибка сбора данных: %s", e)
        return 1

    previous = load_cache()
    changes = diff_specs(previous, specs)
    if changes:
        logging.info("Обнаружены изменения: %s", changes)
    else:
        logging.info("Изменений нет (heartbeat).")

    payload = build_payload(specs)

    if send(payload):
        save_cache(specs)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
