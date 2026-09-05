from tests.conftest import register


def test_register_login_refresh_logout(client):
    headers, tokens = register(client)

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "a@example.com"

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "Sup3rSecret!pw"},
    )
    assert login.status_code == 200

    refreshed = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refreshed.status_code == 200
    new_tokens = refreshed.json()

    # The old refresh token was rotated and must no longer work.
    replay = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert replay.status_code == 401

    out = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": new_tokens["refresh_token"]},
        headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
    )
    assert out.status_code == 204


def test_duplicate_email_rejected(client):
    register(client)
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "An0therPass!x"},
    )
    assert r.status_code == 409


def test_weak_password_rejected(client):
    r = client.post(
        "/api/v1/auth/register", json={"email": "b@example.com", "password": "short"}
    )
    assert r.status_code == 422


def test_wrong_password_rejected(client):
    register(client)
    r = client.post(
        "/api/v1/auth/login", json={"email": "a@example.com", "password": "wrongpassword1!"}
    )
    assert r.status_code == 401


def test_password_reset_flow(client):
    register(client)
    forgot = client.post("/api/v1/auth/forgot-password", json={"email": "a@example.com"})
    assert forgot.status_code == 200
    token = forgot.json()["dev_reset_token"]

    reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "Br4ndNewPass!"},
    )
    assert reset.status_code == 204

    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "a@example.com", "password": "Br4ndNewPass!"}
        ).status_code
        == 200
    )
    # The token is single use.
    assert (
        client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "Y3tAnother!pw"},
        ).status_code
        == 400
    )


def test_forgot_password_does_not_leak_account_existence(client):
    r = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})
    assert r.status_code == 200
    assert "dev_reset_token" not in r.json()


def test_endpoints_require_auth(client):
    for path in [
        "/api/v1/dashboard",
        "/api/v1/transactions",
        "/api/v1/debts",
        "/api/v1/savings/goals",
        "/api/v1/investments/holdings",
        "/api/v1/profile",
    ]:
        assert client.get(path).status_code == 401, path
