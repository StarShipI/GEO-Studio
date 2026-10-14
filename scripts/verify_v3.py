# -*- coding: utf-8 -*-
"""复测：引擎报告 path 入库 + 快照写入 + 趋势查询。"""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def call(path, method="GET", body=None):
    req = urllib.request.Request(BASE + path, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(body).encode("utf-8")
    try:
        r = urllib.request.urlopen(req, timeout=60)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")[:300]


s, d = call("/api/reports/engine/5", "POST")
print("engine report:", s, d.get("path", d)[:60])

s, d = call("/api/reports?brand_id=5")
print("reports[0].path:", s, d[0].get("path", "NO-PATH") if d else "none")

# 快照写入（复用服务层，不经过 HTTP，确保同一代码库）
import sys
sys.path.insert(0, ".")
from app.database import SessionLocal
from app.services.snapshot import write_snapshots_for_brands
db = SessionLocal()
n = write_snapshots_for_brands(db, [5])
print("snapshots written:", n)
db.close()

s, d = call("/api/analytics/trend/5")
print("trend:", s, [(t["sampled_at"][:19], t["visibility_rate"], t["sov"]) for t in d["trend"][-3:]])

s, d = call("/api/analytics/visibility/5")
print("visibility sov:", s, d.get("sov"), "insufficient:", d.get("sov_insufficient"))
