from __future__ import annotations

import argparse
import re
from urllib.parse import parse_qs, urlparse

import httpx


class SmokeFailure(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def run(frontend_url: str, api_url: str) -> None:
    frontend_url = frontend_url.rstrip("/")
    api_url = api_url.rstrip("/")
    parsed_api = urlparse(api_url)
    api_origin = f"{parsed_api.scheme}://{parsed_api.netloc}"
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        frontend = client.get(f"{frontend_url}/")
        require(frontend.status_code == 200, f"frontend returned {frontend.status_code}")
        require("text/html" in frontend.headers.get("content-type", ""), "frontend is not HTML")
        csp = frontend.headers.get("content-security-policy", "")
        require(api_origin in csp, "CSP blocks API")
        has_inline_bootstrap = bool(re.search(r"<script(?:\s[^>]*)?>\s*[^<\s]", frontend.text))
        require(not has_inline_bootstrap or "'unsafe-inline'" in csp, "CSP blocks hydration")
        print("PASS frontend and security headers")

        health = client.get(f"{api_url}/health")
        require(health.status_code == 200, f"health returned {health.status_code}")
        require(health.json() == {"status": "ok"}, "health response is malformed")
        print("PASS API health")

        cors = client.options(
            f"{api_url}/watches",
            headers={
                "Origin": frontend_url,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-csrf-token",
            },
        )
        require(cors.status_code == 200, f"CORS preflight returned {cors.status_code}")
        require(cors.headers.get("access-control-allow-origin") == frontend_url, "CORS origin")
        require(cors.headers.get("access-control-allow-credentials") == "true", "CORS credentials")
        print("PASS credentialed CORS")

        protected = client.get(f"{api_url}/watches")
        require(
            protected.status_code == 401, f"unauthenticated route returned {protected.status_code}"
        )
        error = protected.json().get("error", {})
        require(error.get("code") == "AUTHENTICATION_REQUIRED", "unsafe auth error response")
        require(bool(error.get("correlation_id")), "auth error lacks correlation ID")
        print("PASS protected-route error boundary")

        login = client.get(f"{api_url}/auth/login")
        require(login.status_code == 307, f"login returned {login.status_code}")
        location = login.headers.get("location", "")
        query = parse_qs(urlparse(location).query)
        require(urlparse(location).scheme == "https", "login redirect is not HTTPS")
        require(query.get("response_type") == ["code"], "login is not authorization-code flow")
        require(query.get("code_challenge_method") == ["S256"], "login is not PKCE S256")
        cookies = login.headers.get_list("set-cookie")
        for name in ("direhire_oauth_state", "direhire_oidc_nonce", "direhire_pkce_verifier"):
            require(any(cookie.startswith(f"{name}=") for cookie in cookies), f"missing {name}")
        print("PASS Cognito authorization-code + PKCE start")


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only DireHire production smoke checks")
    parser.add_argument("--frontend-url", required=True)
    parser.add_argument("--api-url", required=True, help="Full API v1 URL")
    args = parser.parse_args()
    try:
        run(args.frontend_url, args.api_url)
    except (httpx.HTTPError, SmokeFailure, ValueError) as exc:
        raise SystemExit(f"FAIL {exc}") from exc


if __name__ == "__main__":
    main()
