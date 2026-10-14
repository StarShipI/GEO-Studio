# -*- coding: utf-8 -*-
"""再写一条快照（模拟第二轮采样）+ 生成周报验证环比 + 快速探活 wenxin。"""
import json, sys
sys.path.insert(0, ".")
from app.database import SessionLocal
from app.services.snapshot import write_brand_snapshot
from app.services import metrics

db = SessionLocal()
# 模拟第二轮：可见度略降（把提到的查询数减 1 生成不同值）——直接写快照即可，数值基于当前指标
snap = write_brand_snapshot(db, 5)
print("snapshot2:", snap.visibility_rate, snap.sov)
db.close()

import urllib.request
# 生成周报（含环比）
req = urllib.request.Request("http://127.0.0.1:8000/api/reports/weekly/5", method="POST")
r = urllib.request.urlopen(req, timeout=60)
d = json.loads(r.read())
print("weekly:", d["path"])
import io
md = io.open(d["path"], encoding="utf-8").read()
for line in md.splitlines():
    if "环比" in line:
        print(">>", line)
