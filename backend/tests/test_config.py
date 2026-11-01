"""Env plumbing tests (Sprint 3 Step A — backend/config.py).

config.py centralizes every environment variable the app reads, with
documented defaults and validated parsing (the audit_logger._env_int
pattern: absent/blank/invalid values fall back to the documented default
with a logged warning, never raise). All accessors read the environment
at CALL time so operators can flip a variable without code changes and
tests can monkeypatch freely.

CORS posture: dev defaults to the local frontend origin; production is
FAIL-CLOSED — unset, empty, or wildcard CORS_ORIGINS raises so the app
can never silently serve wide-open in prod. (The allowlist itself only
activates on the wire in the auth wave; this wave the middleware stack
still runs the wildcard CORS — the check here is the config-level stub.)
"""
import logging

import pytest

import config


# Every env var config.py may read; cleared per test so defaults are
# deterministic regardless of the developer's shell.
_CONFIG_ENV_VARS = (
    "APP_ENV",
    "CORS_ORIGINS",
    "TAX_DB_PATH",
    "TAX_HOST",
    "TAX_PORT",
    "TAX_SESSION_TTL_MINUTES",
    "TAX_SESSION_ABS_TTL_HOURS",
    "TAX_COOKIE_SECURE",
    "TAX_ENABLE_ANON_DEMO",
    "TAX_ENABLE_HISTORY",
    "TAX_MAX_BODY_BYTES",
    "TAX_LOG_LEVEL",
    "TAX_RATE_LIMIT_AUTH_PER_MIN",
    "TAX_RATE_LIMIT_CHAT_PER_MIN",
    "TAX_RATE_LIMIT_CALC_PER_MIN",
    "TAX_RATE_LIMIT_GLOBAL_PER_MIN",
    "TAX_AUDIT_MAX_BYTES",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in _CONFIG_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


class TestDocumentedDefaults:
    def test_app_env_defaults_to_dev(self) -> None:
        assert config.app_env() == "dev"

    def test_cors_defaults_to_local_frontend_origin(self) -> None:
        assert config.cors_origins() == ["http://localhost:3000"]

    def test_bind_defaults_are_loopback_safe(self) -> None:
        # Dev bind safety: the server must never default to 0.0.0.0.
        assert config.tax_host() == "127.0.0.1"
        assert config.tax_port() == 8000

    def test_db_path_default(self) -> None:
        assert config.tax_db_path() == "data/taxassist.db"

    def test_session_ttl_defaults(self) -> None:
        assert config.session_ttl_minutes() == 30
        assert config.session_abs_ttl_hours() == 24

    def test_body_cap_default_is_1mb(self) -> None:
        assert config.tax_max_body_bytes() == 1_000_000

    def test_log_level_default(self) -> None:
        assert config.tax_log_level() == "INFO"

    def test_anon_demo_off_by_default(self) -> None:
        assert config.tax_enable_anon_demo() is False

    def test_cookie_secure_derived_from_dev(self) -> None:
        assert config.tax_cookie_secure() is False

    def test_rate_limit_defaults(self) -> None:
        assert config.rate_limit_auth_per_min() == 10
        assert config.rate_limit_chat_per_min() == 30
        assert config.rate_limit_calc_per_min() == 60
        assert config.rate_limit_global_per_min() == 120


class TestAppEnvNormalization:
    def test_prod_is_case_insensitive(self, monkeypatch) -> None:
        monkeypatch.setenv("APP_ENV", "PROD")
        assert config.app_env() == "prod"

    def test_unknown_value_is_dev(self, monkeypatch) -> None:
        # Fail safe: only an explicit "prod" enables prod posture.
        monkeypatch.setenv("APP_ENV", "staging")
        assert config.app_env() == "dev"

    def test_prod_enables_secure_cookie(self, monkeypatch) -> None:
        monkeypatch.setenv("APP_ENV", "prod")
        assert config.tax_cookie_secure() is True


class TestIntParsing:
    @pytest.mark.parametrize(
        ("name", "accessor", "default"),
        [
            ("TAX_PORT", config.tax_port, 8000),
            ("TAX_SESSION_TTL_MINUTES", config.session_ttl_minutes, 30),
            ("TAX_SESSION_ABS_TTL_HOURS", config.session_abs_ttl_hours, 24),
            ("TAX_MAX_BODY_BYTES", config.tax_max_body_bytes, 1_000_000),
            ("TAX_RATE_LIMIT_CHAT_PER_MIN", config.rate_limit_chat_per_min, 30),
        ],
    )
    def test_invalid_int_falls_back_to_default(
        self, monkeypatch, name, accessor, default
    ) -> None:
        monkeypatch.setenv(name, "not-a-number")
        assert accessor() == default

    def test_below_minimum_falls_back_to_default(self, monkeypatch) -> None:
        monkeypatch.setenv("TAX_PORT", "0")
        assert config.tax_port() == 8000

    def test_blank_value_falls_back_to_default(self, monkeypatch) -> None:
        monkeypatch.setenv("TAX_MAX_BODY_BYTES", "   ")
        assert config.tax_max_body_bytes() == 1_000_000

    def test_valid_values_are_parsed(self, monkeypatch) -> None:
        monkeypatch.setenv("TAX_PORT", "9001")
        monkeypatch.setenv("TAX_SESSION_TTL_MINUTES", "60")
        monkeypatch.setenv("TAX_SESSION_ABS_TTL_HOURS", "12")
        monkeypatch.setenv("TAX_MAX_BODY_BYTES", "2048")
        monkeypatch.setenv("TAX_RATE_LIMIT_CHAT_PER_MIN", "5")
        assert config.tax_port() == 9001
        assert config.session_ttl_minutes() == 60
        assert config.session_abs_ttl_hours() == 12
        assert config.tax_max_body_bytes() == 2048
        assert config.rate_limit_chat_per_min() == 5

    def test_fallback_logs_a_warning(self, monkeypatch, caplog) -> None:
        monkeypatch.setenv("TAX_PORT", "abc")
        with caplog.at_level(logging.WARNING, logger="config"):
            config.tax_port()
        assert any("TAX_PORT" in record.message for record in caplog.records)


class TestCorsParsing:
    def test_comma_list_is_split_and_stripped(self, monkeypatch) -> None:
        monkeypatch.setenv("CORS_ORIGINS", "http://a.com, http://b.com ,http://c.com")
        assert config.cors_origins() == [
            "http://a.com",
            "http://b.com",
            "http://c.com",
        ]

    def test_blank_in_dev_falls_back_to_default(self, monkeypatch) -> None:
        monkeypatch.setenv("CORS_ORIGINS", "   ")
        assert config.cors_origins() == ["http://localhost:3000"]

    def test_wildcard_allowed_in_dev(self, monkeypatch) -> None:
        monkeypatch.setenv("CORS_ORIGINS", "*")
        assert config.cors_origins() == ["*"]


class TestCorsProdFailClosed:
    """Production must never serve wildcard/unset origins (fail closed)."""

    def test_unset_in_prod_raises(self, monkeypatch) -> None:
        monkeypatch.setenv("APP_ENV", "prod")
        with pytest.raises(RuntimeError):
            config.cors_origins()

    def test_empty_in_prod_raises(self, monkeypatch) -> None:
        monkeypatch.setenv("APP_ENV", "prod")
        monkeypatch.setenv("CORS_ORIGINS", "")
        with pytest.raises(RuntimeError):
            config.cors_origins()

    def test_wildcard_in_prod_raises(self, monkeypatch) -> None:
        monkeypatch.setenv("APP_ENV", "prod")
        monkeypatch.setenv("CORS_ORIGINS", "*")
        with pytest.raises(RuntimeError):
            config.cors_origins()

    def test_explicit_origins_accepted_in_prod(self, monkeypatch) -> None:
        monkeypatch.setenv("APP_ENV", "prod")
        monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com")
        assert config.cors_origins() == ["https://app.example.com"]


class TestCookieSecureOverride:
    def test_explicit_true_wins_over_dev(self, monkeypatch) -> None:
        monkeypatch.setenv("TAX_COOKIE_SECURE", "1")
        assert config.tax_cookie_secure() is True

    def test_explicit_false_wins_over_prod(self, monkeypatch) -> None:
        monkeypatch.setenv("APP_ENV", "prod")
        monkeypatch.setenv("TAX_COOKIE_SECURE", "0")
        assert config.tax_cookie_secure() is False


class TestFlagParsing:
    @pytest.mark.parametrize("value", ["1", "true", "True"])
    def test_anon_demo_truthy(self, monkeypatch, value) -> None:
        monkeypatch.setenv("TAX_ENABLE_ANON_DEMO", value)
        assert config.tax_enable_anon_demo() is True

    @pytest.mark.parametrize("value", ["0", "false", "False", "yes", ""])
    def test_anon_demo_otherwise_off(self, monkeypatch, value) -> None:
        monkeypatch.setenv("TAX_ENABLE_ANON_DEMO", value)
        assert config.tax_enable_anon_demo() is False


class TestLogLevelValidation:
    def test_valid_level_normalized(self, monkeypatch) -> None:
        monkeypatch.setenv("TAX_LOG_LEVEL", "debug")
        assert config.tax_log_level() == "DEBUG"

    def test_invalid_level_falls_back_to_info(self, monkeypatch) -> None:
        monkeypatch.setenv("TAX_LOG_LEVEL", "LOUD")
        assert config.tax_log_level() == "INFO"


class TestAuditEnvPassthrough:
    def test_passthrough_reads_value(self, monkeypatch) -> None:
        monkeypatch.setenv("TAX_AUDIT_MAX_BYTES", "123")
        assert config.tax_audit_env("TAX_AUDIT_MAX_BYTES") == "123"

    def test_missing_var_returns_default(self) -> None:
        assert config.tax_audit_env("TAX_AUDIT_MAX_BYTES") is None
        assert config.tax_audit_env("TAX_AUDIT_MAX_BYTES", "x") == "x"


class TestDbPath:
    def test_db_path_override(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setenv("TAX_DB_PATH", str(tmp_path / "custom.db"))
        assert config.tax_db_path() == str(tmp_path / "custom.db")

    def test_blank_db_path_falls_back_to_default(self, monkeypatch) -> None:
        monkeypatch.setenv("TAX_DB_PATH", "  ")
        assert config.tax_db_path() == "data/taxassist.db"
