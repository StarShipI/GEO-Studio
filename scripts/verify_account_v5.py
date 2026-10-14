# -*- coding: utf-8 -*-
"""清理重复内容 + 跑一轮 wenxin 真实采样（瑞幸）+ 重验账号摘要与周报。"""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"

def req(method, path, body=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=timeout).read())

# 1) 清理重复内容（id 9-12 是 5-8 的重复副本，上一脚本重跑产生）
for i in range(9, 13):
    try:
        req("DELETE", f"/api/account/content-items/{i}")
        print("deleted dup", i)
    except Exception as e:
        print("del", i, "fail:", e)
items = req("GET", "/api/account/content-items/5")
print("content_items after cleanup:", len(items))

# 2) 找瑞幸的 wenxin 任务并采样
tasks = req("GET", "/api/sampling/tasks")
kws = req("GET", "/api/brands/5")
kw_ids = {k["id"] for k in kws.get("keywords", [])}
wx = [t["id"] for t in tasks if t["engine"] == "wenxin" and t["keyword_id"] in kw_ids]
print("wenxin tasks for 瑞幸:", len(wx))
if wx:
    r = req("POST", "/api/sampling/run", {"task_ids": wx[:8]}, timeout=600)
    ok = sum(1 for v in r.values() if str(v).startswith("ok"))
    print("sampled ok:", ok, "/", len(r))
