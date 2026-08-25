"""Select the closed product-entry terminal."""


def terminal(classified: dict, product: dict) -> dict:
    if classified.get("route") == "product":
        return {
            "ok": True,
            "result": product.get("payload")
            or {"ok": False, "health": "product_result_missing"},
        }
    return {
        "ok": True,
        "result": {
            "ok": False,
            "error": "preflight failed; product workflow blocked",
            "health": "preflight_failed",
            "preflight": classified.get("preflight") or {},
            "live": False,
            "idle": False,
            "progress": 0,
            "results": [],
        },
    }
