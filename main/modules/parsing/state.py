from modules import config


def _load():
    values = {}
    try:
        lines = config.STATE_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def get(key, default=None):
    return _load().get(key, default)


def set_value(key, value):
    values = _load()
    values[key] = str(value)
    _save(values)


def get_bool(key, default=False):
    value = _load().get(key)
    return default if value is None else value.lower() in ("1", "true", "yes", "on")


def _save(values):
    config.STATES_DIR.mkdir(parents=True, exist_ok=True)
    text = "".join(f"{k} = {v}\n" for k, v in sorted(values.items()))
    config.STATE_FILE.write_text(text, encoding="utf-8")


def set_bool(key, value):
    values = _load()
    values[key] = "true" if value else "false"
    _save(values)
