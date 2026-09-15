"""Innstillinger som persisteres mellom økter (vindusstørrelse, volum m.m.).

Lagres i %APPDATA%\\TankmelkScanner\\settings.json -- bevisst utenfor git-repoet,
siden dette er maskinspesifikk tilstand (vindusstørrelse på akkurat denne PC-en osv.).

Sorteringsmodus- og duplikatkontroll-status lagres IKKE her -- begge skal alltid
starte i utgangsposisjon (av) ved hver oppstart av appen.
"""

import json
import os

APP_DIR = os.path.join(os.environ["APPDATA"], "TankmelkScanner")
SETTINGS_PATH = os.path.join(APP_DIR, "settings.json")
VOICE_CUES_DIR = os.path.join(APP_DIR, "voice_cues")
VOLUME_CACHE_DIR = os.path.join(APP_DIR, "voice_cues_volume_cache")

DEFAULTS = {
    "schema_version": 1,
    "volume": 0.8,
    "window_geometry": {
        "normal": {"width": 600, "height": 400, "x": None, "y": None},
        "sorting": {"width": None, "height": None, "x": None, "y": None},
    },
    "last_excel_path": None,
    "last_code_format": None,
}


def _merge_defaults(data: dict, defaults: dict) -> dict:
    """Fyller inn manglende/ugyldige felt fra defaults, rekursivt for dict-verdier."""
    result = dict(defaults)
    for key, default_value in defaults.items():
        if key not in data:
            continue
        value = data[key]
        if isinstance(default_value, dict) and isinstance(value, dict):
            result[key] = _merge_defaults(value, default_value)
        elif type(value) is type(default_value) or default_value is None:
            result[key] = value
        # feil type -> behold default, ignorer den ugyldige verdien
    return result


def load() -> dict:
    if not os.path.exists(SETTINGS_PATH):
        return json.loads(json.dumps(DEFAULTS))
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return json.loads(json.dumps(DEFAULTS))
        return _merge_defaults(data, DEFAULTS)
    except (json.JSONDecodeError, OSError):
        return json.loads(json.dumps(DEFAULTS))


def save(data: dict) -> None:
    os.makedirs(APP_DIR, exist_ok=True)
    tmp_path = SETTINGS_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, SETTINGS_PATH)
