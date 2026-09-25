from fastapi.testclient import TestClient

from src.config import Settings
from tests.conftest import TEST_PASSWORD, TEST_USERNAME

LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/auth/me"
LOGOUT_URL = "/api/v1/auth/logout"
VALID_CREDENTIALS = {"username": TEST_USERNAME, "password": TEST_PASSWORD}
WRONG_CREDENTIALS = {"username": TEST_USERNAME, "password": "wrong-password"}


def test_login_with_correct_credentials_sets_http_only_session_cookie(
    client: TestClient, test_settings: Settings
) -> None:
    response = client.post(LOGIN_URL, json=VALID_CREDENTIALS)

    assert response.status_code == 200
    set_cookie = response.headers["set-cookie"]
    assert set_cookie.startswith("cn_session=")
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Path=/" in set_cookie
    assert f"Max-Age={test_settings.jwt_expires_seconds}" in set_cookie
    assert "Secure" not in set_cookie
    assert response.headers["X-RateLimit-Limit"] == str(test_settings.login_max_attempts)
    assert response.headers["X-RateLimit-Remaining"] == str(test_settings.login_max_attempts)
    assert response.cookies["cn_session"] not in response.text


def test_login_with_wrong_credentials_returns_generic_401(client: TestClient) -> None:
    response = client.post(LOGIN_URL, json=WRONG_CREDENTIALS)

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid username or password"}
    assert "set-cookie" not in response.headers
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers


def test_too_many_failures_from_one_ip_returns_429_even_with_correct_credentials(
    client: TestClient, test_settings: Settings
) -> None:
    headers = {"X-Real-IP": "203.0.113.7"}
    for _ in range(test_settings.login_max_attempts):
        assert client.post(LOGIN_URL, json=WRONG_CREDENTIALS, headers=headers).status_code == 401

    response = client.post(LOGIN_URL, json=VALID_CREDENTIALS, headers=headers)

    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0
    assert response.headers["X-RateLimit-Remaining"] == "0"
    assert "set-cookie" not in response.headers
    other_ip = client.post(LOGIN_URL, json=VALID_CREDENTIALS, headers={"X-Real-IP": "198.51.100.1"})
    assert other_ip.status_code == 200


def test_me_requires_a_valid_session_cookie(client: TestClient) -> None:
    assert client.get(ME_URL).status_code == 401
    client.cookies.set("cn_session", "not-a-jwt")
    assert client.get(ME_URL).json() == {"detail": "Not authenticated"}
    client.cookies.clear()

    client.post(LOGIN_URL, json=VALID_CREDENTIALS)
    response = client.get(ME_URL)

    assert response.status_code == 200
    assert response.json() == {
        "username": TEST_USERNAME,
        "first_name": "Ada",
        "last_name": "Lovelace",
        "initials": "AL",
        "email": "ada@example.com",
    }


def test_logout_returns_204_and_expires_the_session_cookie(client: TestClient) -> None:
    client.post(LOGIN_URL, json=VALID_CREDENTIALS)

    response = client.post(LOGOUT_URL)

    assert response.status_code == 204
    set_cookie = response.headers["set-cookie"]
    assert set_cookie.startswith("cn_session=")
    assert "Max-Age=0" in set_cookie
    assert "Path=/" in set_cookie
    assert client.get(ME_URL).status_code == 401


def test_successful_login_resets_the_failure_count_for_that_ip(
    client: TestClient, test_settings: Settings
) -> None:
    headers = {"X-Real-IP": "203.0.113.9"}
    for _ in range(test_settings.login_max_attempts - 1):
        client.post(LOGIN_URL, json=WRONG_CREDENTIALS, headers=headers)

    assert client.post(LOGIN_URL, json=VALID_CREDENTIALS, headers=headers).status_code == 200

    response = client.post(LOGIN_URL, json=WRONG_CREDENTIALS, headers=headers)
    assert response.status_code == 401
    assert response.headers["X-RateLimit-Remaining"] == str(test_settings.login_max_attempts - 1)
