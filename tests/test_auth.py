from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from xora_chart import auth
from xora_chart.auth import AuthError, UserStore, hash_password, verify_password


@pytest.fixture()
def users(tmp_path, monkeypatch):
    monkeypatch.setenv("XORA_USERS_FILE", str(tmp_path / "users.json"))
    monkeypatch.setenv("XORA_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("XORA_ADMIN_PASSWORD", "correct horse")
    monkeypatch.setattr(UserStore, "_instance", None)
    return UserStore.instance()


def test_password_hash_roundtrip_and_salting():
    a, b = hash_password("s3cret-pass"), hash_password("s3cret-pass")
    assert a != b
    assert verify_password("s3cret-pass", a)
    assert not verify_password("wrong-pass", a)
    assert not verify_password("anything", "garbage")


def test_admin_bootstrap_login_and_resume(users, tmp_path):
    token, user = users.login("ADMIN", "correct horse")
    assert user["role"] == "admin"
    assert users.resume(token)["username"] == "admin"
    # Sessions survive a restart; the raw token is never written to disk.
    assert token not in (tmp_path / "users.json").read_text()
    reloaded = UserStore(tmp_path / "users.json")
    assert reloaded.resume(token)["username"] == "admin"
    users.logout(token)
    with pytest.raises(AuthError):
        users.resume(token)


def test_lockout_after_repeated_failures(users):
    for _ in range(auth.MAX_FAILED_LOGINS):
        with pytest.raises(AuthError, match="Invalid"):
            users.login("admin", "nope-nope")
    with pytest.raises(AuthError, match="Too many"):
        users.login("admin", "correct horse")


def test_password_change_revokes_other_sessions(users):
    t1, _ = users.login("admin", "correct horse")
    t2, _ = users.login("admin", "correct horse")
    with pytest.raises(AuthError):
        users.change_password("admin", "bad-current", "new-password-1", token=t1)
    users.change_password("admin", "correct horse", "new-password-1", token=t1)
    assert users.resume(t1)
    with pytest.raises(AuthError):
        users.resume(t2)
    users.login("admin", "new-password-1")


def test_user_admin_rules(users):
    users.create_user("trader1", "trader-pass", "user")
    with pytest.raises(AuthError, match="exists"):
        users.create_user("Trader1", "trader-pass")
    with pytest.raises(AuthError, match="at least"):
        users.create_user("trader2", "short")
    with pytest.raises(AuthError, match="own account"):
        users.delete_user("admin", acting="admin")
    users.delete_user("trader1", acting="admin")
    assert [u["username"] for u in users.list_users()] == ["admin"]


def test_websocket_requires_login_and_admin_role(users):
    from xora_chart.main import app

    client = TestClient(app)  # no lifespan: the Binance hub is not started
    users.create_user("viewer", "viewer-pass", "user")
    with client.websocket_connect("/ws") as ws:
        ready = ws.receive_json()
        assert ready["data"] == {"status": "ok", "service": "xora-chart-ai", "auth_required": True}

        ws.send_json({"id": "1", "action": "positions.summary", "payload": {}})
        r = ws.receive_json()
        assert not r["ok"] and r["auth_error"]

        ws.send_json({"id": "2", "action": "auth.login", "payload": {"username": "viewer", "password": "viewer-pass"}})
        assert ws.receive_json()["ok"]

        ws.send_json({"id": "3", "action": "users.list", "payload": {}})
        r = ws.receive_json()
        assert not r["ok"] and "Admin" in r["error"]

        ws.send_json({"id": "4", "action": "positions.summary", "payload": {}})
        assert ws.receive_json()["ok"]
