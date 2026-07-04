"""httpx client for the private session + verify API.

D6 discipline: every failure here is an INFRA fault (our problem), never a
policy failure. Callers must let InfraFault propagate — in the packaged
environment it is re-raised as vf.Error so prime-rl drops the rollout instead
of scoring 0.0. Never log the verify key.
"""

import httpx


class InfraFault(Exception):
    """Infrastructure failure — raise, never score (D6)."""


def _headers(verify_key: str) -> dict:
    return {"Authorization": f"Bearer {verify_key}"}


def mint_sid(store_url: str, verify_key: str, timeout: float = 15.0) -> str:
    try:
        r = httpx.post(
            f"{store_url.rstrip('/')}/api/sessions",
            headers=_headers(verify_key),
            timeout=timeout,
        )
    except httpx.HTTPError as e:
        raise InfraFault(f"session mint failed: {type(e).__name__}") from e
    if r.status_code != 200:
        raise InfraFault(f"session mint failed: HTTP {r.status_code}")
    sid = r.json().get("sid")
    if not sid:
        raise InfraFault("session mint returned no sid")
    return sid


def fetch_verify(store_url: str, verify_key: str, sid: str, timeout: float = 15.0) -> dict:
    try:
        r = httpx.get(
            f"{store_url.rstrip('/')}/api/verify/{sid}",
            headers=_headers(verify_key),
            timeout=timeout,
        )
    except httpx.HTTPError as e:
        raise InfraFault(f"verify fetch failed: {type(e).__name__}") from e
    if r.status_code == 404:
        # unknown/expired sid — infra fault per spec (never a 0.0)
        raise InfraFault("verify 404: unknown or expired sid")
    if r.status_code != 200:
        raise InfraFault(f"verify fetch failed: HTTP {r.status_code}")
    return r.json()
