import json
import os

def load_config(path=None):
    if path is None:
        path = os.environ.get("CONFIG_PATH")
        if path is None:
            base = os.path.dirname(os.path.dirname(__file__))
            local = os.path.join(base, "config.local.json")
            path = local if os.path.exists(local) else os.path.join(base, "config.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
