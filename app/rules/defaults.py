import os
import json
from typing import Dict, Any

SEED_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "seed"))

def load_json_seed(filename: str) -> Any:
    filepath = os.path.join(SEED_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def get_default_rule_config() -> Dict[str, Any]:
    """Build the system default rule_configs document."""
    keywords_data = load_json_seed("keywords.json")
    shorteners = load_json_seed("shorteners.json")
    suspicious_tlds = load_json_seed("suspicious_tlds.json")
    brands = load_json_seed("brands.json")
    free_mail = load_json_seed("free_mail_domains.json")
    disposable = load_json_seed("disposable_domains.json")
    dangerous_exts = load_json_seed("dangerous_extensions.json")

    rules_map = {
        # Group KW
        "R-KW-01": {"enabled": True, "points": 10},
        "R-KW-02": {"enabled": True, "points": 8},
        "R-KW-03": {"enabled": True, "points": 6},
        "R-KW-04": {"enabled": True, "points": 8},
        "R-KW-05": {"enabled": True, "points": 8},
        "R-KW-06": {"enabled": True, "points": 8},
        "R-KW-07": {"enabled": True, "points": 3},
        "R-KW-08": {"enabled": True, "points": 6},
        # Group SND
        "R-SND-01": {"enabled": True, "points": 10},
        "R-SND-02": {"enabled": True, "points": 10},
        "R-SND-03": {"enabled": True, "points": 15},
        "R-SND-04": {"enabled": True, "points": 15},
        "R-SND-05": {"enabled": True, "points": 20},
        "R-SND-06": {"enabled": True, "points": 8},
        "R-SND-07": {"enabled": True, "points": 12},
        "R-SND-08": {"enabled": True, "points": 10},
        "R-SND-09": {"enabled": True, "points": 15},
        "R-SND-10": {"enabled": True, "points": 6},
        # Group URL
        "R-URL-01": {"enabled": True, "points": 8},
        "R-URL-02": {"enabled": True, "points": 20},
        "R-URL-03": {"enabled": True, "points": 12},
        "R-URL-04": {"enabled": True, "points": 10},
        "R-URL-05": {"enabled": True, "points": 15},
        "R-URL-06": {"enabled": True, "points": 15},
        "R-URL-07": {"enabled": True, "points": 18},
        "R-URL-08": {"enabled": True, "points": 12},
        "R-URL-09": {"enabled": True, "points": 4},
        "R-URL-10": {"enabled": True, "points": 5},
        "R-URL-11": {"enabled": True, "points": 10},
        # Group CAP
        "R-CAP-01": {"enabled": True, "points": 8},
        "R-CAP-02": {"enabled": True, "points": 6},
        "R-CAP-03": {"enabled": True, "points": 4},
        # Group PUN
        "R-PUN-01": {"enabled": True, "points": 5},
        "R-PUN-02": {"enabled": True, "points": 4},
        # Group ATT
        "R-ATT-01": {"enabled": True, "points": 30},
        "R-ATT-02": {"enabled": True, "points": 25},
        "R-ATT-03": {"enabled": True, "points": 15},
        "R-ATT-04": {"enabled": True, "points": 8},
        "R-ATT-05": {"enabled": True, "points": 12},
        # Group CMB & GEN
        "R-GEN-01": {"enabled": True, "points": 4},
        "R-GEN-02": {"enabled": True, "points": 5},
        "R-CMB-01": {"enabled": True, "points": 10},
        "R-CMB-02": {"enabled": True, "points": 10}
    }

    return {
        "user_id": None,
        "version": 1,
        "thresholds": {"suspicious": 30, "spam": 60},
        "group_caps": {
            "KW": 40,
            "SND": 45,
            "URL": 50,
            "CAP": 14,
            "PUN": 9,
            "ATT": 60,
            "CMB": 20,
            "CUS": 50
        },
        "rules": rules_map,
        "keyword_categories": keywords_data,
        "shorteners": shorteners,
        "suspicious_tlds": suspicious_tlds,
        "brands": brands,
        "free_mail_domains": free_mail,
        "disposable_domains": disposable,
        "dangerous_extensions": dangerous_exts,
        "lists": {
            "allow_senders": [],
            "allow_domains": [],
            "block_senders": [],
            "block_domains": [],
            "extra_brands": []
        },
        "custom_rules": []
    }
