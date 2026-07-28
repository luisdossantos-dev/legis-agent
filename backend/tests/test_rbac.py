"""
Tests for RBAC + GDPR modules.
Run with: python -m pytest tests/test_rbac.py -v
"""

import os
import sys
import tempfile
from pathlib import Path

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi import HTTPException
from app.models.auth import (
    Role, Permission, ROLE_PERMISSIONS,
    UserCreate, AuthContext, AuditAction,
)


class TestRolePermissions:
    """Verify the role-permission matrix is correct."""

    def test_admin_has_all_permissions(self):
        perms = ROLE_PERMISSIONS[Role.ADMIN]
        for p in Permission:
            assert p in perms, f"Admin should have {p.value}"

    def test_notaire_permissions(self):
        perms = ROLE_PERMISSIONS[Role.NOTAIRE]
        assert Permission.READ in perms
        assert Permission.WRITE in perms
        assert Permission.DRAFT in perms
        assert Permission.FINALIZE in perms
        assert Permission.DELETE in perms
        assert Permission.ADMIN not in perms

    def test_assistant_permissions(self):
        perms = ROLE_PERMISSIONS[Role.ASSISTANT]
        assert Permission.READ in perms
        assert Permission.WRITE in perms
        assert Permission.DRAFT in perms
        assert Permission.FINALIZE not in perms
        assert Permission.DELETE not in perms
        assert Permission.ADMIN not in perms

    def test_stagiaire_permissions(self):
        perms = ROLE_PERMISSIONS[Role.STAGIAIRE]
        assert Permission.READ in perms
        assert Permission.WRITE not in perms
        assert Permission.DRAFT not in perms
        assert Permission.FINALIZE not in perms
        assert Permission.DELETE not in perms
        assert Permission.ADMIN not in perms


class TestUserStore:
    """Test the file-based user store (with temp file)."""

    @pytest.fixture(autouse=True)
    def setup(self, monkeypatch):
        """Use a temp directory for user storage."""
        self.tmpdir = Path(tempfile.mkdtemp())
        monkeypatch.setattr("app.core.auth.USERS_DIR", self.tmpdir)
        monkeypatch.setattr("app.core.auth.USERS_FILE", self.tmpdir / "users.json")
        monkeypatch.setattr("app.core.auth.TOKENS_FILE", self.tmpdir / "tokens.json")

        # Use a known admin password for deterministic testing
        from app.core.config import settings as _rbac_settings
        monkeypatch.setattr(_rbac_settings, "ADMIN_PASSWORD", "TestPass789!")

        # Re-trigger default admin creation
        from app.core import auth
        auth._ensure_default_admin()
        yield

    def test_default_admin_created(self):
        from app.core.auth import list_users
        users = list_users()
        assert len(users) >= 1
        admin = [u for u in users if u.role == Role.ADMIN]
        assert len(admin) >= 1
        assert admin[0].username == "admin"

    def test_create_user(self):
        from app.core.auth import create_user, list_users
        user = create_user(UserCreate(
            username="testuser",
            email="test@test.com",
            password="test1234",
            role=Role.NOTAIRE,
            office="branch1",
            display_name="Test User",
        ))
        assert user.username == "testuser"
        assert user.role == Role.NOTAIRE
        assert user.office == "branch1"
        assert user.is_active is True

        users = list_users()
        assert len(users) >= 2  # admin + new user

    def test_create_duplicate_username(self):
        from app.core.auth import create_user
        create_user(UserCreate(
            username="unique", email="a@a.com", password="test1234", role=Role.STAGIAIRE,
        ))
        with pytest.raises(HTTPException) as exc:
            create_user(UserCreate(
                username="unique", email="b@b.com", password="test1234", role=Role.STAGIAIRE,
            ))
        assert exc.value.status_code == 409

    def test_authenticate_valid(self):
        from app.core.auth import authenticate_user, create_user
        create_user(UserCreate(
            username="authuser", email="auth@test.com", password="mypassword", role=Role.ASSISTANT,
        ))
        user = authenticate_user("authuser", "mypassword")
        assert user is not None
        assert user.username == "authuser"
        assert user.role == Role.ASSISTANT

    def test_authenticate_invalid_password(self):
        from app.core.auth import authenticate_user, create_user
        create_user(UserCreate(
            username="authfail", email="f@test.com", password="correctpassword", role=Role.STAGIAIRE,
        ))
        user = authenticate_user("authfail", "wrongpass")
        assert user is None

    def test_authenticate_inactive_user(self):
        from app.core.auth import authenticate_user, get_user_by_id, update_user
        from app.models.auth import UserUpdate
        create_user_data = UserCreate(
            username="inactiveuser", email="i@test.com", password="pass1234", role=Role.NOTAIRE,
        )
        from app.core.auth import create_user
        created = create_user(create_user_data)
        # Deactivate
        update_user(created.id, UserUpdate(is_active=False))
        user = authenticate_user("inactiveuser", "pass123")
        assert user is None

    def test_token_creation_and_validation(self):
        from app.core.auth import create_user, create_token, get_user_from_token
        created = create_user(UserCreate(
            username="tokenuser", email="t@t.com", password="pass1234", role=Role.ADMIN,
        ))
        token = create_token(created.id)
        assert token.startswith("lgt_")

        resolved = get_user_from_token(token)
        assert resolved is not None
        assert resolved.id == created.id

    def test_token_revocation(self):
        from app.core.auth import create_user, create_token, revoke_token, get_user_from_token
        created = create_user(UserCreate(
            username="revoketest", email="r@r.com", password="pass1234", role=Role.STAGIAIRE,
        ))
        token = create_token(created.id)
        revoke_token(token)
        resolved = get_user_from_token(token)
        assert resolved is None

    def test_delete_user_anonymizes(self):
        from app.core.auth import create_user, delete_user, get_user_by_id
        created = create_user(UserCreate(
            username="deleteuser", email="d@d.com", password="pass1234", role=Role.ASSISTANT,
        ))
        delete_user(created.id)
        deleted = get_user_by_id(created.id)
        assert deleted is not None
        assert deleted.username.startswith("deleted-")
        assert deleted.is_active is False
        assert deleted.role == Role.STAGIAIRE


