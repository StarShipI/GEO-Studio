# -*- coding: utf-8 -*-
"""console.html 补丁 3：内容清单管理（账号 GEO）+ 账号视图入口。"""
import io

P = "web/console.html"
s = io.open(P, encoding="utf-8").read()

def rep(old, new, tag):
    global s
    assert old in s, f"[{tag}] anchor missing"
    s = s.replace(old, new, 1)
    print(f"[{tag}] ok")

# R1 renderDetail：hint 加账号视图入口 + 词库表后追加内容清单区 + 绑定添加按钮
rep("""      box.innerHTML =
        '<div class="hint">官网：' + (d.official_domain || '未填') + ' ｜ 竞品：' + comps + '</div>' +
        '<div class="tbl-wrap"><table class="fixed kw-tbl"><colgroup><col style="width:8%"><col style="width:58%"><col style="width:34%"></colgroup>' +
        '<thead><tr><th>ID</th><th>查询词</th><th>场景</th></tr></thead><tbody>' + (rows || '<tr><td colspan="3">暂无查询词</td></tr>') + '</tbody></table></div>' +
        '<div style="margin-top:12px"><div class="hint">添加查询词（自动为当前全部引擎建任务）：</div>' +
        '<div class="f-row"><div class="f"><input id="kwText" placeholder="如：瑞幸咖啡 新品"></div>' +
        '<div class="f"><input id="kwScn" placeholder="场景（可选）"></div>' +
        '<button class="primary" id="btnKw" style="white-space:nowrap">添加</button></div></div>';
      var b = $('btnKw');
      if (b) b.addEventListener('click', addKeyword);""",
"""      box.innerHTML =
        '<div class="hint">官网：' + (d.official_domain || '未填') + ' ｜ 竞品：' + comps + ' ｜ <a href="account.html" target="_blank" style="color:#059669;font-weight:600">打开账号视图 →</a></div>' +
        '<div class="tbl-wrap"><table class="fixed kw-tbl"><colgroup><col style="width:8%"><col style="width:58%"><col style="width:34%"></colgroup>' +
        '<thead><tr><th>ID</th><th>查询词</th><th>场景</th></tr></thead><tbody>' + (rows || '<tr><td colspan="3">暂无查询词</td></tr>') + '</tbody></table></div>' +
        '<div style="margin-top:12px"><div class="hint">添加查询词（自动为当前全部引擎建任务）：</div>' +
        '<div class="f-row"><div class="f"><input id="kwText" placeholder="如：瑞幸咖啡 新品"></div>' +
        '<div class="f"><input id="kwScn" placeholder="场景（可选）"></div>' +
        '<button class="primary" id="btnKw" style="white-space:nowrap">添加</button></div></div>' +
        '<div style="margin-top:16px;border-top:1px solid #eef0f3;padding-top:12px">' +
        '<div class="hint"><b>内容清单（账号 GEO）</b>：登记发布的内容 URL，系统监测被 AI 引用情况（哪篇、哪句话、收录时效）。平台可自动识别，发布时间用于计算收录时效。</div>' +
        '<div class="tbl-wrap"><table class="fixed" id="ctTbl"><colgroup><col style="width:38%"><col style="width:13%"><col style="width:15%"><col style="width:12%"><col style="width:22%"></colgroup>' +
        '<thead><tr><th>内容 URL</th><th>平台</th><th>发布时间</th><th>被引</th><th>操作</th></tr></thead>' +
        '<tbody id="ctBody"><tr><td colspan="5" class="empty">加载中…</td></tr></tbody></table></div>' +
        '<div class="f-row" style="margin-top:8px">' +
        '<div class="f" style="flex:2"><input id="ctUrl" placeholder="内容 URL，如 https://mp.weixin.qq.com/s/... 或小红书笔记链接"></div>' +
        '<div class="f"><select id="ctPlat"><option value="">自动识别</option><option>小红书</option><option>公众号</option><option>知乎</option><option>B站</option><option>抖音</option><option>微博</option><option>官网</option><option>其他</option></select></div>' +
        '<div class="f"><input id="ctPub" type="date" title="发布时间（收录时效基准）"></div>' +
        '<button class="primary" id="btnCtAdd" style="white-space:nowrap">添加内容</button></div></div>';
      var b = $('btnKw');
      if (b) b.addEventListener('click', addKeyword);
      var cb = $('btnCtAdd');
      if (cb) cb.addEventListener('click', addContentItem);
      loadContentItems();""", "renderDetail")

