# -*- coding: utf-8 -*-
"""console.html 补丁 2：新功能 JS 逻辑与事件绑定。"""
import io

P = "web/console.html"
s = io.open(P, encoding="utf-8").read()

def rep(old, new, tag):
    global s
    assert old in s, f"[{tag}] anchor missing"
    s = s.replace(old, new, 1)
    print(f"[{tag}] ok")

# R7 新函数组：插在事件绑定前
rep("""  // ---- 事件绑定 ----
  $('ctxBrand').addEventListener('change', setContext);""",
"""  // ---- 新功能：登录引导 / 探活 / 任务启停 / 导出 / 阈值 / 打开报告 ----
  function engineLogin(engine) {
    api('/api/engines/login/' + engine, { method: 'POST' }).then(function (r) {
      toast('已打开浏览器，请完成登录/验证码后关闭窗口', 'ok');
    }).catch(function (e) { toast('打开失败：' + e.message, 'err'); });
  }

  function probeAll() {
    var box = $('probeBox');
    box.innerHTML = '<div class="pr">正在探测各引擎（每个约 15 秒，请稍候）…</div>';
    api('/api/engines/probe', { method: 'POST' }).then(function (r) {
      box.innerHTML = (r.results || []).map(function (p) {
        return '<div class="pr ' + (p.ok ? 'ok' : 'bad') + '">' + p.engine + '：' + (p.ok ? '可用' : '不可用') + ' — ' + p.note + '</div>';
      }).join('') || '<div class="pr">无结果</div>';
    }).catch(function (e) {
      box.innerHTML = '<div class="pr bad">探测失败：' + e.message + '</div>';
    });
  }

  function toggleTask(id, cur) {
    var next = cur === 'paused' ? 'active' : 'paused';
    api('/api/sampling/tasks/' + id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: next }) })
      .then(function () { toast('任务 ' + id + ' 已' + (next === 'active' ? '启用' : '停用'), 'ok'); loadTasks(); })
      .catch(function (e) { toast('操作失败：' + e.message, 'err'); });
  }

  function setFreq(id, h) {
    api('/api/sampling/tasks/' + id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ frequency_hours: h }) })
      .then(function () { toast('任务 ' + id + ' 采样频率已改为每 ' + h + ' 小时', 'ok'); })
      .catch(function (e) { toast('设置失败：' + e.message, 'err'); });
  }

  function loadAlertCfg() {
    if (!state.current) { return; }
    api('/api/brands/' + state.current.id).then(function (d) {
      $('aNeg').value = d.alert_negative_threshold;
      $('aDrop').value = Math.round((d.alert_visibility_drop || 0.2) * 100);
    }).catch(function () {});
  }

  function saveAlertCfg() {
    if (!state.current) { toast('请先选择品牌', 'err'); return; }
    var neg = parseInt($('aNeg').value, 10);
    var drop = parseFloat($('aDrop').value);
    if (isNaN(neg) || neg < 0 || isNaN(drop)) { toast('阈值填写有误', 'err'); return; }
    api('/api/brands/' + state.current.id + '/alerts', {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ negative_threshold: neg, visibility_drop: drop / 100 })
    }).then(function (r) { toast('阈值已保存（负面 ≥' + r.negative_threshold + ' 条 / 下降 ≥' + Math.round(r.visibility_drop * 100) + '%）', 'ok'); })
      .catch(function (e) { toast('保存失败：' + e.message, 'err'); });
  }

  function exportCsv() {
    if (!state.current) { toast('请先选择品牌', 'err'); return; }
    window.open(API_BASE + '/api/export/citations/' + state.current.id);
  }

  function openReport(path) {
    if (!path) { toast('该报告没有文件路径', 'err'); return; }
    window.open('file:///' + path.replace(/\\\\/g, '/'));
  }

  // ---- 事件绑定 ----
  $('ctxBrand').addEventListener('change', setContext);""", "funcs")

# R8 setContext 载入阈值
rep("""  function setContext() {
    var v = Number($('ctxBrand').value);
    state.current = state.brands.find(function (b) { return b.id === v; }) || null;
    renderBrandList();
    renderDetail();
  }""",
"""  function setContext() {
    var v = Number($('ctxBrand').value);
    state.current = state.brands.find(function (b) { return b.id === v; }) || null;
    renderBrandList();
    renderDetail();
    loadAlertCfg();
  }""", "setContext")

# R9 修正 tasks 绑定（只绑 data-act，避免误绑登录按钮）
rep("""  document.querySelectorAll('#tab-tasks .ops button').forEach(function (b) {
    b.addEventListener('click', function () { samplingAction(b.getAttribute('data-act')); });
  });""",
"""  document.querySelectorAll('#tab-tasks .ops button[data-act]').forEach(function (b) {
    b.addEventListener('click', function () { samplingAction(b.getAttribute('data-act')); });
  });
  $('taskBox').addEventListener('click', function (e) {
    var b = e.target.closest('button[data-tg]');
    if (b) { toggleTask(Number(b.getAttribute('data-tg')), b.getAttribute('data-st')); }
  });
  $('taskBox').addEventListener('change', function (e) {
    var s = e.target.closest('select[data-freq]');
    if (s) { setFreq(Number(s.getAttribute('data-freq')), parseInt(s.value, 10)); }
  });
  document.querySelectorAll('button[data-login]').forEach(function (b) {
    b.addEventListener('click', function () { engineLogin(b.getAttribute('data-login')); });
  });
  document.querySelector('button[data-probe]').addEventListener('click', probeAll);""", "task-bind")

# R10 报告绑定：export 单独处理
rep("""  document.querySelectorAll('#tab-reports .ops button').forEach(function (b) {
    b.addEventListener('click', function () { reportAction(b.getAttribute('data-act')); });
  });""",
"""  document.querySelectorAll('#tab-reports .ops button[data-act]').forEach(function (b) {
    b.addEventListener('click', function () {
      var k = b.getAttribute('data-act');
      if (k === 'export') { exportCsv(); } else { reportAction(k); }
    });
  });
  $('repBox').addEventListener('click', function (e) {
    var a = e.target.closest('a[data-open]');
    if (a) { e.preventDefault(); openReport(a.getAttribute('data-open')); }
  });""", "report-bind")

# R11 告警阈值保存
rep("""  $('btnUnres').addEventListener('click', function () {""",
"""  $('btnAlertCfg').addEventListener('click', saveAlertCfg);
  $('btnUnres').addEventListener('click', function () {""", "alert-bind")

open(P, "w", encoding="utf-8").write(s)
print("console.html patched (part 2)")
