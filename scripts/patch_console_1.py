# -*- coding: utf-8 -*-
"""console.html 批量补丁：登录引导/任务启停/探活/CSV导出/打开报告/告警阈值。"""
import io

P = "web/console.html"
s = io.open(P, encoding="utf-8").read()

def rep(old, new, tag):
    global s
    assert old in s, f"[{tag}] anchor missing"
    s = s.replace(old, new, 1)
    print(f"[{tag}] ok")

# R1 CSS
rep("""  .st.idle { background: #f3f4f6; color: #6b7280; }""",
"""  .st.idle { background: #f3f4f6; color: #6b7280; }
  button.mini, select.mini { padding: 3px 8px; font-size: 12px; border-radius: 6px; width: auto; }
  #probeBox { margin-top: 10px; }
  #probeBox .pr { font-size: 12.5px; padding: 5px 0; }
  .pr.ok { color: #059669; } .pr.bad { color: #dc2626; }
  .cfg-line { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; font-size: 13.5px; }
  .cfg-line input { width: 80px; }""", "css")

# R2 采样卡：登录引导 + 探活
rep("""      <div class="ops">
        <button class="primary" data-act="all">采样全部品牌</button>
        <button data-act="brand">采样当前品牌</button>
        <button data-act="retry">重跑出错任务</button>
      </div>
    </div>""",
"""      <div class="ops">
        <button class="primary" data-act="all">采样全部品牌</button>
        <button data-act="brand">采样当前品牌</button>
        <button data-act="retry">重跑出错任务</button>
      </div>
      <div class="hint" style="margin-top:12px">引擎登录引导：未登录/限流的引擎先登录一次，弹窗里完成登录/验证码后关闭窗口（cookie 自动保存）：</div>
      <div class="ops">
        <button data-login="wenxin">登录文心</button>
        <button data-login="kimi">登录 Kimi</button>
        <button data-login="doubao">登录豆包</button>
        <button data-login="yuanbao">登录元宝</button>
        <button data-probe="1">探测全部引擎可用性（约 1 分钟）</button>
      </div>
      <div id="probeBox"></div>
    </div>""", "sampling-login")

# R3 报告卡：导出 CSV
rep("""          <button data-act="checkidx">检查 AI 收录</button>
        </div>""",
"""          <button data-act="checkidx">检查 AI 收录</button>
          <button data-act="export">导出引用明细 CSV</button>
        </div>""", "export-btn")

# R4 告警卡：阈值配置
rep("""    <div class="card"><h2>告警中心 <span class="tag">负面提及 / 可见度骤降</span></h2>""",
"""    <div class="card"><h2>告警阈值 <span class="tag">按当前品牌设置</span></h2>
      <div class="cfg-line">
        <span>负面提及达到</span><input id="aNeg" type="number" min="0" value="1"><span>条时告警；</span>
        <span>可见度下降超过</span><input id="aDrop" type="number" min="0" max="100" value="20"><span>% 时告警</span>
        <button class="primary" id="btnAlertCfg" style="white-space:nowrap">保存阈值</button>
      </div>
      <div class="hint" style="margin-top:6px">告警会写入下方列表（配置了飞书 webhook 也会推送到群）。</div>
    </div>
    <div class="card"><h2>告警中心 <span class="tag">负面提及 / 可见度骤降</span></h2>""", "alert-cfg")

# R5 renderTasks：加操作列
rep("""    box.innerHTML = '<div class="tbl-wrap"><table class="fixed"><colgroup><col style="width:6%"><col style="width:10%"><col style="width:34%"><col style="width:14%"><col style="width:36%"></colgroup>' +
      '<thead><tr><th>ID</th><th>引擎</th><th>查询词</th><th>状态</th><th>说明 / 错误</th></tr></thead><tbody>' +
      rows.map(function (t) {
        var kw = state.kwMap ? state.kwMap[t.keyword_id] : '';
        return '<tr><td>' + t.id + '</td><td>' + t.engine + '</td><td>' + (kw || '#' + t.keyword_id) + '</td>' +
          '<td><span class="st ' + (t.status === 'active' ? 'active' : t.status === 'error' ? 'error' : t.status === 'done' ? 'done' : 'pending') + '">' + t.status + '</span></td>' +
          '<td>' + (t.last_error ? '<div class="mini-err">' + (t.last_error.slice(0, 90)) + '</div>' : (t.last_run_at ? '上次 ' + t.last_run_at.slice(0, 16).replace('T', ' ') : '-')) + '</td></tr>';
      }).join('') + '</tbody></table></div>';""",
"""    box.innerHTML = '<div class="tbl-wrap"><table class="fixed"><colgroup><col style="width:5%"><col style="width:8%"><col style="width:28%"><col style="width:10%"><col style="width:27%"><col style="width:22%"></colgroup>' +
      '<thead><tr><th>ID</th><th>引擎</th><th>查询词</th><th>状态</th><th>说明 / 错误</th><th>操作</th></tr></thead><tbody>' +
      rows.map(function (t) {
        var kw = state.kwMap ? state.kwMap[t.keyword_id] : '';
        var freqOpts = [12, 24, 48, 72, 168].map(function (h) {
          return '<option value="' + h + '"' + (t.frequency_hours === h ? ' selected' : '') + '>' + h + 'h</option>';
        }).join('');
        return '<tr><td>' + t.id + '</td><td>' + t.engine + '</td><td>' + (kw || '#' + t.keyword_id) + '</td>' +
          '<td><span class="st ' + (t.status === 'active' ? 'active' : t.status === 'error' ? 'error' : t.status === 'done' ? 'done' : 'pending') + '">' + t.status + '</span></td>' +
          '<td>' + (t.last_error ? '<div class="mini-err">' + (t.last_error.slice(0, 80)) + '</div>' : (t.last_run_at ? '上次 ' + t.last_run_at.slice(0, 16).replace('T', ' ') : '-')) + '</td>' +
          '<td><button class="mini" data-tg="' + t.id + '" data-st="' + t.status + '">' + (t.status === 'paused' ? '启用' : '停用') + '</button> ' +
          '<select class="mini" data-freq="' + t.id + '" title="采样频率">' + freqOpts + '</select></td></tr>';
      }).join('') + '</tbody></table></div>';""", "renderTasks-ops")

# R6 loadReports：打开链接
rep("""          return '<tr><td>' + (bn ? bn.name : '#' + r.brand_id) + '</td><td>' + (r.period_start || '').slice(0, 10) + ' 至 ' + (r.period_end || '').slice(0, 10) + '</td><td>' + (r.created_at || '').slice(0, 16).replace('T', ' ') + '</td><td>reports/' + (bn ? bn.name : '') + '/ 目录</td></tr>';""",
"""          var openLink = r.path ? '<a href="#" data-open="' + r.path + '" style="color:#1d4ed8">打开</a>' : '-';
          return '<tr><td>' + (bn ? bn.name : '#' + r.brand_id) + '</td><td>' + (r.period_start || '').slice(0, 10) + ' 至 ' + (r.period_end || '').slice(0, 10) + '</td><td>' + (r.created_at || '').slice(0, 16).replace('T', ' ') + '</td><td>' + openLink + '</td></tr>';""", "reports-open")

open(P, "w", encoding="utf-8").write(s)
print("console.html patched (HTML/CSS/JS part 1)")
