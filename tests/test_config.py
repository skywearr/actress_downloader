from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from actress_downloader.config import AppConfig, DEFAULT_DATABASE_NAME, MissingSecretError


class ConfigTests(unittest.TestCase):
    def test_loads_non_sensitive_settings_and_reads_secrets_from_dotenv(self) -> None:
        temp_root = PROJECT_ROOT / ".tmp_test_config"
        shutil.rmtree(temp_root, ignore_errors=True)
        temp_root.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(temp_root, ignore_errors=True))

        config_dir = temp_root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "settings.toml"
        config_path.write_text(
            "\n".join(
                [
                    "[postgres]",
                    'host = "db.internal"',
                    "port = 5433",
                    'sslmode = "prefer"',
                    "",
                    "[llm]",
                    'provider = "glm"',
                    'model = "glm-5.1"',
                    'base_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"',
                    "tagging_temperature = 0.1",
                    "alias_lookup_temperature = 0.02",
                    "timeout_seconds = 30.0",
                    "enabled = true",
                ]
            ),
            encoding="utf-8",
        )
        (temp_root / ".env").write_text(
            "\n".join(
                [
                    "PGUSER=app_user",
                    "PGPASSWORD=secret",
                    "GLM_API_KEY=demo-key",
                ]
            ),
            encoding="utf-8",
        )

        config = AppConfig.from_file(config_path)

        self.assertEqual("db.internal", config.postgres.host)
        self.assertEqual(5433, config.postgres.port)
        self.assertEqual(DEFAULT_DATABASE_NAME, config.postgres.database)
        self.assertIn(f"app_user:secret@db.internal:5433/{DEFAULT_DATABASE_NAME}", config.database_url)
        self.assertEqual("glm-5.1", config.llm.model)
        self.assertEqual("demo-key", config.llm.api_key)
        self.assertEqual(0.1, config.llm.tagging_temperature)
        self.assertEqual(0.1, config.llm.temperature)
        self.assertEqual(0.02, config.llm.alias_lookup_temperature)
        self.assertTrue(config.llm.is_active)

    def test_prefers_environment_over_dotenv_for_sensitive_values(self) -> None:
        temp_root = PROJECT_ROOT / ".tmp_test_config_env"
        shutil.rmtree(temp_root, ignore_errors=True)
        temp_root.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(temp_root, ignore_errors=True))

        config_dir = temp_root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "settings.toml"
        config_path.write_text(
            "\n".join(
                [
                    "[llm]",
                    'provider = "xai"',
                    'model = "grok-4.20"',
                    "tagging_temperature = 0.15",
                    "alias_lookup_temperature = 0.01",
                ]
            ),
            encoding="utf-8",
        )
        (temp_root / ".env").write_text(
            "\n".join(
                [
                    "PGUSER=file-user",
                    "PGPASSWORD=file-password",
                    "XAI_API_KEY=file-key",
                ]
            ),
            encoding="utf-8",
        )

        old_values = {
            "PGUSER": os.environ.get("PGUSER"),
            "PGPASSWORD": os.environ.get("PGPASSWORD"),
            "XAI_API_KEY": os.environ.get("XAI_API_KEY"),
        }
        try:
            os.environ["PGUSER"] = "env-user"
            os.environ["PGPASSWORD"] = "env-password"
            os.environ["XAI_API_KEY"] = "env-key"
            config = AppConfig.from_file(config_path)
        finally:
            for key, value in old_values.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        self.assertEqual("env-user", config.postgres.user)
        self.assertIn("env-user:env-password@", config.database_url)
        self.assertEqual("env-key", config.llm.api_key)
        self.assertEqual("https://api.x.ai/v1/responses", config.llm.base_url)
        self.assertEqual(0.15, config.llm.tagging_temperature)
        self.assertEqual(0.01, config.llm.alias_lookup_temperature)

    def test_raises_when_required_secrets_are_missing(self) -> None:
        temp_root = PROJECT_ROOT / ".tmp_test_config_missing"
        shutil.rmtree(temp_root, ignore_errors=True)
        temp_root.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(temp_root, ignore_errors=True))

        config_dir = temp_root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "settings.toml"
        config_path.write_text(
            "\n".join(
                [
                    "[postgres]",
                    'host = "127.0.0.1"',
                    "",
                    "[llm]",
                    'provider = "xai"',
                ]
            ),
            encoding="utf-8",
        )

        old_values = {
            "PGUSER": os.environ.get("PGUSER"),
            "PGPASSWORD": os.environ.get("PGPASSWORD"),
            "XAI_API_KEY": os.environ.get("XAI_API_KEY"),
            "LLM_API_KEY": os.environ.get("LLM_API_KEY"),
        }
        try:
            for key in old_values:
                os.environ.pop(key, None)
            with self.assertRaises(MissingSecretError):
                AppConfig.from_file(config_path)
        finally:
            for key, value in old_values.items():
                if value is not None:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
