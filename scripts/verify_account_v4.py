# -*- coding: utf-8 -*-
"""账号 GEO 端到端验证：给瑞幸补真实跨平台内容 + 账号摘要 + 账号周报。"""
import io
import json
import urllib.request

BASE = "http://127.0.0.1:8000"

def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=30).read())

# 1) 添加真实跨平台内容（微博/抖音/36氪/行业媒体，发布时间取自搜索结果）
for url, platform, pub in [
    ("https://m.weibo.cn/detail/5140968359335161", "微博", "2025-03-05"),
    ("https://www.iesdouyin.com/share/video/7606306067194072383", "抖音", "2026-02-13"),
    ("https://m.36kr.com/p/1625977125367049", "其他", "2022-02-22"),
    ("https://www.woshipm.com/operate/5640864.html", "其他", "2026-08-29"),
]:
    print("add:", req("POST", "/api/account/content-items",
                      {"brand_id": 5, "url": url, "platform": platform, "published_at": pub}))

# 2) 内容清单
items = req("GET", "/api/account/content-items/5")
print("content_items:", len(items))
for it in items:
    print("  -", it["platform"], it["url"], it["published_at"])

# 3) 账号摘要
s = req("GET", "/api/account/summary/5")
print("summary: content=%s cited=%s rate=%s total_citations=%s avg_dur=%s" % (
    s["content_count"], s["cited_content_count"], s["citation_rate"], s["total_citations"], s.get("avg_cited_duration")))
print("platforms:")
for p in s["platforms"]:
    print("  ", p["platform"], "content:", p["content_count"], "cited:", p["cited_count"], "rate:", p["citation_rate"], "citations:", p["citations"])
print("cited items:")
for it in s["items"]:
    print("  ", it["url"], "count:", it["citation_count"], "first:", it["first_cited_at"], "dur:", it["duration"])
    for c in it["citations"][:2]:
        print("     [", c["engine"], "] Q:", c["query"][:30], "| snippet:", (c["snippet"] or "")[:40])
print("uncited count:", len(s["uncited"]))
for u in s["uncited"][:3]:
    print("  ", u["platform"], u["url"][:55], u["published_at"])
print("compare:")
for c in s["compare"]:
    print("  ", c["brand_name"], "content:", c["content_count"], "cited:", c["cited_content_count"], "rate:", c["citation_rate"])

# 4) 账号周报
rep = req("POST", "/api/reports/account/5")
print("account report:", rep.get("path"))
md = io.open(rep["path"], encoding="utf-8").read()
print("--- report head ---")
print("\n".join(md.splitlines()[:14]))
