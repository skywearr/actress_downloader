from __future__ import annotations

import json
from time import perf_counter
from typing import Any


def now() -> float:
    return perf_counter()


def emit_timing_event(label: str, started_at: float, **fields: Any) -> None:
    duration_ms = (perf_counter() - started_at) * 1000
    payload = {
        "label": label,
        "duration_ms": round(duration_ms, 2),
        **fields,
    }
    print(f"[timing] {json.dumps(payload, ensure_ascii=False, sort_keys=True)}", flush=True)
