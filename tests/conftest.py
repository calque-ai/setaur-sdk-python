import pytest
import setaur._client as _client_module


@pytest.fixture(autouse=True)
def reset_client():
    """Ensure the module-level singleton is clean before and after every test."""
    _client_module._instance = None
    yield
    if _client_module._instance is not None:
        _client_module._instance.close()
    _client_module._instance = None