class TestGDPR:
    """Test GDPR audit logging."""

    @pytest.fixture(autouse=True)
    def setup(self, monkeypatch):
        self.tmpdir = Path(tempfile.mkdtemp())
        monkeypatch.setattr("app.core.gdpr.AUDIT_DIR", self.tmpdir)
        monkeypatch.setattr("app.core.gdpr.AUDIT_FILE", self.tmpdir / "audit_trail.jsonl")
        yield

    def test_log_interaction(self):
        from app.core.gdpr import log_interaction, get_audit_trail
        auth = AuthContext(
            user_id="user1", username="testuser", role=Role.NOTAIRE,
            office="main", display_name="Test User", email="test@test.com",
        )
        entry_id = log_interaction(
            auth=auth,
            action=AuditAction.CREATE,
            resource_type="document",
            resource_id="doc_123",
            details="Uploaded contract.pdf",
        )
        assert entry_id is not None

        entries = get_audit_trail(user_id="user1")
        assert len(entries) >= 1
        assert entries[0].action == AuditAction.CREATE
        assert entries[0].resource_id == "doc_123"
        assert entries[0].username == "testuser"

    def test_audit_filter_by_case(self):
        from app.core.gdpr import log_interaction, get_audit_trail
        auth = AuthContext(
            user_id="user2", username="notaire1", role=Role.NOTAIRE,
            office="main", display_name="", email="",
        )
        log_interaction(auth, AuditAction.READ, resource_type="case", resource_id="case_001")
        log_interaction(auth, AuditAction.READ, resource_type="case", resource_id="case_002")
        log_interaction(auth, AuditAction.UPDATE, resource_type="case", resource_id="case_001")

        case_entries = get_audit_trail(case_id="case_001")
        assert len(case_entries) == 2
        for e in case_entries:
            assert e.resource_id == "case_001"

    def test_audit_filter_by_action(self):
        from app.core.gdpr import log_interaction, get_audit_trail
        auth = AuthContext(
            user_id="user3", username="admin", role=Role.ADMIN,
            office="main", display_name="", email="",
        )
        log_interaction(auth, AuditAction.LOGIN)
        log_interaction(auth, AuditAction.LOGOUT)
        log_interaction(auth, AuditAction.CREATE, resource_type="user")

        login_entries = get_audit_trail(action=AuditAction.LOGIN)
        assert len(login_entries) >= 1
        for e in login_entries:
            assert e.action == AuditAction.LOGIN


class TestRoutingProfiles:
    """Test the routing profile selection logic."""

    @pytest.fixture(autouse=True)
    def setup_env(self, monkeypatch):
        monkeypatch.setenv("VLLM_API_BASE", "http://localhost:8001/v1")
        monkeypatch.setenv("LITELLM_API_KEY", "sk-test-key-1234567890")
        yield

    def test_profiles_defined(self):
        from app.core.routing import ALL_PROFILES
        assert "reasoning" in ALL_PROFILES
        assert "structured" in ALL_PROFILES
        assert "fast" in ALL_PROFILES
        assert "cheap" in ALL_PROFILES
        assert "private" in ALL_PROFILES
        assert "french" in ALL_PROFILES
        assert "fallback" in ALL_PROFILES

    def test_auto_select_normal(self):
        from app.core.routing import auto_select_profile
        messages = [{"role": "user", "content": "Analyze this contract"}]
        profile = auto_select_profile(messages)
        assert profile == "structured"  # default for normal use

    def test_auto_select_private(self):
        from app.core.routing import auto_select_profile
        messages = [{"role": "user", "content": "Process this private document"}]
        profile = auto_select_profile(messages, sensitivity="private")
        assert profile == "private"

    def test_auto_select_french(self):
        from app.core.routing import auto_select_profile
        messages = [{"role": "user", "content": "Analysez ce contrat"}]
        profile = auto_select_profile(messages, language="fr")
        assert profile == "french"

    def test_auto_select_urgent(self):
        from app.core.routing import auto_select_profile
        messages = [{"role": "user", "content": "Quick task"}]
        profile = auto_select_profile(messages, urgent=True)
        assert profile == "fast"

    def test_auto_select_cheap(self):
        from app.core.routing import auto_select_profile
        messages = [{"role": "user", "content": "Simple classification"}]
        profile = auto_select_profile(messages, prefer_cheap=True)
        assert profile == "cheap"

    def test_get_profile_config(self):
        from app.core.routing import get_profile_config, ALL_PROFILES
        config = get_profile_config()
        assert "strategy" in config
        assert config["strategy"] == "auto"
        assert "profiles" in config
        assert "criteria" in config
        for profile in ALL_PROFILES:
            assert profile in config["profiles"], f"Profile '{profile}' missing from config"
            assert "description" in config["profiles"][profile]
            assert "available" in config["profiles"][profile]
