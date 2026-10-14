# -*- coding: utf-8 -*-
"""幂等收尾：清重复内容 → 采样 wenxin（瑞幸前 6 个任务）→ 验证账号摘要+周报。"""
import json
import time
import urllib.request

BASE = "http://127.0.0.1:8000"

def req(method, path, body=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=timeout).read())

# 1) 内容去重（按 URL 保留最早，删其余）
items = req("GET", "/api/account/content-items/5")
seen, keep, drop = set(), [], []
for it in items:
    if it["url"] in seen:
        drop.append(it["id"])
    else:
        seen.add(it["url"])
        keep.append(it)
for d in drop:
    req("DELETE", f"/api/account/content-items/{d}")
print(f"content_items: {len(keep)} kept, {len(drop)} dup removed")

# 2) 采样 wenxin 瑞幸任务（前 6 个，后台异步）
tasks = req("GET", "/api/sampling/tasks?limit=500")
kws = req("GET", "/api/brands/5")
kw_ids = {k["id"] for k in kws.get("keywords", [])}
wx = [t["id"] for t in tasks if t["engine"] == "wenxin" and t["keyword_id"] in kw_ids and t["status"] != "paused"][:6]
print("sampling wenxin tasks:", wx)
req("POST", "/api/sampling/run", {"task_ids": wx})
time.sleep(75)  # 等后台采样完成

# 3) 采样后再查任务状态
tasks = req("GET", "/api/sampling/tasks?limit=500")
for t in tasks:
    if t["id"] in wx:
        print("task", t["id"], t["status"], "|", (t.get("last_error") or "")[:80])

# 4) 账号摘要（无 hours = 全量口径，看被引内容）
s = req("GET", "/api/account/summary/5")
print("summary: content=%s cited=%s rate=%s total_cit=%s" % (
    s["content_count"], s["cited_content_count"], s["citation_rate"], s["total_citations"]))
for it in s["items"]:
    print("  cited:", it["url"][:50], "count:", it["citation_count"], "first:", (it["first_cited_at"] or "")[:10], "dur:", it["duration"])
print("  uncited:", len(s["uncited"]))
