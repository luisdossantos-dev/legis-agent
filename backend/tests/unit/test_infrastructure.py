"""
🔵 UNIT TESTS — Infrastructure files existence and correctness.

Verifies that the project infrastructure files exist and are syntactically valid.
"""

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def test_dockerfile_exists():
    """Dockerfile exists for production builds."""
    assert (PROJECT_ROOT / "backend" / "Dockerfile").exists()


def test_dockerignore_exists():
    """Dockerignore exists with proper exclusions."""
    dj = PROJECT_ROOT / "backend" / ".dockerignore"
    assert dj.exists()
    content = dj.read_text()
    assert ".git/" in content
    assert ".venv/" in content
    assert ".env" in content


def test_docker_compose_exists():
    """Docker compose file exists for dev environment."""
    assert (PROJECT_ROOT / "docker-compose.yml").exists()


def test_ci_workflow_exists():
    """CI workflow exists for GitHub Actions."""
    ci = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
    assert ci.exists()
    content = ci.read_text()
    assert "on:" in content
    assert "jobs:" in content


def test_env_example_exists():
    """Env example file exists for documentation."""
    assert (PROJECT_ROOT / "backend" / ".env.example").exists()


def test_gitignore_exists():
    """Gitignore excludes sensitive files."""
    gi = PROJECT_ROOT / ".gitignore"
    assert gi.exists()
    content = gi.read_text()
    assert ".env" in content
    assert "__pycache__" in content


def test_rollback_plan_exists():
    """Rollback plan documentation exists."""
    rp = PROJECT_ROOT / "docs" / "rollback-plan.md"
    assert rp.exists()
    content = rp.read_text()
    assert "Rollback" in content


def test_readme_exists():
    """README exists with English content."""
    readme = PROJECT_ROOT / "README.md"
    assert readme.exists()
    content = readme.read_text()
    assert "Legis Agent" in content
    # Should not have excessive emoji headers
    emoji_headers = sum(1 for line in content.splitlines() if line.startswith("## ") and any(c in line for c in "✨🚀📋🔧🌐🎨🧪📦📄🤝"))
    assert emoji_headers < 5, f"Too many emoji headers ({emoji_headers}), should be < 5"
