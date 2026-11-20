from __future__ import annotations

import queue
import select
import socket
import threading

from . import crypto, protocol


class AuthError(Exception):
    pass


class Link:
    def __init__(self, sock: socket.socket, key: bytes, peer_screen: tuple[int, int]) -> None:
        self._sock = sock
        self._key = key
        self.peer_screen = peer_screen
        self._buffer = bytearray()
        self._incoming: queue.Queue[tuple[str, dict] | None] = queue.Queue()
        self._send_lock = threading.Lock()
        self._closed = threading.Event()
        self._dead = threading.Event()
        self._receiver = threading.Thread(target=self._receive_loop, daemon=True)
        self._receiver.start()

    @classmethod
    def connect(
        cls,
        host: str,
        port: int,
        secret: str,
        my_screen: tuple[int, int],
        timeout: float = 5.0,
    ) -> "Link":
        sock = socket.create_connection((host, port), timeout=timeout)
        try:
            kind, data = cls._recv_plain(sock)
            if kind != protocol.HELLO:
                raise AuthError("expected hello")
            salt = bytes.fromhex(data["salt"])
            peer_screen = tuple(data["screen"])
            key = crypto.derive_key(secret, salt)
            probe = crypto.make_probe(key)
            cls._send_plain(
                sock,
                protocol.AUTH,
                {"probe": probe.hex(), "screen": list(my_screen)},
            )
            kind, data = cls._recv_plain(sock)
            if kind == protocol.AUTH_FAIL:
                raise AuthError("wrong secret")
            if kind != protocol.AUTH_OK:
                raise AuthError("expected auth_ok")
            return cls(sock, key, tuple(data["screen"]))
        except Exception:
            sock.close()
            raise

    @classmethod
    def accept(cls, sock: socket.socket, secret: str, my_screen: tuple[int, int]) -> "Link":
        salt = crypto.new_salt()
        cls._send_plain(
            sock, protocol.HELLO, {"salt": salt.hex(), "screen": list(my_screen)}
        )
        kind, data = cls._recv_plain(sock)
        if kind != protocol.AUTH:
            raise AuthError("expected auth")
        key = crypto.derive_key(secret, salt)
        if not crypto.verify_probe(key, bytes.fromhex(data["probe"])):
            cls._send_plain(sock, protocol.AUTH_FAIL, {})
            sock.close()
            raise AuthError("wrong secret")
        peer_screen = tuple(data["screen"])
        cls._send_plain(
            sock, protocol.AUTH_OK, {"screen": list(my_screen)}
        )
        return cls(sock, key, peer_screen)

    def send(self, kind: str, data: dict | None = None) -> None:
        if self._closed.is_set():
            raise ConnectionError("link closed")
        payload = protocol.encode(kind, data)
        blob = crypto.seal(self._key, payload)
        with self._send_lock:
            self._sock.sendall(protocol.frame(blob))

    def recv(self, timeout: float | None = None) -> tuple[str, dict] | None:
        try:
            return self._incoming.get(timeout=timeout)
        except queue.Empty:
            return None

    @property
    def alive(self) -> bool:
        return not self._dead.is_set()

    def close(self) -> None:
        if self._closed.is_set():
            return
        self._closed.set()
        self._dead.set()
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self._sock.close()
        self._incoming.put(None)

    def _receive_loop(self) -> None:
        try:
            while not self._closed.is_set():
                ready, _, _ = select.select([self._sock], [], [], 0.5)
                if not ready:
                    continue
                chunk = self._sock.recv(65536)
                if not chunk:
                    break
                self._buffer.extend(chunk)
                while True:
                    blob = protocol.unframe(self._buffer)
                    if blob is None:
                        break
                    payload = crypto.open_sealed(self._key, blob)
                    body = protocol.unframe(bytearray(payload))
                    if body is None:
                        continue
                    kind, data = protocol.decode(body)
                    self._incoming.put((kind, data))
        except Exception:
            pass
        finally:
            self._dead.set()
            if not self._closed.is_set():
                self._incoming.put(None)

    @staticmethod
    def _recv_plain(sock: socket.socket) -> tuple[str, dict]:
        buffer = bytearray()
        while True:
            payload = protocol.unframe(buffer)
            if payload is not None:
                return protocol.decode(payload)
            chunk = sock.recv(65536)
            if not chunk:
                raise AuthError("peer closed during handshake")
            buffer.extend(chunk)

    @staticmethod
    def _send_plain(sock: socket.socket, kind: str, data: dict) -> None:
        sock.sendall(protocol.encode(kind, data))


def serve_once(
    port: int,
    secret: str,
    my_screen: tuple[int, int],
    on_link,
    should_stop=None,
    timeout: float = 0.5,
) -> None:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("0.0.0.0", port))
    listener.listen(1)
    listener.settimeout(timeout)
    try:
        while True:
            if should_stop and should_stop():
                return
            try:
                sock, _ = listener.accept()
            except socket.timeout:
                continue
            try:
                link = Link.accept(sock, secret, my_screen)
            except (AuthError, OSError, ValueError, KeyError, TypeError):
                sock.close()
                continue
            try:
                on_link(link)
            finally:
                link.close()
    finally:
        listener.close()
