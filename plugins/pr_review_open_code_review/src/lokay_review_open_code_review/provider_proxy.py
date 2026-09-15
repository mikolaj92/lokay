"""Loopback CONNECT proxy that only tunnels the exact configured provider."""

from __future__ import annotations

import select
import socket
import threading


class ProviderProxy:
    """One CONNECT-only loopback proxy pinned to a single host:port authority."""

    _MAX_HEADER = 8192

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        authority_host = f"[{host}]" if ":" in host else host
        self._authority = f"{authority_host}:{port}".encode()
        self._listener = socket.socket()
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen(4)
        self._listener.settimeout(0.2)
        self._stopping = threading.Event()
        self._slots = threading.BoundedSemaphore(4)
        self._clients: set[threading.Thread] = set()
        self._clients_lock = threading.Lock()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self.port = int(self._listener.getsockname()[1])
        self._thread.start()

    def _reject(self, client: socket.socket, status: str) -> None:
        try:
            client.sendall(f"HTTP/1.1 {status}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".encode())
        finally:
            client.close()

    def _relay(self, client: socket.socket, upstream: socket.socket) -> None:
        sockets = [client, upstream]
        try:
            while not self._stopping.is_set():
                readable, _, _ = select.select(sockets, [], [], 0.2)
                for source in readable:
                    target = upstream if source is client else client
                    data = source.recv(65536)
                    if not data:
                        return
                    target.sendall(data)
        except OSError:
            return
        finally:
            for item in sockets:
                try:
                    item.close()
                except OSError:
                    pass

    def _handle(self, client: socket.socket) -> None:
        client.settimeout(5)
        try:
            header = bytearray()
            while b"\r\n\r\n" not in header and len(header) <= self._MAX_HEADER:
                chunk = client.recv(4096)
                if not chunk:
                    return self._reject(client, "400 Bad Request")
                header.extend(chunk)
            if len(header) > self._MAX_HEADER:
                return self._reject(client, "400 Bad Request")
            request = bytes(header).split(b"\r\n", 1)[0].split(b" ")
            if len(request) != 3 or request[0] != b"CONNECT":
                return self._reject(client, "403 Forbidden")
            if request[1] != self._authority or request[2] not in {b"HTTP/1.0", b"HTTP/1.1"}:
                return self._reject(client, "403 Forbidden")
            authorities = [line[5:].strip() for line in bytes(header).split(b"\r\n") if line.lower().startswith(b"host:")]
            if authorities != [self._authority]:
                return self._reject(client, "403 Forbidden")
            upstream = socket.create_connection((self._host, self._port), timeout=10)
            upstream.settimeout(None)
            client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            client.settimeout(None)
            self._relay(client, upstream)
        except OSError:
            try:
                self._reject(client, "502 Bad Gateway")
            except Exception:
                pass

    def _handle_and_forget(self, client: socket.socket) -> None:
        worker = threading.current_thread()
        try:
            self._handle(client)
        finally:
            with self._clients_lock:
                self._clients.discard(worker)
            self._slots.release()

    def _serve(self) -> None:
        while not self._stopping.is_set():
            try:
                client, _ = self._listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            if not self._slots.acquire(blocking=False):
                self._reject(client, "503 Service Unavailable")
                continue
            with self._clients_lock:
                worker = threading.Thread(
                    target=self._handle_and_forget, args=(client,), daemon=True
                )
                self._clients.add(worker)
                worker.start()
        try:
            self._listener.close()
        except OSError:
            pass

    def __enter__(self) -> "ProviderProxy":
        return self

    def __exit__(self, *_args: object) -> None:
        self._stopping.set()
        try:
            self._listener.close()
        except OSError:
            pass
        self._thread.join(timeout=2)
        with self._clients_lock:
            workers = list(self._clients)
        for worker in workers:
            worker.join(timeout=2)
