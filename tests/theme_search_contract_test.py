import http.client
import io
import json
import socket
from threading import Event, Thread

import pytest
from django.urls import reverse

from django_resume.formats.json_resume import themes
from django_resume.models import Resume


@pytest.fixture
def registry(monkeypatch):
    connections = []
    monkeypatch.setattr(themes, "getproxies", lambda: {})

    def serve(body, *, step=0):
        clock = [0.0]
        monkeypatch.setattr(themes, "monotonic", lambda: clock[0])

        class Response(io.BytesIO):
            status = 200

            def read1(self, amount):
                clock[0] += step
                return super().read1(min(amount, 1) if step else amount)

        class Connection:
            sock = None

            def __init__(self, *args, **kwargs):
                self.response = Response(body)
                self.closed = False
                self.request_args = None
                connections.append(self)

            def connect(self):
                pass

            def request(self, *args, **kwargs):
                self.request_args = args

            def getresponse(self):
                return self.response

            def close(self):
                self.closed = True

        monkeypatch.setattr(themes, "HTTPSConnection", Connection, raising=False)
        return connections, clock

    return serve


def test_registry_search_stops_at_byte_budget(registry, monkeypatch):
    monkeypatch.setattr(themes, "THEME_SEARCH_MAX_BYTES", 32, raising=False)
    connections, _ = registry(b" " * 33 + b'{"objects":[]}')
    with pytest.raises(themes.JsonResumeThemeError, match="maximum size"):
        themes.search_themes()
    assert connections[0].closed
    assert connections[0].response.closed


def test_registry_search_stops_dripping_body(registry):
    connections, clock = registry(b'{"objects":[]}', step=2)
    with pytest.raises(themes.JsonResumeThemeError, match="deadline"):
        themes.search_themes(timeout=5)
    assert clock[0] == 6
    assert connections[0].closed


def test_registry_search_exact_limit_and_filter(registry, monkeypatch):
    body = json.dumps(
        {
            "objects": [
                {"package": {"name": "jsonresume-theme-even"}},
                {"package": {"name": "not-a-theme"}},
            ]
        }
    ).encode()
    monkeypatch.setattr(themes, "THEME_SEARCH_MAX_BYTES", len(body), raising=False)
    connections, _ = registry(body)
    assert [item.name for item in themes.search_themes("even", size=999)] == [
        "jsonresume-theme-even"
    ]
    assert "keywords%3Ajsonresume-theme" in connections[0].request_args[1]
    assert "size=250" in connections[0].request_args[1]


@pytest.mark.parametrize(
    "body",
    [
        b"[]",
        b"null",
        b'{"objects":null}',
        b'{"objects":{}}',
        b'{"objects":[null]}',
        b'{"objects":[{"package":[]}]}',
        b'{"objects":[{"package":null}]}',
        b"\xff",
        b"[" * 2000 + b"]" * 2000,
    ],
)
@pytest.mark.django_db
def test_invalid_registry_response_uses_selector_error(
    body, registry, settings, client, user
):
    registry(body)
    settings.DJANGO_RESUME_JSON_RESUME_ALLOW_DYNAMIC_THEME_INSTALL = True
    user.save()
    resume = Resume.objects.create(name="Synthetic", slug="synthetic", owner=user)
    client.force_login(user)
    response = client.get(
        reverse("django_resume:json-resume-themes", kwargs={"slug": resume.slug})
    )
    assert response.status_code == 200
    assert "npm registry returned invalid" in response.content.decode()


@pytest.mark.parametrize("headers", [True, False])
def test_deadline_interrupts_dripping_http(monkeypatch, headers):
    monkeypatch.setattr(themes, "getproxies", lambda: {})
    reader, writer = socket.socketpair()
    writer.sendall(
        b"HTTP/1.1 200 OK\r\nX-Slow: "
        if headers
        else b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n1;slow="
    )
    stopped = Event()

    def drip():
        while not stopped.wait(0.005):
            try:
                writer.sendall(b"x")
            except OSError:
                break

    worker = Thread(target=drip)
    worker.start()

    class Connection:
        sock = reader
        closed = False

        def __init__(self, *args, **kwargs):
            pass

        def connect(self):
            pass

        def request(self, *args, **kwargs):
            pass

        def getresponse(self):
            response = http.client.HTTPResponse(reader)
            response.begin()
            return response

        def close(self):
            reader.close()
            self.closed = True

    connection = Connection()
    monkeypatch.setattr(themes, "HTTPSConnection", lambda *args, **kwargs: connection)
    try:
        with pytest.raises(themes.JsonResumeThemeError, match="deadline"):
            themes.search_themes(timeout=0.15)
        assert connection.closed
    finally:
        stopped.set()
        worker.join(timeout=1)
        writer.close()
        reader.close()


def test_registry_proxy_connection_preserves_tunnel_auth(monkeypatch):
    calls = []

    class Connection:
        def __init__(self, *args, **kwargs):
            calls.append((args, kwargs))

        def set_tunnel(self, *args, **kwargs):
            calls.append((args, kwargs))

    monkeypatch.setattr(themes, "HTTPSConnection", Connection)
    monkeypatch.setattr(
        themes, "getproxies", lambda: {"https": "http://user:pass@proxy.example:8080"}
    )
    monkeypatch.setattr(themes, "proxy_bypass", lambda host: False)
    themes._registry_connection("registry.npmjs.org", timeout=8)
    assert calls == [
        (("proxy.example", 8080), {"timeout": 8}),
        (
            ("registry.npmjs.org",),
            {"port": 443, "headers": {"Proxy-Authorization": "Basic dXNlcjpwYXNz"}},
        ),
    ]
    calls.clear()
    monkeypatch.setattr(themes, "proxy_bypass", lambda host: True)
    themes._registry_connection("registry.npmjs.org", timeout=8)
    assert calls == [(("registry.npmjs.org",), {"timeout": 8})]


@pytest.mark.parametrize(
    "proxy",
    [
        "proxy.example:abc",
        "http://proxy.example:99999",
        "http://bad host",
        "https://proxy.example",
    ],
)
def test_invalid_proxy_is_domain_error(monkeypatch, proxy):
    monkeypatch.setattr(themes, "getproxies", lambda: {"https": proxy})
    monkeypatch.setattr(themes, "proxy_bypass", lambda host: False)
    with pytest.raises(themes.JsonResumeThemeError, match="unsupported HTTPS proxy"):
        themes.search_themes()
