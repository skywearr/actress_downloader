from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
import tomllib
from urllib.parse import quote_plus


DEFAULT_DATABASE_NAME = "actress_downloader"


class MissingSecretError(RuntimeError):
    """Raised when a required secret cannot be resolved from env or .env."""


@dataclass(slots=True)
class PostgresConfig:
    host: str
    port: int
    user: str
    password: str
    sslmode: str = "prefer"
    database: str = DEFAULT_DATABASE_NAME

    @property
    def database_url(self) -> str:
        user = quote_plus(self.user)
        password = quote_plus(self.password)
        return (
            f"postgresql://{user}:{password}"
            f"@{self.host}:{self.port}/{self.database}?sslmode={self.sslmode}"
        )

    def with_database(self, database: str) -> "PostgresConfig":
        return PostgresConfig(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            sslmode=self.sslmode,
            database=database,
        )


@dataclass(slots=True)
class LLMConfig:
    provider: str
    model: str
    api_key: str
    base_url: str
    temperature: float
    tagging_temperature: float
    alias_lookup_temperature: float
    timeout_seconds: float
    enabled: bool

    @property
    def is_active(self) -> bool:
        normalized = self.api_key.strip().lower()
        return self.enabled and bool(normalized) and "your_" not in normalized


@dataclass(slots=True)
class PathConfig:
    seed_file: Path
    library_root: Path
    schema_file: Path


@dataclass(slots=True)
class AppConfig:
    postgres: PostgresConfig
    llm: LLMConfig
    paths: PathConfig
    config_path: Path

    @classmethod
    def from_file(cls, config_path: Path | None = None) -> "AppConfig":
        project_root = Path(__file__).resolve().parents[2]
        resolved_config_path = config_path or (project_root / "config" / "settings.toml")
        file_payload = cls._load_toml(resolved_config_path)
        dotenv_payload = _load_project_dotenv(
            resolved_config_path=resolved_config_path,
            default_project_root=project_root,
        )

        postgres_payload = file_payload.get("postgres", {})
        llm_payload = file_payload.get("llm", {})
        paths_payload = file_payload.get("paths", {})
        llm_provider = os.environ.get("LLM_PROVIDER", llm_payload.get("provider", "xai"))

        return cls(
            postgres=PostgresConfig(
                host=postgres_payload.get("host", "127.0.0.1"),
                port=int(postgres_payload.get("port", 5432)),
                user=_resolve_required_secret(
                    env_names=("PGUSER",),
                    dotenv_payload=dotenv_payload,
                    secret_label="PostgreSQL user",
                ),
                password=_resolve_required_secret(
                    env_names=("PGPASSWORD",),
                    dotenv_payload=dotenv_payload,
                    secret_label="PostgreSQL password",
                ),
                sslmode=postgres_payload.get("sslmode", "prefer"),
            ),
            llm=LLMConfig(
                provider=llm_provider,
                model=llm_payload.get("model", _default_llm_model(llm_provider)),
                api_key=_resolve_llm_api_key(llm_provider, dotenv_payload),
                base_url=llm_payload.get("base_url", _default_llm_base_url(llm_provider)),
                temperature=float(llm_payload.get("tagging_temperature", llm_payload.get("temperature", 0.2))),
                tagging_temperature=float(llm_payload.get("tagging_temperature", llm_payload.get("temperature", 0.2))),
                alias_lookup_temperature=float(llm_payload.get("alias_lookup_temperature", 0.05)),
                timeout_seconds=float(llm_payload.get("timeout_seconds", 60.0)),
                enabled=_as_bool(os.environ.get("LLM_ENABLED"), llm_payload.get("enabled", True)),
            ),
            paths=PathConfig(
                seed_file=project_root / paths_payload.get("seed_file", "examples/demo_catalog.json"),
                library_root=project_root / paths_payload.get("library_root", "library"),
                schema_file=project_root / paths_payload.get("schema_file", "sql/init_schema.sql"),
            ),
            config_path=resolved_config_path,
        )

    @property
    def database_url(self) -> str:
        return self.postgres.database_url

    @staticmethod
    def _load_toml(config_path: Path) -> dict:
        if not config_path.exists():
            return {}
        with config_path.open("rb") as file_handle:
            return tomllib.load(file_handle)


def _as_bool(env_value: str | None, fallback: bool) -> bool:
    if env_value is None:
        return bool(fallback)
    return env_value.strip().lower() in {"1", "true", "yes", "on"}


def _default_llm_model(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized == "glm":
        return "glm-4.7"
    return "grok-4.20"


def _default_llm_base_url(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized == "glm":
        return "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    return "https://api.x.ai/v1/responses"


def _load_dotenv(dotenv_path: Path) -> dict[str, str]:
    if not dotenv_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        normalized_key = key.strip()
        normalized_value = value.strip()
        if (
            len(normalized_value) >= 2
            and normalized_value[0] == normalized_value[-1]
            and normalized_value[0] in {'"', "'"}
        ):
            normalized_value = normalized_value[1:-1]
        values[normalized_key] = normalized_value
    return values


def _load_project_dotenv(
    resolved_config_path: Path,
    default_project_root: Path,
) -> dict[str, str]:
    candidate_paths: list[Path] = []
    default_config_path = default_project_root / "config" / "settings.toml"

    config_parent = resolved_config_path.parent
    if config_parent.name == "config":
        candidate_paths.append(config_parent.parent / ".env")

    if resolved_config_path.resolve() == default_config_path.resolve():
        candidate_paths.append(default_project_root / ".env")

    seen: set[Path] = set()
    for candidate_path in candidate_paths:
        resolved_candidate = candidate_path.resolve()
        if resolved_candidate in seen:
            continue
        seen.add(resolved_candidate)
        dotenv_payload = _load_dotenv(candidate_path)
        if dotenv_payload:
            return dotenv_payload
    return {}


def _resolve_required_secret(
    env_names: tuple[str, ...],
    dotenv_payload: dict[str, str],
    secret_label: str,
) -> str:
    for env_name in env_names:
        env_value = os.environ.get(env_name)
        if env_value:
            return env_value

    for env_name in env_names:
        dotenv_value = dotenv_payload.get(env_name)
        if dotenv_value:
            return dotenv_value

    joined_names = ", ".join(env_names)
    raise MissingSecretError(
        f"Missing {secret_label}. Set one of {joined_names} in the environment or in .env."
    )


def _resolve_llm_api_key(provider: str, dotenv_payload: dict[str, str]) -> str:
    normalized = provider.strip().lower()
    candidate_env_names = ["LLM_API_KEY"]
    if normalized == "glm":
        candidate_env_names = ["GLM_API_KEY", "ZHIPUAI_API_KEY", *candidate_env_names]
    if normalized == "xai":
        candidate_env_names = ["XAI_API_KEY", *candidate_env_names]

    return _resolve_required_secret(
        env_names=tuple(candidate_env_names),
        dotenv_payload=dotenv_payload,
        secret_label=f"{normalized or 'llm'} API key",
    )
