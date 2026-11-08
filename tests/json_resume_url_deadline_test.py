import http.client
import io
import socket
import time
import ssl
from threading import Event, Thread
from types import SimpleNamespace

import pytest

from django_resume.formats.json_resume import importer


@pytest.mark.parametrize("redirect_seconds,chunk_seconds", [(0, 5), (10, 2)])
def test_dripping_body_shares_deadline_across_redirects(
    monkeypatch, redirect_seconds, chunk_seconds
):
    clock = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    connections = []

    class Response:
        headers = {}

        def __init__(self, status):
            self.status = status
            self.body = io.BytesIO(b'{"basics":{"name":"Jane"}}')

        def close(self):
            pass

        def getheader(self, name):
            return "/next"

        def read1(self, amount):
            clock[0] += chunk_seconds
            return self.body.read(1)

        def read(self, amount):
            # The old unbounded read completes the same valid document.
            clock[0] += chunk_seconds * len(self.body.getvalue())
            return self.body.read(amount)

    class Connection:
        sock = None
        closed = False

        def __init__(self, status):
            self.response = Response(status)

        def connect(self):
            pass

        def request(self, *args, **kwargs):
            pass

        def getresponse(self):
            if self.response.status == 302:
                clock[0] += redirect_seconds
            return self.response

        def close(self):
            self.closed = True

    def connection(url):
        conn = Connection(302 if redirect_seconds and not connections else 200)
        connections.append(conn)
        return conn

    monkeypatch.setattr(
        importer,
        "_validate_import_url",
        lambda url: SimpleNamespace(
            url=url, request_target="/resume", host_header="example.com"
        ),
    )
    monkeypatch.setattr(importer, "_connection_for_url", connection)
    with pytest.raises(
        importer.JsonResumeImportError, match="Could not read.*deadline"
    ) as exc:
        importer.load_document_url("https://example.com/resume")
    assert exc.value.field == "source_url"
    assert 15 <= clock[0] < 15 + chunk_seconds
    assert all(conn.closed for conn in connections)


def test_deadline_interrupts_blocked_response_headers(monkeypatch):
    reader, writer = socket.socketpair()
    writer.sendall(b"HTTP/1.1 200 OK\r\nX-Slow: ")
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
    monkeypatch.setattr(importer, "URL_FETCH_TOTAL_SECONDS", 0.15)
    monkeypatch.setattr(
        importer,
        "_validate_import_url",
        lambda url: SimpleNamespace(
            url=url, request_target="/resume", host_header="example.com"
        ),
    )
    monkeypatch.setattr(importer, "_connection_for_url", lambda url: connection)
    try:
        with pytest.raises(
            importer.JsonResumeImportError, match="Could not read.*deadline"
        ):
            importer.load_document_url("https://example.com/resume")
        assert connection.closed
    finally:
        stopped.set()
        worker.join(timeout=1)
        writer.close()
        reader.close()


def test_deadline_shutdown_preserves_ssl_object():
    reader, writer = socket.socketpair()
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    wrapped = context.wrap_socket(
        reader, server_hostname="example.com", do_handshake_on_connect=False
    )
    expired = Event()
    original_ssl = wrapped._sslobj
    try:
        importer._interrupt_fetch(wrapped, expired)
        assert expired.is_set()
        assert wrapped._sslobj is original_ssl
    finally:
        wrapped.close()
        writer.close()


def test_https_handshake_uses_remaining_connect_budget(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    timeouts = []

    class Socket:
        def setsockopt(self, *args):
            pass

        def settimeout(self, timeout):
            timeouts.append(timeout)

        def close(self):
            pass

    sock = Socket()

    def connect(*args):
        clock[0] += 8
        return sock

    monkeypatch.setattr(importer.socket, "create_connection", connect)
    connection = importer._PinnedHTTPSConnection("example.com", 443, "8.8.8.8")
    connection._ssl_context = SimpleNamespace(wrap_socket=lambda *args, **kwargs: sock)
    connection.connect()
    assert timeouts == [2]


def test_streamed_url_body_stops_at_size_limit(monkeypatch):
    read_sizes = []
    received = [0]

    class Response:
        status = 200
        headers = {}

        def read1(self, amount):
            read_sizes.append(amount)
            assert 0 < amount <= importer.MAX_INPUT_BYTES + 1 - received[0]
            chunk = b"x" * amount
            received[0] += len(chunk)
            return chunk

        def close(self):
            pass

    response = Response()

    class Connection:
        sock = None

        def connect(self):
            pass

        def request(self, *args, **kwargs):
            pass

        def getresponse(self):
            return response

        def close(self):
            pass

    monkeypatch.setattr(
        importer,
        "_validate_import_url",
        lambda url: SimpleNamespace(
            url=url, request_target="/resume", host_header="example.com"
        ),
    )
    monkeypatch.setattr(importer, "_connection_for_url", lambda url: Connection())
    with pytest.raises(importer.JsonResumeImportError, match="maximum size") as exc:
        importer.load_document_url("https://example.com/resume")
    assert exc.value.field == "source_url"
    assert received[0] == importer.MAX_INPUT_BYTES + 1
    assert max(read_sizes) <= 64 * 1024


@pytest.mark.parametrize(
    "protocol,headers",
    [
        ("HTTP/1.0", b"Content-Length: 26\r\n"),
        ("HTTP/1.1", b"Connection: close\r\nContent-Length: 26\r\n"),
        ("HTTP/1.1", b"Connection: close\r\nTransfer-Encoding: chunked\r\n"),
    ],
)
def test_close_response_preserves_complete_body(monkeypatch, protocol, headers):
    reader, writer = socket.socketpair()
    body = b'{"basics":{"name":"Jane"}}'
    if b"chunked" in headers:
        wire_body = b"%x\r\n" % len(body) + body + b"\r\n0\r\n\r\n"
    else:
        wire_body = body
    writer.sendall(protocol.encode() + b" 200 OK\r\n" + headers + b"\r\n" + wire_body)
    writer.shutdown(socket.SHUT_WR)
    connection = http.client.HTTPConnection("example.com")
    monkeypatch.setattr(
        connection, "connect", lambda: setattr(connection, "sock", reader)
    )
    monkeypatch.setattr(
        importer,
        "_validate_import_url",
        lambda url: SimpleNamespace(
            url=url, request_target="/resume", host_header="example.com"
        ),
    )
    monkeypatch.setattr(importer, "_connection_for_url", lambda url: connection)
    try:
        assert importer.load_document_url("https://example.com/resume") == {
            "basics": {"name": "Jane"}
        }
        assert reader.fileno() == -1
    finally:
        connection.close()
        reader.close()
        writer.close()


def test_body_oserror_is_not_treated_as_eof(monkeypatch):
    class Response:
        status = 200
        headers = {}
        calls = 0

        def read1(self, amount):
            self.calls += 1
            if self.calls == 1:
                # A valid JSON prefix must not make a failed transport succeed.
                return b'{"basics":{"name":"Jane"}}'
            raise OSError("body transport failed")

        def close(self):
            pass

    response = Response()
    connection = SimpleNamespace(
        sock=None,
        connect=lambda: None,
        request=lambda *a, **kw: None,
        getresponse=lambda: response,
        close=lambda: None,
    )
    monkeypatch.setattr(
        importer,
        "_validate_import_url",
        lambda url: SimpleNamespace(
            url=url, request_target="/resume", host_header="example.com"
        ),
    )
    monkeypatch.setattr(importer, "_connection_for_url", lambda url: connection)
    with pytest.raises(importer.JsonResumeImportError, match="body transport failed"):
        importer.load_document_url("https://example.com/resume")
