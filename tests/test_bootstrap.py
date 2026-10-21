import os
import tempfile
from pathlib import Path

from openrecognition.bootstrap import run_bootstrap
from openrecognition.config import Settings
from openrecognition.gallery.db import Database


def _settings(tmp: str) -> Settings:
    return Settings(
        data_dir=Path(tmp) / "data",
        model_packs_dir=Path(os.environ.get("OPENRECOGNITION_MODEL_PACKS_DIR", "model-packs")),
    )


def test_run_bootstrap_creates_database_without_credentials():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _settings(tmp)
        run_bootstrap(cfg)
        assert cfg.db_path.is_file()
        assert not cfg.bootstrap_key_path.exists()
        assert not cfg.admin_password_path.exists()
        assert Database(cfg.db_path).fetchone("SELECT id FROM users LIMIT 1") is None
        assert Database(cfg.db_path).fetchone("SELECT id FROM api_keys LIMIT 1") is None

        run_bootstrap(cfg)
        assert Database(cfg.db_path).fetchone("SELECT id FROM users LIMIT 1") is None
