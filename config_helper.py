import json
import os

import global_value as g


def read_config(name: str = "config.json"):
    if not os.path.isabs(name):
        name = os.path.join(g.base_dir, name)
    with open(name, "r", encoding="utf-8") as f:
        return json.load(f)
