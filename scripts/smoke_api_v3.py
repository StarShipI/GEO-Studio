# -*- coding: utf-8 -*-
"""新功能 API 冒烟测试。"""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def call(path, method="GET", body=None):
    req = urllib.request.Request(BASE + path, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(body).encode("utf-8")
    try:
        r = urllib.request.urlopen(req, timeout=30)
        raw = r.read().decode("utf-8")
        try:
            return r.status, json.loads(raw)
        except Exception:
            return r.status, raw[:200]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")[:200]


checks = []

s, d = call("/api/analytics/trend/5")
checks.append(("trend/5", s, d.get("trend", "ERR") if isinstance(d, dict) else d))

s, d = call("/api/analytics/compare?ids=5,3,4")
checks.append(("compare 5,3,4", s, [i["brand_name"] for i in d.get("items", [])] if isinstance(d, dict) else d))

s, d = call("/api/export/citations/5")
checks.append(("export csv", s, d[:60].replace("\n", " | ") if isinstance(d, str) else d))

s, d = call("/api/sampling/tasks/28", "PATCH", {"status": "paused"})
checks.append(("patch task 28 paused", s, d))

s, d = call("/api/sampling/tasks/28", "PATCH", {"status": "active", "frequency_hours": 48})
checks.append(("patch task 28 back", s, d))

s, d = call("/api/brands/5/alerts", "PATCH", {"negative_threshold": 3, "visibility_drop": 0.3})
checks.append(("patch alerts brand5", s, d))

s, d = call("/api/reports?brand_id=5")
checks.append(("reports path", s, d[0].get("path", "NO-PATH") if isinstance(d, list) and d else d))

s, d = call("/api/brands/5")
checks.append(("brand detail alerts", s, {k: d.get(k) for k in ("alert_negative_threshold", "alert_visibility_drop")} if isinstance(d, dict) else d))

for name, s, d in checks:
    print(f"{name}: {s} | {d}")
