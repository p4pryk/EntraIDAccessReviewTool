import pytest
import requests


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    """Tests may use only the explicit loopback transport in test_integration."""

    def denied(*args, **kwargs):
        raise AssertionError("Unexpected network request")

    monkeypatch.setattr(requests.sessions.Session, "request", denied)
