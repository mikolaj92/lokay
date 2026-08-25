"""Purely classify one closed direct-product preflight result."""


def classify(preflight: dict) -> dict:
    return {
        "ok": True,
        "route": "product" if preflight.get("ok") else "terminal",
        "preflight": preflight,
    }
