"""Basic tests for AI News Agent Pro"""

import pytest
from config.settings import settings


def test_settings_loaded():
    """Test that settings are loaded properly"""
    assert settings.app_name == "AI News Agent Pro"
    assert settings.database_url is not None


def test_imports():
    """Test that all main modules can be imported"""
    try:
        from core.database import init_db
        from core.models import Article
        from config.prompts import NEWS_ANALYZER_PROMPT
        assert True
    except ImportError as e:
        pytest.fail(f"Import failed: {e}")


@pytest.mark.asyncio
async def test_database_init():
    """Test database initialization"""
    from core.database import init_db
    # This should not raise an exception
    await init_db()