# R2 新函数：内容清单 CRUD（插在 addKeyword 函数之后）
rep("""  function addKeyword() {
    if (!state.current) { toast('请先选择品牌', 'err'); return; }
    var q = $('kwText').value.trim();
    if (!q) { toast('请填写查询词', 'err'); return; }
    api('/api/brands/' + state.current.id + '/keywords', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query_text: q, scenario: $('kwScn').value.trim() })
    }).then(function () { toast('查询词已添加'); renderDetail(); loadTasks(); })
      .catch(function (e) { toast('添加失败：' + e.message, 'err'); });
  }""",
"""  function addKeyword() {
    if (!state.current) { toast('请先选择品牌', 'err'); return; }
    var q = $('kwText').value.trim();
    if (!q) { toast('请填写查询词', 'err'); return; }
    api('/api/brands/' + state.current.id + '/keywords', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query_text: q, scenario: $('kwScn').value.trim() })
    }).then(function () { toast('查询词已添加'); renderDetail(); loadTasks(); })
      .catch(function (e) { toast('添加失败：' + e.message, 'err'); });
  }

  // ---- 内容清单（账号 GEO）----
  function loadContentItems() {
    if (!state.current) { return; }
    api('/api/account/content-items/' + state.current.id).then(function (items) {
      var body = $('ctBody');
      if (!body) { return; }
      if (!items.length) { body.innerHTML = '<tr><td colspan="5" class="empty">还没有登记内容——自媒体客户请添加发布的文章/笔记 URL（之后登录引擎采样即可监测引用）</td></tr>'; return; }
      body.innerHTML = items.map(function (c) {
        var platOpts = ['', '小红书', '公众号', '知乎', 'B站', '抖音', '微博', '官网', '其他'].map(function (p) {
          return '<option value="' + p + '"' + (c.platform === p ? ' selected' : '') + '>' + (p || '自动识别') + '</option>';
        }).join('');
        return '<tr><td>' + c.url + '</td>' +
          '<td><select class="mini ct-plat" data-id="' + c.id + '">' + platOpts + '</select></td>' +
          '<td><input type="date" class="ct-pub" data-id="' + c.id + '" value="' + (c.published_at ? c.published_at.slice(0, 10) : '') + '"></td>' +
          '<td id="ctCnt' + c.id + '">-</td>' +
          '<td><button class="mini ct-del" data-id="' + c.id + '">删除</button></td></tr>';
      }).join('');
      // 顺带拉一次账号摘要填充被引次数
      api('/api/account/summary/' + state.current.id).then(function (s) {
        (s.items || []).forEach(function (it) {
          var td = $('ctCnt' + it.id);
          if (td) { td.innerHTML = '<b>' + it.citation_count + '</b>' + (it.duration && it.duration !== '-' ? '<div class="mini-err" style="color:#6b7280">收录 ' + it.duration + '</div>' : ''); }
        });
      }).catch(function () {});
    }).catch(function () {});
  }

  function addContentItem() {
    if (!state.current) { toast('请先选择品牌', 'err'); return; }
    var url = $('ctUrl').value.trim();
    if (!url) { toast('请填写内容 URL', 'err'); return; }
    api('/api/account/content-items', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ brand_id: state.current.id, url: url, platform: $('ctPlat').value, published_at: $('ctPub').value })
    }).then(function () { toast('内容已登记，采样后即可监测引用'); $('ctUrl').value = ''; $('ctPub').value = ''; loadContentItems(); })
      .catch(function (e) { toast('添加失败：' + e.message, 'err'); });
  }

  function saveContentMeta(id, patch) {
    api('/api/account/content-items/' + id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(patch) })
      .then(function () { toast('已保存'); loadContentItems(); })
      .catch(function (e) { toast('保存失败：' + e.message, 'err'); });
  }

  function delContentItem(id) {
    if (!confirm('删除这条监控内容？引用历史会保留。')) { return; }
    api('/api/account/content-items/' + id, { method: 'DELETE' })
      .then(function () { toast('已删除'); loadContentItems(); })
      .catch(function (e) { toast('删除失败：' + e.message, 'err'); });
  }""", "content-funcs")

# R3 事件委托（detailBox 变更/点击）——插在告警阈值绑定前
rep("""  $('btnAlertCfg').addEventListener('click', saveAlertCfg);""",
"""  $('detailBox').addEventListener('change', function (e) {
    var s = e.target.closest('select.ct-plat');
    if (s) { saveContentMeta(Number(s.getAttribute('data-id')), { platform: s.value }); return; }
    var d = e.target.closest('input.ct-pub');
    if (d) { saveContentMeta(Number(d.getAttribute('data-id')), { published_at: d.value }); }
  });
  $('detailBox').addEventListener('click', function (e) {
    var b = e.target.closest('button.ct-del');
    if (b) { delContentItem(Number(b.getAttribute('data-id'))); }
  });
  $('btnAlertCfg').addEventListener('click', saveAlertCfg);""", "events")

open(P, "w", encoding="utf-8").write(s)
print("console.html patched (content list)")
