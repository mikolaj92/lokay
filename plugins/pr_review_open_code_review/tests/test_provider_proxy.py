from __future__ import annotations

import socket
import threading

import pytest

from lokay_review_open_code_review.provider_proxy import ProviderProxy


def _echo_server():
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    received: list[bytes] = []

    def serve():
        try:
            connection, _ = listener.accept()
        except OSError:
            return
        with connection:
            payload = connection.recv(64)
            received.append(payload)
            connection.sendall(payload)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    return listener, thread, received


def test_proxy_tunnels_only_the_exact_configured_provider_authority():
    listener, thread, received = _echo_server()
    host, port = listener.getsockname()
    try:
        with ProviderProxy(host, port) as proxy:
            client = socket.create_connection(("127.0.0.1", proxy.port), timeout=2)
            with client:
                client.sendall(f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n".encode())
                assert client.recv(128).startswith(b"HTTP/1.1 200")
                client.sendall(b"provider request")
                assert client.recv(64) == b"provider request"
            thread.join(timeout=2)
            assert received == [b"provider request"]
    finally:
        listener.close()


def test_proxy_rejects_other_hosts_and_non_connect_methods():
    listener, _thread, _received = _echo_server()
    host, port = listener.getsockname()
    try:
        with ProviderProxy(host, port) as proxy:
            for request in (
                (b"CONNECT attacker.example:443 HTTP/1.1\r\nHost: attacker.example:443\r\n\r\n", b"HTTP/1.1 403"),
                (f"GET http://{host}:{port}/ HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n".encode(), b"HTTP/1.1 403"),
                (f"CONNECT {host}:{port} HTTP/1.1\r\nHost: attacker.example:443\r\n\r\n".encode(), b"HTTP/1.1 403"),
                (f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\nHost: {host}:{port}\r\n\r\n".encode(), b"HTTP/1.1 403"),
            ):
                with socket.create_connection(("127.0.0.1", proxy.port), timeout=2) as client:
                    client.sendall(request[0])
                    assert client.recv(128).startswith(request[1])
    finally:
        listener.close()


def test_proxy_bounds_idle_client_threads():
    listener, _thread, _received = _echo_server()
    host, port = listener.getsockname()
    clients = []
    try:
        with ProviderProxy(host, port) as proxy:
            for _ in range(4):
                client = socket.create_connection(("127.0.0.1", proxy.port), timeout=1)
                clients.append(client)
            rejected = socket.create_connection(("127.0.0.1", proxy.port), timeout=1)
            clients.append(rejected)
            assert rejected.recv(128).startswith(b"HTTP/1.1 503")
    finally:
        for client in clients:
            client.close()
        listener.close()


def test_proxy_removes_finished_client_workers_from_capacity_set():
    listener, _thread, _received = _echo_server()
    host, port = listener.getsockname()
    try:
        with ProviderProxy(host, port) as proxy:
            with socket.create_connection(("127.0.0.1", proxy.port), timeout=2) as client:
                client.sendall(
                    f"GET / HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n".encode()
                )
                assert client.recv(128).startswith(b"HTTP/1.1 403")
            for _ in range(100):
                with proxy._clients_lock:
                    if not proxy._clients:
                        break
                threading.Event().wait(0.01)
            with proxy._clients_lock:
                assert not proxy._clients
    finally:
        listener.close()


def test_proxy_rejects_malformed_and_oversized_connect_headers():
    listener, _thread, _received = _echo_server()
    host, port = listener.getsockname()
    try:
        with ProviderProxy(host, port) as proxy:
            with socket.create_connection(("127.0.0.1", proxy.port), timeout=2) as client:
                client.sendall(b"CONNECT attacker.example:443 HTTP/1.1\r\n\r\n")
                assert client.recv(128).startswith(b"HTTP/1.1 403")
            with socket.create_connection(("127.0.0.1", proxy.port), timeout=2) as client:
                client.sendall(b"GET / HTTP/1.1\r\nHost: provider\r\n\r\n")
                assert client.recv(128).startswith(b"HTTP/1.1 403")
            with socket.create_connection(("127.0.0.1", proxy.port), timeout=2) as client:
                client.sendall(b"CONNECT " + f"{host}:{port}".encode() + b" HTTP/1.1\r\nX: " + b"x" * 9000)
                assert client.recv(128).startswith(b"HTTP/1.1 400")
    finally:
        listener.close()
