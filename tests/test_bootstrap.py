import os
import tempfile
from pathlib import Path

from openrecognition.bootstrap import run_bootstrap
from openrecognition.config import Settings


def _settings(tmp: str) -> Settings:
    return Settings(
        data_dir=Path(tmp) / "data",
        model_packs_dir=Path(os.environ.get("OPENRECOGNITION_MODEL_PACKS_DIR", "model-packs")),
    )


def test_run_bootstrap_creates_key_once():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _settings(tmp)
        result = run_bootstrap(cfg)
        assert result.api_key
        assert result.admin_password
        assert result.admin_password != "admin"
        assert cfg.bootstrap_key_path.read_text().strip() == result.api_key
        assert cfg.admin_password_path.read_text().strip() == result.admin_password
        assert oct(cfg.admin_password_path.stat().st_mode & 0o777) == "0o600"

        again = run_bootstrap(cfg)
        assert again.api_key is None
        assert again.admin_password is None
        assert cfg.admin_password_path.read_text().strip() == result.admin_password


def test_run_bootstrap_replaces_default_admin_password():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _settings(tmp)
        cfg.data_dir.mkdir(parents=True)
        from openrecognition.auth.sessions import SessionService
        from openrecognition.gallery.db import Database

        sessions = SessionService(Database(cfg.db_path))
        assert sessions.ensure_default_admin(password="admin") == "admin"

        result = run_bootstrap(cfg)
        assert result.admin_password
        assert result.admin_password != "admin"
        assert sessions.authenticate_user("admin", result.admin_password)
        assert sessions.authenticate_user("admin", "admin") is None
