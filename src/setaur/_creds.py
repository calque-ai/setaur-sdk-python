import base64
import json
import time
from datetime import datetime, timezone

_NATS_MARKER = b"BEGIN NATS USER JWT"
_CLOUD_MARKER = b"BEGIN USER JWT"


def check_creds_file(path: str, now: float | None = None) -> None:
    with open(path, "rb") as f:
        raw = f.read()

    # The NATS header ("BEGIN NATS USER JWT") does not contain the cloud marker, and it wins
    # so a stray marker in a comment of a robot file is not grounds for rejection.
    if _NATS_MARKER not in raw:
        if _CLOUD_MARKER in raw:
            raise ValueError(
                f"setaur: {path} is the edge-to-cloud credentials file (<robotKey>-cloud.creds), "
                "which setaur-edge uses to connect to the cloud; "
                "robots and the SDK need <robotKey>-nats.creds"
            )
        raise ValueError(
            f"setaur: no credentials found in {path}; "
            "robots and the SDK need the robot credentials file (<robotKey>-nats.creds)"
        )

    expires = _user_jwt_expiry(raw)
    if expires is not None and expires > 0 and (time.time() if now is None else now) > expires:
        when = datetime.fromtimestamp(expires, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        raise ValueError(
            f"setaur: credentials in {path} expired at {when}; download a new <robotKey>-nats.creds"
        )


def _user_jwt_expiry(raw: bytes) -> int | None:
    # Unparseable JWTs are left for the nats client to reject; only a readable `exp` claim is enforced.
    try:
        after = raw.split(_NATS_MARKER, 1)[1].split(b"\n", 1)[1]
        token = after.split()[0].decode("ascii")
        payload = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        exp = claims.get("exp")
    except (IndexError, ValueError, AttributeError, UnicodeDecodeError):
        return None
    return exp if isinstance(exp, int) and not isinstance(exp, bool) else None
