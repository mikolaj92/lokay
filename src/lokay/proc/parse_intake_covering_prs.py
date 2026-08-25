"""Parse bounded covering-PR CLI evidence into a closed physical schema."""


def parse(request: dict) -> dict:
    rows = []
    try:
        for raw in request.get("covering_prs") or []:
            text = str(raw)
            num, state = (
                (text.split(":", 1) + ["OPEN"])[:2] if ":" in text else (text, "OPEN")
            )
            rows.append(
                {
                    "number": int(num),
                    "state": state.upper(),
                    "merged": state.lower() == "merged",
                }
            )
    except (TypeError, ValueError) as exc:
        return {
            "ok": True,
            "route": "terminal",
            "reason": "invalid_covering_pr",
            "error": str(exc),
            "prs": [],
        }
    return {"ok": True, "route": "parsed", "prs": rows}
