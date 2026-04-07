import os
from pathlib import Path

import yaml


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""
    pass


def get_config(root_dir: str = ".") -> dict:
    """Load configuration from config.yaml in *root_dir*.

    Environment variable ``LLM_WIKI_API_KEY`` overrides the yaml value.
    """
    config_path = Path(root_dir) / "config.yaml"
    if not config_path.exists():
        raise ConfigError(
            f"config.yaml not found in {Path(root_dir).resolve()}.\n"
            "Run 'llm-wiki init' first to create the project structure."
        )

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    # Ensure top-level keys exist
    config.setdefault("llm", {})
    config.setdefault("wiki", {})

    # Environment variable override
    env_key = os.environ.get("LLM_WIKI_API_KEY")
    if env_key:
        config["llm"]["api_key"] = env_key

    # Validate required LLM fields
    if not config["llm"].get("api_key"):
        raise ConfigError(
            "LLM API key is not configured.\n"
            "Set it in config.yaml under llm.api_key, "
            "or export LLM_WIKI_API_KEY environment variable."
        )

    # Defaults
    config["llm"].setdefault("base_url", "https://api.openai.com/v1")
    config["llm"].setdefault("model", "gpt-4o")

    config["wiki"].setdefault("root", root_dir)
    config["wiki"].setdefault("raw_dir", "raw")
    config["wiki"].setdefault("wiki_dir", "wiki")
    config["wiki"].setdefault("schema_dir", "schema")

    return config
