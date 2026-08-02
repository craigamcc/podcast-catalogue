import re
import json
import os
from typing import Dict

from .config import data_path

REGISTRY_FILE = data_path("entity_registry.json")

# Default core corrections if file doesn't exist
DEFAULT_CORRECTIONS = {
    r"\bBargara\b": "Barbara",
    r"\bWoolly Gonga\b": "Wollongong",
    r"\bCanbra\b": "Canberra",
    r"\bIn the rail\b": "Innisfail",
    r"\bPK\b": "Patricia Karvelas",
}

def load_registry() -> Dict[str, str]:
    if os.path.exists(REGISTRY_FILE):
        try:
            with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return DEFAULT_CORRECTIONS
    return DEFAULT_CORRECTIONS

def save_registry(registry: Dict[str, str]):
    os.makedirs(os.path.dirname(REGISTRY_FILE), exist_ok=True)
    with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=4, ensure_ascii=False)

def apply_corrections(text: str) -> str:
    """Apply all registered entity corrections to a block of text."""
    if not text:
        return text
    
    registry = load_registry()
    corrected = text
    for pattern, replacement in registry.items():
        try:
            corrected = re.sub(pattern, replacement, corrected, flags=re.IGNORECASE)
        except Exception:
            continue # Skip invalid regex
    
    return corrected
