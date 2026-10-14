# -*- coding: utf-8 -*-
"""修复 engine_report 的 SOV 数据不足显示。"""
p = "app/services/engine_report.py"
s = open(p, encoding="utf-8").read()
old = '        ("引用份额 SOV", f"{vis.get(\'sov\', 0) * 100:.1f}%", "自身域名引用 / 全部引用"),'
new = ('        ("引用份额 SOV",\n'
       '         "数据不足" if vis.get("sov") is None else f"{vis[\'sov\'] * 100:.1f}%",\n'
       '         "自身域名引用 / 全部引用（引用 <5 条时为数据不足）"),')
assert old in s, "anchor missing"
open(p, "w", encoding="utf-8").write(s.replace(old, new))
print("engine_report.py patched")
