import json
import os
from datetime import datetime, timedelta

import pytz

import config

ET = pytz.timezone("America/New_York")
_CACHE_DIR = os.path.expanduser("~/.punktrader")


def _cache_path(date):
    return os.path.join(_CACHE_DIR, f"levels_{date.strftime('%Y-%m-%d')}.json")


def _ensure_dir():
    os.makedirs(_CACHE_DIR, exist_ok=True)


def _current_et_time():
    return datetime.now(ET)


def is_locked(level_name: str) -> bool:
    et_now = _current_et_time()
    et_time = et_now.hour * 100 + et_now.minute

    if level_name in ("PDH", "PDL"):
        return True
    elif level_name in ("PMH", "PML"):
        return et_time >= 930
    elif level_name in ("ORH", "ORL"):
        return et_time >= 935
    return False


def get(ticker: str) -> dict | None:
    et_now = _current_et_time()
    today = et_now.date()
    cache_file = _cache_path(today)

    if not os.path.exists(cache_file):
        return None

    try:
        with open(cache_file, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return None

    if ticker not in data:
        return None

    entry = data[ticker]
    for level_name in ("PDH", "PDL", "PMH", "PML", "ORH", "ORL"):
        if level_name in entry and isinstance(entry[level_name], dict):
            if not entry[level_name].get("locked", False) and is_locked(level_name):
                entry[level_name]["locked"] = True

    result = {}
    for level_name in ("PDH", "PDL", "PMH", "PML", "ORH", "ORL"):
        if level_name in entry:
            level_data = entry[level_name]
            if isinstance(level_data, dict):
                result[level_name] = level_data.get("value")
            else:
                result[level_name] = level_data
        else:
            result[level_name] = None

    return result


def set(ticker: str, levels: dict) -> None:
    _ensure_dir()

    et_now = _current_et_time()
    today = et_now.date()
    cache_file = _cache_path(today)

    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            data = {}
    else:
        data = {}

    if ticker not in data:
        data[ticker] = {}

    entry = data[ticker]
    computed_at = int(et_now.timestamp())

    for level_name, value in levels.items():
        if level_name in ("PDH", "PDL", "PMH", "PML", "ORH", "ORL"):
            entry[level_name] = {
                "value": value,
                "locked": is_locked(level_name)
            }

    entry["computed_at"] = computed_at

    tmp_file = cache_file + ".tmp"
    try:
        with open(tmp_file, "w") as f:
            json.dump(data, f)
        os.replace(tmp_file, cache_file)
    except IOError:
        if os.path.exists(tmp_file):
            os.remove(tmp_file)
        raise


def purge_old() -> None:
    _ensure_dir()

    if not os.path.isdir(_CACHE_DIR):
        return

    cutoff = datetime.now() - timedelta(days=7)

    for filename in os.listdir(_CACHE_DIR):
        if not filename.startswith("levels_") or not filename.endswith(".json"):
            continue

        file_path = os.path.join(_CACHE_DIR, filename)
        try:
            file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
            if file_mtime < cutoff:
                os.remove(file_path)
        except (OSError, ValueError):
            pass
