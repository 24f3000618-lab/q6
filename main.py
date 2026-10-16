import os
from pathlib import Path

import yaml
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS: lets the grader's web page call your API from the browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Layer 1: hardcoded defaults
DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

ALIASES = {"num_workers": "workers"}  # NUM_WORKERS -> workers


def clean_key(key: str) -> str:
    """Lowercase the key and apply aliases."""
    key = key.strip().lower()
    return ALIASES.get(key, key)


def coerce(key: str, value):
    """Convert a value to the right type for its key."""
    if key in ("port", "workers"):
        return int(value)
    if key == "debug":
        return str(value).strip().lower() in ("true", "1", "yes", "on")
    return str(value)


def load_yaml(env_name: str) -> dict:
    path = Path(f"config.{env_name}.yaml")
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text()) or {}
    return {clean_key(k): v for k, v in data.items()}


def load_dotenv(path: str = ".env") -> dict:
    result = {}
    p = Path(path)
    if not p.exists():
        return result
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        if k.upper().startswith("APP_"):
            k = k[4:]  # APP_DEBUG -> DEBUG
        result[clean_key(k)] = v.strip().strip('"').strip("'")
    return result


def load_os_env() -> dict:
    result = {}
    for k, v in os.environ.items():
        if k.startswith("APP_"):
            result[clean_key(k[4:])] = v
    return result


@app.get("/effective-config")
def effective_config(set: list[str] = Query(default=[])):
    env_name = os.environ.get("CONFIG_ENV", "development")

    # CLI overrides from ?set=key=value
    cli = {}
    for item in set:
        if "=" in item:
            k, v = item.split("=", 1)
            cli[clean_key(k)] = v

    merged = {}
    # Later updates overwrite earlier ones = higher precedence
    for layer in (DEFAULTS, load_yaml(env_name), load_dotenv(), load_os_env(), cli):
        merged.update(layer)

    # Convert types, then mask the secret
    result = {k: coerce(k, v) for k, v in merged.items()}
    result["api_key"] = "****"
    return result