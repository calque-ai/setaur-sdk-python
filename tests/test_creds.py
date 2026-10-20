import base64
import json
import pytest
from setaur._client import _Client
from setaur._creds import check_creds_file

FAKE_SEED = "SUAAFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKE"
NOW = 1_800_000_000


def make_jwt(claims: dict) -> str:
    def seg(obj: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")
    return f"{seg({'typ': 'JWT'})}.{seg(claims)}.c2ln"


FAKE_JWT = make_jwt({"fake": "true"})


def nats_creds(jwt: str = FAKE_JWT, extra: str = "") -> str:
    return (
        "-----BEGIN NATS USER JWT-----\n" + jwt + "\n------END NATS USER JWT------\n\n"
        "************************* IMPORTANT *************************\n"
        "NKEY Seed printed below can be used to sign and prove identity.\n\n"
        "-----BEGIN USER NKEY SEED-----\n" + FAKE_SEED + "\n------END USER NKEY SEED------\n\n"
        "*************************************************************\n" + extra
    )


CLOUD_CREDS = (
    "-----BEGIN USER JWT-----\nZXlK\n-----END USER JWT-----\n"
    "-----BEGIN USER NKEY SEED-----\nU1VB\n-----END USER NKEY SEED-----\n"
)
CLOUD_HINT = ["-cloud.creds", "-nats.creds", "robots and the SDK need"]
NO_CREDS = ["no credentials found", "-nats.creds"]


@pytest.mark.parametrize("data, want_err", [
    pytest.param(nats_creds(), None, id="valid nats file"),
    pytest.param(nats_creds().replace("\n", "\r\n"), None, id="valid nats file, CRLF"),
    pytest.param(nats_creds(extra="# BEGIN USER JWT\n"), None, id="valid nats file, cloud marker in comment"),

    pytest.param(CLOUD_CREDS, CLOUD_HINT, id="cloud file"),
    pytest.param(CLOUD_CREDS.replace("\n", "\r\n"), CLOUD_HINT, id="cloud file, CRLF"),

    pytest.param("", NO_CREDS, id="empty"),
    pytest.param("  \n\t\n", NO_CREDS, id="whitespace"),
    pytest.param("not a valid JWT file", NO_CREDS, id="unrelated text"),
    pytest.param("\x00\xff\xfe\x00\x01", NO_CREDS, id="NUL bytes"),
    pytest.param("A" * (1 << 20), NO_CREDS, id="1 MiB of junk"),
])
def test_check_creds_file(tmp_path, data, want_err):
    path = tmp_path / "rbt-abc-test.creds"
    path.write_bytes(data.encode("latin-1"))

    if want_err is None:
        check_creds_file(str(path), now=NOW)
        return

    with pytest.raises(ValueError) as exc:
        check_creds_file(str(path), now=NOW)
    msg = str(exc.value)
    assert str(path) in msg
    for want in want_err:
        assert want in msg
    for secret in (FAKE_JWT, FAKE_SEED):
        assert secret not in msg


@pytest.mark.parametrize("claims, want_err", [
    pytest.param({}, False, id="no exp claim"),
    pytest.param({"exp": 0}, False, id="exp zero"),
    pytest.param({"exp": -1}, False, id="negative exp ignored"),
    pytest.param({"exp": NOW + 10 * 365 * 86400}, False, id="far future"),
    pytest.param({"exp": NOW + 1}, False, id="expires in one second"),
    pytest.param({"exp": NOW}, False, id="expires exactly now is valid"),
    pytest.param({"exp": NOW - 1}, True, id="expired one second ago"),
    pytest.param({"exp": "soon"}, False, id="non-integer exp ignored"),
    pytest.param({"exp": True}, False, id="boolean exp ignored"),
])
def test_check_creds_file_expiry(tmp_path, claims, want_err):
    jwt = make_jwt(claims)
    path = tmp_path / "rbt-abc-nats.creds"
    path.write_text(nats_creds(jwt))

    if not want_err:
        check_creds_file(str(path), now=NOW)
        return

    with pytest.raises(ValueError, match="expired at") as exc:
        check_creds_file(str(path), now=NOW)
    assert "-nats.creds" in str(exc.value)
    assert jwt not in str(exc.value)
    assert FAKE_SEED not in str(exc.value)


@pytest.mark.parametrize("jwt", ["not-a-jwt", "a.b.c", "a.!!!.c", "a." + base64.urlsafe_b64encode(b"[1]").decode() + ".c", ""])
def test_unparseable_user_jwt_is_left_to_the_nats_client(tmp_path, jwt):
    path = tmp_path / "rbt-abc-nats.creds"
    path.write_text(nats_creds(jwt))
    check_creds_file(str(path), now=NOW)


def test_truncated_nats_file_does_not_raise(tmp_path):
    path = tmp_path / "rbt-abc-nats.creds"
    path.write_text("-----BEGIN NATS USER JWT-----")
    check_creds_file(str(path), now=NOW)


# --- wired into _Client ------------------------------------------------------

class _FakeNats:
    async def publish(self, subject: str, payload: bytes) -> None: ...
    async def close(self) -> None: ...


async def _connector(url, credentials):
    return _FakeNats()


def test_client_rejects_cloud_creds_before_connecting(tmp_path):
    path = tmp_path / "rbt-abc-cloud.creds"
    path.write_text(CLOUD_CREDS)

    async def must_not_connect(url, credentials):
        raise AssertionError("connector called")

    with pytest.raises(ValueError, match="edge-to-cloud credentials file"):
        _Client("rbt-test000001", creds_file=str(path), connector=must_not_connect)


def test_client_rejects_cloud_creds_from_env_var(tmp_path, monkeypatch):
    path = tmp_path / "rbt-abc-cloud.creds"
    path.write_text(CLOUD_CREDS)
    monkeypatch.setenv("SETAUR_CREDS_FILE", str(path))

    with pytest.raises(ValueError, match="-nats.creds"):
        _Client("rbt-test000001", creds_file=None, connector=_connector)


def test_client_accepts_valid_nats_creds(tmp_path):
    path = tmp_path / "rbt-abc-nats.creds"
    path.write_text(nats_creds())

    client = _Client("rbt-test000001", creds_file=str(path), connector=_connector)
    client.close()
