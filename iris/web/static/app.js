/* Iris 工具箱 —— 桌面端界面（Fluent 排版，参考拖把工具箱） */
"use strict";

const TOKEN = window.__IRIS_TOKEN__;
const EMBED = window.__IRIS_DATA__ || null;
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

async function api(path, options = {}) {
  if (EMBED) {
    const key = path.split("?")[0];
    if (EMBED[key] !== undefined) return EMBED[key];
    throw new Error("静态快照：这个功能需要启动本地服务（iris gui）");
  }
  const res = await fetch(path, {
    ...options,
    headers: { "X-Iris-Token": TOKEN, ...(options.headers || {}) },
  });
  const text = await res.text();
  let data;
  try { data = JSON.parse(text); } catch { data = { error: text }; }
  if (!res.ok) {
    const err = new Error(data.error || `HTTP ${res.status}`);
    err.hint = data.hint || "";
    throw err;
  }
  return data;
}

function toast(msg, bad) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.toggle("bad", !!bad);
  el.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.remove("show"), 3000);
}

const human = (n) => {
  const u = ["B", "KiB", "MiB", "GiB", "TiB"];
  let v = n, i = 0;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return (i === 0 ? v : v.toFixed(1)) + u[i];
};

const head = (title, sub) => `<div class="page-head"><h1>${esc(title)}</h1><p>${esc(sub)}</p></div>`;

/* ---------------- 图标 ---------------- */
const ICONS = {
  device: '<rect x="6.5" y="3" width="11" height="18" rx="2.4"/><path d="M10.5 18.4h3"/>',
  flash: '<path d="M13 2.5L4.5 14H10l-1 7.5L18.5 10H13l1-7.5z"/>',
  root: '<circle cx="8.5" cy="12" r="3.2"/><path d="M11.7 12H21M17.6 12v3.4M20.6 12v2.2"/>',
  cast: '<rect x="3" y="4.5" width="18" height="11.5" rx="2"/><path d="M8.5 20h7"/><path d="M12 16v4"/>',
  apps: '<rect x="4" y="4" width="6.5" height="6.5" rx="1.4"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="1.4"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="1.4"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.4"/>',
  files: '<path d="M3.5 7.2A2.2 2.2 0 015.7 5h4l1.8 2h6.8a2.2 2.2 0 012.2 2.2v8.6a2.2 2.2 0 01-2.2 2.2H5.7a2.2 2.2 0 01-2.2-2.2V7.2z"/>',
  backup: '<path d="M12 3l7.5 3.2v5.6c0 4.7-3.1 7.9-7.5 9.2-4.4-1.3-7.5-4.5-7.5-9.2V6.2L12 3z"/><path d="M9 11.8l2.1 2.1 4-4.2"/>',
  misc: '<path d="M14.8 6.2a4.2 4.2 0 00-5.3 5.3l-6 6 2 2 6-6a4.2 4.2 0 005.3-5.3l-2.4 2.4-2-2 2.4-2.4z"/>',
  firmware: '<path d="M12 3.5v11.5M7.5 10.5L12 15l4.5-4.5"/><path d="M4 20.5h16"/>',
  settings: '<circle cx="12" cy="12" r="3.1"/><path d="M12 2.8v2.6M12 18.6v2.6M2.8 12h2.6M18.6 12h2.6M5.2 5.2l1.9 1.9M16.9 16.9l1.9 1.9M18.8 5.2l-1.9 1.9M7.1 16.9l-1.9 1.9"/>',
};

function svg(name) {
  return `<svg viewBox="0 0 24 24">${ICONS[name] || ICONS.misc}</svg>`;
}

/* ---------------- 导航 ---------------- */
const SECTIONS = [
  { id: "device", name: "设备信息", icon: "device", render: renderDevice },
  { id: "flash", name: "刷机", icon: "flash", render: renderFlash },
  { id: "root", name: "一键ROOT", icon: "root", render: renderRoot },
  { id: "cast", name: "投屏", icon: "cast", render: renderCast },
  { id: "apps", name: "软件管理", icon: "apps", render: renderApps },
  { id: "files", name: "文件管理", icon: "files", render: renderFiles },
  { id: "backup", name: "基带备份", icon: "backup", render: renderBackup },
  { id: "misc", name: "杂项", icon: "misc", render: renderMisc },
  { id: "firmware", name: "固件下载", icon: "firmware", render: renderFirmware },
  { id: "settings", name: "设置", icon: "settings", render: renderSettings },
];

function buildNav() {
  const top = SECTIONS.filter((s) => s.id !== "settings");
  const bottom = SECTIONS.filter((s) => s.id === "settings");
  const item = (s) => `<button class="nav-item" data-id="${s.id}">${svg(s.icon)}<span>${esc(s.name)}</span></button>`;
  $("#nav").innerHTML = top.map(item).join("");
  $("#navFoot").innerHTML = bottom.map(item).join("");
  document.querySelectorAll(".nav-item").forEach((b) => {
    b.addEventListener("click", () => show(b.dataset.id));
  });
}

async function show(id) {
  const sec = SECTIONS.find((s) => s.id === id);
  if (!sec) return;
  document.querySelectorAll(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.id === id));
  const main = $("#main");
  main.dataset.booted = "1";
  main.scrollTop = 0;
  main.innerHTML = head(sec.name, "加载中…");
  try {
    await sec.render(main);
  } catch (e) {
    main.innerHTML = head(sec.name, "出错了") + `<div class="card"><div class="alert">${esc(e.message)}</div></div>`;
  }
}

/* 给无浏览器冒烟测试用；不影响界面 */
window.__IRIS_DEBUG__ = { SECTIONS, show };

/* ---------------- 系统状态 ---------------- */
async function refreshStatus() {
  try {
    const p = await api("/api/info");
    const bar = $("#tbStatus");
    bar.classList.add("on");
    bar.querySelector("span").textContent = `${p.brand} ${p.model} · ${p.ab_update ? "A/B" : "单槽"} · ${p.root ? "ROOT" : "未 root"}`;
    return p;
  } catch {
    const bar = $("#tbStatus");
    bar.classList.remove("on");
    bar.querySelector("span").textContent = "未连接";
    return null;
  }
}

/* ================= 设备信息 ================= */
async function renderDevice(main) {
  main.innerHTML = head("设备信息", "连接状态、硬件画像与常用操作") + `
    <div class="statusbar off" id="stBar">
      <div class="beacon">●</div>
      <div class="st-text">
        <div class="st-title" id="stTitle">正在检测设备…</div>
        <div class="st-sub" id="stSub">adb devices</div>
      </div>
      <div class="st-right"><button class="btn" id="btnRefresh">刷新</button></div>
    </div>
    <div class="metrics" id="metrics"></div>
    <div class="grid2">
      <section class="card"><h2>设备画像</h2><div class="info-list" id="devInfo"></div></section>
      <section class="card"><h2>快捷操作</h2><div class="acts" id="devActs"></div><pre class="console hidden" id="actOut"></pre></section>
    </div>`;

  const load = async () => {
    const [info, root, stats] = await Promise.all([
      api("/api/info").catch(() => null),
      api("/api/root").catch(() => null),
      api("/api/device/stats").catch(() => null),
    ]);
    const p = info;
    const bar = $("#stBar");
    if (!p) {
      bar.classList.add("off");
      bar.querySelector(".beacon").textContent = "●";
      $("#stTitle").textContent = "未检测到设备";
      $("#stSub").textContent = "开启 USB 调试并连接数据线";
      $("#metrics").innerHTML = "";
      $("#devInfo").innerHTML = '<p class="empty-inline">连接手机后会自动读取设备信息</p>';
      $("#devActs").innerHTML = "";
      return;
    }
    bar.classList.remove("off");
    bar.querySelector(".beacon").textContent = "✓";
    $("#stTitle").textContent = `已连接：${p.brand} ${p.model}`;
    $("#stSub").textContent = `${p.serial} · Android ${p.android_release} · ${p.ab_update ? "A/B " + (p.slot_suffix || "") : "单槽位"}`;

    const battery = stats && typeof stats.battery_level === "number" ? stats.battery_level : null;
    const diskPct = stats && stats.disk_total ? Math.round(stats.disk_used / stats.disk_total * 100) : null;
    const diskText = stats && stats.disk_total ? `${human(stats.disk_used)} / ${human(stats.disk_total)}` : "未知";

    $("#metrics").innerHTML = `
      <div class="card metric">
        <div class="ring" style="--p:${battery || 0}" data-value="${battery === null ? "--" : battery + "%"}"></div>
        <div><div class="m-k">电量</div><div class="m-v">${battery === null ? "未知" : battery + "%"}</div><div class="m-s">${stats && stats.battery_temp ? stats.battery_temp + "°C" : "—"}</div></div>
      </div>
      <div class="card metric">
        <div class="ring" style="--p:${diskPct || 0}" data-value="${diskPct === null ? "--" : diskPct + "%"}"></div>
        <div><div class="m-k">存储（/data）</div><div class="m-v">${diskText}</div><div class="m-s">${diskPct === null ? "—" : diskPct + "% 已用"}</div></div>
      </div>
      <div class="card metric">
        <div class="ring" style="--p:${p.root ? 100 : 0}" data-value="${p.root ? "✓" : "—"}"></div>
        <div><div class="m-k">ROOT</div><div class="m-v">${p.root ? (root && root.manager ? root.manager : "已授权") : "未 root"}</div><div class="m-s">${p.root ? (root && root.su_path ? root.su_path : "") : "部分功能不可用"}</div></div>
      </div>`;

    const rows = [
      ["品牌 / 型号", `${p.brand} ${p.model}`],
      ["代号", p.codename || "—"],
      ["SoC", `${p.soc_manufacturer || ""} ${p.soc_model || ""}`.trim() || "—"],
      ["系统", `Android ${p.android_release}（SDK ${p.sdk}）`],
      ["A/B 槽位", p.ab_update ? (p.slot_suffix || "A/B") : "单槽位"],
      ["安全补丁", p.security_patch || "—"],
      ["by-name 根", p.by_name_root || "未探测到"],
      ["块设备", p.block_device || "—"],
      ["序列号", p.serial],
      ["架构", p.abi || "—"],
    ];
    $("#devInfo").innerHTML = rows.map(([k, v]) =>
      `<div class="row2"><span class="k">${esc(k)}</span><span class="v ${k === "序列号" || k === "by-name 根" ? "mono" : ""}" title="${esc(v)}">${esc(v)}</span></div>`).join("");

    const acts = [
      ["reboot_system", "重启系统"], ["reboot_recovery", "Recovery"], ["reboot_bootloader", "Bootloader"],
      ["reboot_fastbootd", "Fastbootd"], ["screenshot", "截图"], ["record", "录屏 15s"],
      ["tcpip", "无线调试"], ["logcat", "抓日志"], ["shutdown", "关机"],
    ];
    $("#devActs").innerHTML = acts.map(([a, n]) => `<button class="act" data-act="${a}">${n}</button>`).join("") +
      `<p class="meta" style="flex-basis:100%">截图与录屏保存在 shots/ 目录；无线调试会重启 adbd。</p>`;
    $("#devActs").querySelectorAll(".act").forEach((b) => {
      b.onclick = async () => {
        b.disabled = true;
        try {
          const r = await api("/api/device/action?name=" + b.dataset.act);
          toast(r.message, !r.ok);
          if (r.detail) { const o = $("#actOut"); o.classList.remove("hidden"); o.textContent = r.detail; }
        } catch (e) { toast(e.message, true); }
        finally { b.disabled = false; }
      };
    });
  };

  $("#btnRefresh").onclick = async () => { await load(); await refreshStatus(); };
  await load();
  await refreshStatus();
}

/* ================= 刷机 ================= */
async function renderFlash(main) {
  main.innerHTML = head("刷机", "分区表、还原与 fastboot 刷写。所有写操作先生成计划，确认后再执行。") + `
    <div class="grid2">
      <section class="card">
        <div class="panel-head"><h2>分区表</h2><span class="meta" id="partInfo" style="padding:0">需要 root</span></div>
        <div class="filerow" style="margin-bottom:10px">
          <input class="input" id="partFilter" placeholder="筛选分区名" spellcheck="false">
          <button class="btn" id="partRefresh">读取</button>
        </div>
        <div id="partTable"><p class="empty-inline">点「读取」获取 by-name 分区表</p></div>
      </section>
      <div class="stack">
        <section class="card">
          <h2>还原分区</h2>
          <div class="filerow">
            <input class="input mono" id="restorePart" placeholder="分区名，如 boot_a" spellcheck="false">
            <input class="input" id="restoreImg" placeholder="本地镜像绝对路径" spellcheck="false">
            <button class="btn" id="restorePlan">计划</button>
            <button class="btn btn-danger" id="restoreGo" disabled>还原</button>
          </div>
          <pre class="console hidden" id="restoreOut"></pre>
        </section>
        <section class="card">
          <h2>fastboot 刷入</h2>
          <p class="meta">手机需先进入 bootloader（设备信息 → Bootloader）。</p>
          <div class="filerow">
            <input class="input mono" id="fbPart" placeholder="分区名，如 boot" spellcheck="false">
            <input class="input" id="fbImg" placeholder="本地镜像路径" spellcheck="false">
          </div>
          <div class="filerow">
            <button class="btn" id="fbPlan">预检</button>
            <button class="btn btn-danger" id="fbGo" disabled>刷入</button>
          </div>
          <pre class="console hidden" id="fbOut"></pre>
        </section>
      </div>
    </div>
    <section class="card">
      <div class="panel-head"><h2>镜像分析</h2><span class="tag" id="anaKind">未选择</span></div>
      <div class="filerow">
        <button class="btn btn-primary" id="anaPick">选择镜像</button>
        <span class="path" id="anaName">支持 GPT / super / payload / boot / vbmeta / sparse，可拖进来</span>
      </div>
      <div id="anaBody"></div>
    </section>`;

  const tableBox = $("#partTable");
  let parts = [];

  const loadParts = async () => {
    tableBox.innerHTML = '<p class="empty-inline">读取中…</p>';
    try {
      const r = await api("/api/part/table");
      parts = r.partitions || [];
      $("#partInfo").textContent = `${parts.length} 个分区 · 备份到 ${r.backup_dir}`;
      renderParts();
    } catch (e) {
      tableBox.innerHTML = `<div class="alert">${esc(e.message)}${e.hint ? `<br><span class="meta">${esc(e.hint)}</span>` : ""}</div>`;
    }
  };

  const renderParts = () => {
    const filter = ($("#partFilter").value || "").trim().toLowerCase();
    const list = parts.filter((p) => !filter || p.name.toLowerCase().includes(filter));
    tableBox.innerHTML = `<div class="table-wrap"><table><thead><tr><th>分区</th><th>大小</th><th style="width:140px"></th></tr></thead><tbody>
      ${list.map((p) => `<tr><td class="mono">${esc(p.name)}</td><td>${esc(p.size_text)}</td>
        <td class="nowrap"><button class="btn btn-sm" data-backup="${esc(p.name)}">备份</button>
        <button class="btn btn-sm" data-fill="${esc(p.name)}">还原</button></td></tr>`).join("")}
    </tbody></table></div>`;
    tableBox.querySelectorAll("button[data-backup]").forEach((b) => {
      b.onclick = async () => {
        const name = b.dataset.backup;
        if (!confirm(`备份 ${name}？期间不要拔线。`)) return;
        b.disabled = true; b.textContent = "备份中…";
        try {
          const r = await api("/api/part/backup", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) });
          toast(`已备份 ${name}（${r.size_text}）→ ${r.local_path}`);
        } catch (e) { toast("备份失败：" + e.message, true); }
        finally { b.disabled = false; b.textContent = "备份"; }
      };
    });
    tableBox.querySelectorAll("button[data-fill]").forEach((b) => {
      b.onclick = () => { $("#restorePart").value = b.dataset.fill; $("#restoreImg").focus(); };
    });
  };

  const showOut = (el, data) => { el.classList.remove("hidden"); el.textContent = JSON.stringify(data, null, 2); };

  $("#partRefresh").onclick = loadParts;
  $("#partFilter").oninput = () => { if (parts.length) renderParts(); };
  $("#restorePlan").onclick = async () => {
    const name = $("#restorePart").value.trim();
    const path = $("#restoreImg").value.trim();
    if (!name || !path) return toast("先填分区名和镜像路径", true);
    try {
      const plan = await api("/api/part/plan", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "restore", name, path }) });
      showOut($("#restoreOut"), plan);
      $("#restoreGo").disabled = !plan.executable;
      if (!plan.executable) toast("计划被拦截，原因见输出", true);
    } catch (e) { showOut($("#restoreOut"), { error: e.message, hint: e.hint }); $("#restoreGo").disabled = true; }
  };
  $("#restoreGo").onclick = async () => {
    const name = $("#restorePart").value.trim();
    const path = $("#restoreImg").value.trim();
    if (!confirm(`把 ${path} 写进 ${name}？覆盖后无法撤销。`)) return;
    const btn = $("#restoreGo");
    btn.disabled = true; btn.textContent = "写入中…";
    try {
      const r = await api("/api/part/restore", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, path }) });
      showOut($("#restoreOut"), r);
      toast(r.ok ? "已写入并通过回读校验" : "写入后校验失败，见输出", !r.ok);
    } catch (e) { toast("失败：" + e.message, true); }
    finally { btn.disabled = false; btn.textContent = "还原"; }
  };
  $("#fbPlan").onclick = async () => {
    const part = $("#fbPart").value.trim();
    const image = $("#fbImg").value.trim();
    if (!part || !image) return toast("先填分区名和镜像路径", true);
    try {
      const plan = await api("/api/flash", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ part, image, dry_run: true }) });
      showOut($("#fbOut"), plan);
      $("#fbGo").disabled = false;
    } catch (e) { showOut($("#fbOut"), { error: e.message, hint: e.hint }); }
  };
  $("#fbGo").onclick = async () => {
    const part = $("#fbPart").value.trim();
    const image = $("#fbImg").value.trim();
    if (!confirm(`fastboot flash ${part} ${image}？`)) return;
    const btn = $("#fbGo");
    btn.disabled = true; btn.textContent = "刷入中…";
    try {
      const r = await api("/api/flash", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ part, image }) });
      showOut($("#fbOut"), r);
      toast(r.ok ? "刷入完成" : "刷入失败，见输出", !r.ok);
    } catch (e) { toast("失败：" + e.message, true); }
    finally { btn.disabled = false; btn.textContent = "刷入"; }
  };

  bindAnalyzer();
}

/* ================= 一键 ROOT ================= */
async function renderRoot(main) {
  main.innerHTML = head("一键 ROOT", "root 状态、管理器识别与模块管理") + `
    <div class="grid2">
      <section class="card">
        <div class="panel-head"><h2>ROOT 状态</h2><button class="btn" id="rootRefresh">重新探测</button></div>
        <div class="info-list" id="rootInfo"></div>
        <pre class="console hidden" id="rootOut"></pre>
      </section>
      <section class="card">
        <div class="panel-head"><h2>模块</h2><button class="btn" id="modRefresh">刷新</button></div>
        <p class="meta" id="modManager">读取中…</p>
        <div class="filerow">
          <input class="input" id="modZip" placeholder="模块 zip 的本地路径" spellcheck="false">
          <button class="btn" id="modInstall">安装</button>
          <button class="btn" id="modLog">日志</button>
        </div>
        <div id="modList" style="margin-top:10px"></div>
        <pre class="console hidden" id="modLogOut"></pre>
      </section>
    </div>`;

  const loadRoot = async () => {
    try {
      const r = await api("/api/root");
      const rows = [
        ["状态", r.available ? "已授权" : "未授权"],
        ["方式", r.method || "—"],
        ["管理器", `${r.manager || "未识别"} ${r.version || ""}`.trim()],
        ["su 路径", r.su_path || "—"],
        ["说明", r.reason || "—"],
      ];
      $("#rootInfo").innerHTML = rows.map(([k, v]) =>
        `<div class="row2"><span class="k">${esc(k)}</span><span class="v ${k === "su 路径" ? "mono" : ""}" title="${esc(v)}">${esc(v)}</span></div>`).join("");
      if (!r.available) toast("没有检测到可用的 root", true);
    } catch (e) {
      $("#rootInfo").innerHTML = `<div class="alert">${esc(e.message)}${e.hint ? `<br><span class="meta">${esc(e.hint)}</span>` : ""}</div>`;
    }
  };

  const loadModules = async () => {
    const box = $("#modList");
    box.innerHTML = '<p class="empty-inline">读取中…</p>';
    try {
      const r = await api("/api/modules");
      $("#modManager").textContent = r.manager.name ? `管理器：${r.manager.name} ${r.manager.version || ""}` : "没有识别到 root 管理器";
      if (!r.modules.length) { box.innerHTML = '<p class="empty-inline">没有已安装模块</p>'; return; }
      box.innerHTML = `<div class="table-wrap" style="max-height:320px"><table><thead><tr><th>模块</th><th>版本</th><th>状态</th><th></th></tr></thead><tbody>
        ${r.modules.map((m) => `<tr><td class="mono">${esc(m.name)}</td><td>${esc(m.version || "—")}</td>
          <td>${m.enabled ? "启用" : '<span class="muted">禁用</span>'}${m.pending_remove ? " · 待卸载" : ""}</td>
          <td class="nowrap"><button class="btn btn-sm" data-toggle="${esc(m.name)}" data-on="${m.enabled ? "0" : "1"}">${m.enabled ? "禁用" : "启用"}</button>
          <button class="btn btn-sm" data-remove="${esc(m.name)}">卸载</button></td></tr>`).join("")}
      </tbody></table></div>`;
      box.querySelectorAll("button[data-toggle]").forEach((b) => {
        b.onclick = async () => {
          b.disabled = true;
          try {
            const r2 = await api("/api/modules/toggle", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: b.dataset.toggle, enabled: b.dataset.on === "1" }) });
            toast(r2.message, !r2.ok);
            loadModules();
          } catch (e) { toast(e.message, true); b.disabled = false; }
        };
      });
      box.querySelectorAll("button[data-remove]").forEach((b) => {
        b.onclick = async () => {
          if (!confirm(`标记卸载 ${b.dataset.remove}？重启后生效。`)) return;
          b.disabled = true;
          try {
            const r2 = await api("/api/modules/remove", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: b.dataset.remove }) });
            toast(r2.message, !r2.ok);
            loadModules();
          } catch (e) { toast(e.message, true); b.disabled = false; }
        };
      });
    } catch (e) {
      box.innerHTML = `<div class="alert">${esc(e.message)}${e.hint ? `<br><span class="meta">${esc(e.hint)}</span>` : ""}</div>`;
    }
  };

  $("#rootRefresh").onclick = async () => { await loadRoot(); await loadModules(); };
  $("#modRefresh").onclick = loadModules;
  $("#modInstall").onclick = async () => {
    const path = $("#modZip").value.trim();
    if (!path) return toast("先填模块 zip 的路径", true);
    const btn = $("#modInstall");
    btn.disabled = true; btn.textContent = "安装中…";
    try {
      const r = await api("/api/modules/install", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path }) });
      toast(r.message, !r.ok);
      if (r.ok) loadModules();
    } catch (e) { toast("失败：" + e.message, true); }
    finally { btn.disabled = false; btn.textContent = "安装"; }
  };
  $("#modLog").onclick = async () => {
    const out = $("#modLogOut");
    out.classList.remove("hidden");
    out.textContent = "读取中…";
    try { const r = await api("/api/modules/log"); out.textContent = r.log || "(空)"; }
    catch (e) { out.textContent = "失败：" + e.message; }
  };

  await loadRoot();
  await loadModules();
}

/* ================= 投屏 / 固件（占位） ================= */
async function renderCast(main) {
  main.innerHTML = head("投屏", "集成 scrcpy 的 USB 投屏") + `
    <section class="card">
      <p class="todo-why">投屏依赖 scrcpy 的私有二进制，本仓库不打包第三方可执行文件。</p>
      <ul class="todo-list">
        <li>全自动投屏（自动选择设备与编码器）</li>
        <li>虚拟按键 / 自定义分辨率与帧率</li>
        <li>窗口置顶、屏幕常亮</li>
      </ul>
      <p class="meta">把 scrcpy.exe 放到 tools/ 目录后即可接上；在那之前这里不假装能用。</p>
    </section>`;
}

async function renderFirmware(main) {
  main.innerHTML = head("固件下载", "常用刷机包与官方固件") + `
    <section class="card">
      <p class="todo-why">固件源依赖厂商接口，随时可能变更，也不适合硬编码在客户端里。</p>
      <ul class="todo-list">
        <li>按机型查询官方固件与校验值</li>
        <li>多线程下载、断点续传</li>
        <li>下载后自动校验并进入刷机计划</li>
      </ul>
      <p class="meta">在接入可信下载源之前，这一页只说明现状。</p>
    </section>`;
}

/* ================= 软件管理 ================= */
async function renderApps(main) {
  main.innerHTML = head("软件管理", "安装、冻结、提取与卸载应用") + `
    <section class="card">
      <div class="filerow" style="margin-bottom:10px">
        <div class="segmented" id="appScope">
          <button class="active" data-all="0">第三方</button>
          <button data-all="1">全部</button>
        </div>
        <input class="input" id="appFilter" placeholder="筛选包名" spellcheck="false">
        <span class="meta" id="appCount" style="padding:0"></span>
      </div>
      <div id="appTable"><p class="empty-inline">选择范围后自动读取</p></div>
    </section>`;

  let scopeAll = false;
  let packages = [];

  const render = () => {
    const box = $("#appTable");
    const filter = $("#appFilter").value.trim().toLowerCase();
    const list = packages.filter((p) => !filter || p.toLowerCase().includes(filter));
    if (!list.length) {
      box.innerHTML = '<p class="empty-inline">没有匹配的应用</p>';
      return;
    }
    box.innerHTML = `<div class="table-wrap"><table><thead><tr><th>包名</th><th style="width:260px"></th></tr></thead><tbody>
      ${list.map((p) => `<tr><td class="mono">${esc(p)}</td><td class="nowrap">
        <button class="btn btn-sm" data-op="freeze" data-pkg="${esc(p)}">冻结</button>
        <button class="btn btn-sm" data-op="unfreeze" data-pkg="${esc(p)}">解冻</button>
        <button class="btn btn-sm" data-op="extract" data-pkg="${esc(p)}">提取</button>
        <button class="btn btn-sm btn-danger" data-op="uninstall" data-pkg="${esc(p)}">卸载</button>
      </td></tr>`).join("")}</tbody></table></div>`;
    box.querySelectorAll("button[data-pkg]").forEach((b) => {
      b.onclick = async () => {
        const pkg = b.dataset.pkg, op = b.dataset.op;
        if (op === "uninstall" && !confirm(`卸载 ${pkg}？`)) return;
        b.disabled = true;
        try {
          const url = op === "freeze" ? `/api/app/freeze?pkg=${encodeURIComponent(pkg)}&on=0`
            : op === "unfreeze" ? `/api/app/freeze?pkg=${encodeURIComponent(pkg)}&on=1`
            : op === "extract" ? `/api/app/extract?pkg=${encodeURIComponent(pkg)}`
            : `/api/app/uninstall?pkg=${encodeURIComponent(pkg)}`;
          const r = await api(url);
          toast(r.message, !r.ok);
          if (op === "uninstall" && r.ok) b.closest("tr").remove();
        } catch (e) { toast(e.message, true); }
        finally { b.disabled = false; }
      };
    });
  };

  const load = async () => {
    const box = $("#appTable");
    box.innerHTML = '<p class="empty-inline">读取中…</p>';
    try {
      const data = await api("/api/app/list" + (scopeAll ? "?all=1" : ""));
      packages = data.packages || [];
      $("#appCount").textContent = `${data.count} 个`;
      render();
    } catch (e) { box.innerHTML = `<div class="alert">${esc(e.message)}</div>`; }
  };

  $("#appScope").querySelectorAll("button").forEach((b) => {
    b.onclick = () => {
      scopeAll = b.dataset.all === "1";
      $("#appScope").querySelectorAll("button").forEach((x) => x.classList.toggle("active", x === b));
      load();
    };
  });
  $("#appFilter").oninput = () => { if (packages.length) render(); };
  await load();
}

/* ================= 文件管理 ================= */
async function renderFiles(main) {
  main.innerHTML = head("文件管理", "设备文件浏览、拉取与 APK 安装") + `
    <section class="card">
      <div class="filerow">
        <button class="btn" id="fileUp">↑ 上级</button>
        <input class="input mono" id="filePath" value="/sdcard" spellcheck="false">
        <button class="btn" id="fileGo">打开</button>
        <label class="chk"><input type="checkbox" id="fileRoot"> root 浏览</label>
      </div>
      <div class="filerow" style="margin-top:8px">
        <button class="btn btn-sm" data-jump="/sdcard">/sdcard</button>
        <button class="btn btn-sm" data-jump="/data">/data</button>
        <button class="btn btn-sm" data-jump="/system">/system</button>
      </div>
      <div id="fileTable" style="margin-top:12px"><p class="empty-inline">输入路径后点「打开」</p></div>
      <pre class="console hidden" id="fileView"></pre>
    </section>
    <section class="card">
      <h2>安装 APK</h2>
      <div class="filerow">
        <button class="btn btn-primary" id="pickApk">选择 APK</button>
        <span class="path" id="apkName">未选择</span>
        <span class="meta" id="apkResult" style="padding:0"></span>
      </div>
    </section>`;

  const box = $("#fileTable");
  const view = $("#fileView");
  const rootFlag = () => ($("#fileRoot").checked ? "&root=1" : "");

  const load = async () => {
    const path = $("#filePath").value.trim() || "/sdcard";
    box.innerHTML = '<p class="empty-inline">读取中…</p>';
    view.classList.add("hidden");
    try {
      const r = await api(`/api/file/ls?path=${encodeURIComponent(path)}${rootFlag()}`);
      box.innerHTML = `<div class="table-wrap"><table><thead><tr><th>权限</th><th>大小</th><th>名称</th><th style="width:120px"></th></tr></thead><tbody>
        ${r.items.map((i) => `<tr><td class="mono muted">${esc(i.perm)}</td><td>${esc(i.size)}</td>
          <td class="mono">${i.dir ? `<a href="#" class="flink" data-dir="${esc(i.name)}">${esc(i.name)}/</a>` : esc(i.name)}</td>
          <td class="nowrap">${i.dir ? "" : `<button class="btn btn-sm" data-view="${esc(i.name)}">查看</button>
          <button class="btn btn-sm" data-pull="${esc(i.name)}">拉取</button>`}</td></tr>`).join("")}
      </tbody></table></div>`;
      box.querySelectorAll("a[data-dir]").forEach((a) => {
        a.onclick = (ev) => { ev.preventDefault(); $("#filePath").value = path.replace(/\/$/, "") + "/" + a.dataset.dir; load(); };
      });
      box.querySelectorAll("button[data-view]").forEach((b) => {
        b.onclick = async () => {
          view.classList.remove("hidden");
          view.textContent = "读取中…";
          try {
            const d = await api(`/api/file/read?path=${encodeURIComponent(path.replace(/\/$/, "") + "/" + b.dataset.view)}${rootFlag()}`);
            view.textContent = d.text + (d.truncated ? "\n\n…… 已截断" : "");
          } catch (e) { view.textContent = "读取失败：" + e.message; }
        };
      });
      box.querySelectorAll("button[data-pull]").forEach((b) => {
        b.onclick = async () => {
          b.disabled = true;
          try {
            const r2 = await api(`/api/file/pull?remote=${encodeURIComponent(path.replace(/\/$/, "") + "/" + b.dataset.pull)}${rootFlag()}`);
            toast(r2.message || (r2.ok ? "已拉取" : "拉取失败"), !r2.ok);
          } catch (e) { toast(e.message, true); }
          finally { b.disabled = false; }
        };
      });
    } catch (e) { box.innerHTML = `<div class="alert">${esc(e.message)}${e.hint ? `<br><span class="meta">${esc(e.hint)}</span>` : ""}</div>`; }
  };

  $("#fileGo").onclick = load;
  $("#filePath").onkeydown = (e) => { if (e.key === "Enter") load(); };
  $("#fileRoot").onchange = load;
  $("#fileUp").onclick = () => {
    const cur = $("#filePath").value.trim().replace(/\/$/, "");
    if (!cur || cur === "/") return;
    $("#filePath").value = cur.slice(0, cur.lastIndexOf("/")) || "/";
    load();
  };
  main.querySelectorAll("button[data-jump]").forEach((b) => {
    b.onclick = () => { $("#filePath").value = b.dataset.jump; $("#fileRoot").checked = b.dataset.jump !== "/sdcard"; load(); };
  });

  const apkInput = document.createElement("input");
  apkInput.type = "file"; apkInput.accept = ".apk";
  apkInput.onchange = async () => {
    const f = apkInput.files[0];
    if (!f) return;
    $("#apkName").textContent = f.name;
    $("#apkResult").textContent = "上传并安装中…";
    try {
      const r = await api("/api/app/install?name=" + encodeURIComponent(f.name), {
        method: "POST", body: f, headers: { "Content-Type": "application/vnd.android.package-archive" },
      });
      $("#apkResult").textContent = r.message;
    } catch (e) { $("#apkResult").textContent = "失败：" + e.message; }
  };
  $("#pickApk").onclick = () => apkInput.click();

  await load();
}

/* ================= 基带备份 ================= */
async function renderBackup(main) {
  main.innerHTML = head("基带备份", "把 modem / 基带相关分区读出来存到电脑") + `
    <section class="card">
      <div class="filerow" style="margin-bottom:10px">
        <div class="segmented" id="bkScope">
          <button class="active" data-all="0">基带相关</button>
          <button data-all="1">全部分区</button>
        </div>
        <button class="btn" id="bkRefresh">读取分区表</button>
        <span class="meta" id="bkInfo" style="padding:0">需要 root</span>
      </div>
      <p class="meta">基带分区写错会导致无信号、无 IMEI。备份是只读操作；还原请去「刷机」页，看清分区名再动手。</p>
      <div id="bkTable"><p class="empty-inline">点「读取分区表」开始</p></div>
    </section>`;

  let all = false;
  let parts = [];
  const KEYWORDS = ["modem", "baseband", "radio", "fsg", "fsc", "modemst"];

  const load = async () => {
    const box = $("#bkTable");
    box.innerHTML = '<p class="empty-inline">读取中…</p>';
    try {
      const r = await api("/api/part/table");
      parts = r.partitions || [];
      $("#bkInfo").textContent = `${parts.length} 个分区 · 备份目录 ${r.backup_dir}`;
      render();
    } catch (e) {
      box.innerHTML = `<div class="alert">${esc(e.message)}${e.hint ? `<br><span class="meta">${esc(e.hint)}</span>` : ""}</div>`;
    }
  };

  const render = () => {
    const list = all ? parts : parts.filter((p) => KEYWORDS.some((k) => p.name.toLowerCase().includes(k)));
    const box = $("#bkTable");
    if (!list.length) { box.innerHTML = '<p class="empty-inline">没有匹配的基带分区；切到「全部分区」看看</p>'; return; }
    box.innerHTML = `<div class="table-wrap"><table><thead><tr><th>分区</th><th>大小</th><th style="width:120px"></th></tr></thead><tbody>
      ${list.map((p) => `<tr><td class="mono">${esc(p.name)}</td><td>${esc(p.size_text)}</td>
        <td><button class="btn btn-sm" data-bk="${esc(p.name)}">备份</button></td></tr>`).join("")}
    </tbody></table></div>`;
    box.querySelectorAll("button[data-bk]").forEach((b) => {
      b.onclick = async () => {
        const name = b.dataset.bk;
        if (!confirm(`备份 ${name}？`)) return;
        b.disabled = true; b.textContent = "备份中…";
        try {
          const r = await api("/api/part/backup", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) });
          toast(`已备份 ${name}（${r.size_text}）\n${r.local_path}`);
        } catch (e) { toast("备份失败：" + e.message, true); }
        finally { b.disabled = false; b.textContent = "备份"; }
      };
    });
  };

  $("#bkScope").querySelectorAll("button").forEach((b) => {
    b.onclick = () => {
      all = b.dataset.all === "1";
      $("#bkScope").querySelectorAll("button").forEach((x) => x.classList.toggle("active", x === b));
      render();
    };
  });
  $("#bkRefresh").onclick = load;
  await load();
}

/* ================= 杂项 ================= */
async function renderMisc(main) {
  main.innerHTML = head("杂项", "终端、本地工具与脱机修补") + `
    <div class="grid2">
      <section class="card" style="display:flex;flex-direction:column">
        <div class="panel-head"><h2>终端</h2>
          <label class="chk"><input type="checkbox" id="termRoot"> root</label>
        </div>
        <div class="console term" id="termOut" style="margin-top:0"></div>
        <div class="filerow" style="margin-top:10px">
          <input class="input mono" id="termCmd" placeholder="输入命令，回车执行" spellcheck="false" autocomplete="off">
          <button class="btn btn-primary" id="termRun">执行</button>
          <button class="btn" id="termClear">清屏</button>
        </div>
        <p class="meta">命令直接交给设备 shell；勾选 root 时走 su -c。↑ / ↓ 翻历史。</p>
      </section>
      <div class="stack">
        <section class="card">
          <h2>本地工具</h2>
          <div class="filerow">
            <input class="input" id="toolPath" placeholder="文件路径（电脑上的）" spellcheck="false">
            <select class="select" id="toolOp" style="flex:0 0 130px">
              <option value="hash">计算哈希</option>
              <option value="bootunpack">拆 boot</option>
              <option value="sparsepack">打包 sparse</option>
              <option value="gptxml">GPT 转 XML</option>
              <option value="supermake">合并 super</option>
              <option value="split">拆分文件</option>
              <option value="join">合并分片</option>
            </select>
          </div>
          <div class="filerow">
            <input class="input" id="toolArg" placeholder="输出路径 / 大小 / 名字=文件;名字=文件" spellcheck="false">
            <button class="btn" id="toolRun">执行</button>
          </div>
          <pre class="console hidden" id="toolOut"></pre>
        </section>
        <section class="card">
          <h2>脱机修补</h2>
          <div class="filerow">
            <input class="input" id="patchPath" placeholder="boot.img 或 vbmeta.img 路径" spellcheck="false">
            <button class="btn" id="patchBoot">拆 boot</button>
            <button class="btn" id="patchAvb">看 vbmeta</button>
          </div>
          <pre class="console hidden" id="patchOut"></pre>
        </section>
      </div>
    </div>`;

  /* 终端 */
  const out = $("#termOut");
  const hist = [];
  let pos = 0;
  const line = (text, cls) => {
    const div = document.createElement("div");
    if (cls) div.className = cls;
    div.textContent = text;
    out.appendChild(div);
    while (out.childNodes.length > 400) out.removeChild(out.firstChild);
    out.scrollTop = out.scrollHeight;
  };
  const run = async () => {
    const cmd = $("#termCmd").value.trim();
    if (!cmd) return;
    hist.push(cmd); pos = hist.length;
    $("#termCmd").value = "";
    line((($("#termRoot").checked) ? "# " : "$ ") + cmd, "cmd");
    try {
      const r = await api(`/api/shell?cmd=${encodeURIComponent(cmd)}${$("#termRoot").checked ? "&root=1" : ""}`);
      line((r.out || "") + (r.err ? (r.out ? "\n" : "") + r.err : "") || "(无输出)", r.ok ? "" : "bad");
      line(`[退出码 ${r.code} · ${r.duration}s · ${r.root ? "root" : "shell"}]`, "meta");
    } catch (e) { line("[失败] " + e.message, "bad"); }
  };
  $("#termRun").onclick = run;
  $("#termClear").onclick = () => { out.innerHTML = ""; };
  $("#termCmd").onkeydown = (e) => {
    if (e.key === "Enter") { e.preventDefault(); run(); }
    if (e.key === "ArrowUp") { e.preventDefault(); if (pos > 0) { pos--; $("#termCmd").value = hist[pos] || ""; } }
    if (e.key === "ArrowDown") { e.preventDefault(); if (pos < hist.length - 1) { pos++; $("#termCmd").value = hist[pos] || ""; } else { pos = hist.length; $("#termCmd").value = ""; } }
  };
  line("就绪。输入命令后回车。", "meta");

  /* 本地工具 */
  $("#toolRun").onclick = async () => {
    const target = $("#toolPath").value.trim();
    const op = $("#toolOp").value;
    const arg = $("#toolArg").value.trim();
    const o = $("#toolOut");
    if (!target) return toast("先填文件路径", true);
    o.classList.remove("hidden"); o.textContent = "执行中…";
    try {
      const r = await api(`/api/tool?op=${op}&path=${encodeURIComponent(target)}&arg=${encodeURIComponent(arg)}`);
      o.textContent = JSON.stringify(r.result, null, 2);
    } catch (e) { o.textContent = "失败：" + e.message; }
  };

  /* 脱机修补 */
  const patch = async (op) => {
    const p = $("#patchPath").value.trim();
    if (!p) return toast("先填路径", true);
    const o = $("#patchOut");
    o.classList.remove("hidden"); o.textContent = "处理中…";
    try {
      if (op === "avb") {
        const r = await api("/api/analyze?path=" + encodeURIComponent(p));
        o.textContent = JSON.stringify(r, null, 2);
        return;
      }
      const r = await api(`/api/tool?op=bootunpack&path=${encodeURIComponent(p)}&arg=${encodeURIComponent(p + "-out")}`);
      o.textContent = JSON.stringify(r.result, null, 2);
    } catch (e) { o.textContent = "失败：" + e.message; }
  };
  $("#patchBoot").onclick = () => patch("boot");
  $("#patchAvb").onclick = () => patch("avb");
}

/* ================= 设置 ================= */
async function renderSettings(main) {
  const saved = localStorage.getItem("iris-theme") || "auto";
  main.innerHTML = head("设置", "外观、存储位置与版本信息") + `
    <div class="grid2">
      <section class="card">
        <h2>外观</h2>
        <p class="meta">跟随系统时会读取 Windows 的浅色 / 深色设置。</p>
        <div class="segmented" id="themeSeg">
          <button data-theme="auto" class="${saved === "auto" ? "active" : ""}">跟随系统</button>
          <button data-theme="light" class="${saved === "light" ? "active" : ""}">浅色</button>
          <button data-theme="dark" class="${saved === "dark" ? "active" : ""}">深色</button>
        </div>
      </section>
      <section class="card">
        <h2>存储位置</h2>
        <div class="info-list">
          <div class="row2"><span class="k">截图 / 录屏</span><span class="v mono" id="setShots">shots/</span></div>
          <div class="row2"><span class="k">分区备份</span><span class="v mono" id="setBackup">backups/</span></div>
        </div>
      </section>
    </div>
    <section class="card">
      <h2>关于</h2>
      <p class="about-p">
        Iris 工具箱 · 面向 Android 设备的多功能工具链。<br>
        设计原则：计划式执行、结构化结果、探测优先、核心与界面分离。<br>
        本工具按 GPL-3.0 发布；参考了 VioletToolBox 的设计与算法知识，未打包任何第三方二进制。
      </p>
      <div class="filerow" style="margin-top:10px">
        <span class="tag" id="setVersion">v0.3.0</span>
        <button class="btn" id="openShots">打开截图目录</button>
      </div>
    </section>`;

  $("#themeSeg").querySelectorAll("button").forEach((b) => {
    b.onclick = () => {
      const t = b.dataset.theme;
      if (t === "auto") document.documentElement.removeAttribute("data-theme");
      else document.documentElement.dataset.theme = t;
      localStorage.setItem("iris-theme", t);
      $("#themeSeg").querySelectorAll("button").forEach((x) => x.classList.toggle("active", x === b));
    };
  });

  try {
    const info = await api("/api/info").catch(() => null);
    if (info) {
      $("#setShots").textContent = "shots/";
      $("#setBackup").textContent = "backups/";
    }
  } catch { /* ignore */ }

  $("#setVersion").textContent = "v" + (window.__IRIS_VERSION__ || "0.3.0");
  $("#openShots").onclick = () => toast("截图与备份在程序目录的 shots/ 与 backups/ 下");
}

/* ================= 镜像分析 ================= */
let anaData = null;

function bindAnalyzer() {
  const input = $("#file");
  input.value = "";
  input.onchange = () => input.files[0] && uploadImage(input.files[0]);
  $("#anaPick").onclick = () => input.click();
  window.ondragover = (e) => e.preventDefault();
  window.ondrop = (e) => {
    e.preventDefault();
    const f = e.dataTransfer?.files[0];
    if (f) uploadImage(f);
  };
}

async function uploadImage(file) {
  $("#anaName").textContent = `${file.name} · ${(file.size / 1048576).toFixed(1)} MB`;
  $("#anaKind").textContent = "分析中…";
  $("#anaBody").innerHTML = "";
  try {
    const data = await api("/api/upload?name=" + encodeURIComponent(file.name), {
      method: "POST", body: file, headers: { "Content-Type": "application/octet-stream" },
    });
    anaData = data;
    renderAnalysis(data);
  } catch (e) {
    $("#anaKind").textContent = "失败";
    $("#anaBody").innerHTML = `<div class="alert">${esc(e.message)}</div>`;
  }
}

function renderAnalysis(data) {
  const kindName = { gpt: "GPT", lp: "super", payload: "payload", boot: "boot", avb: "vbmeta", sparse: "sparse" }[data.kind] || data.kind;
  $("#anaKind").textContent = kindName;
  const body = $("#anaBody");

  if (data.kind === "payload") {
    const p = data.payload;
    body.innerHTML = `<p class="meta">payload v${p.version} · 块 ${p.block_size}B · ${p.partition_count} 个分区</p>
      <div class="table-wrap"><table><thead><tr><th>分区</th><th>解包后</th><th>类型</th><th></th></tr></thead><tbody>
      ${p.partitions.map((x) => `<tr><td class="mono">${esc(x.name)}</td><td>${human(x.size_bytes)}</td>
        <td class="muted">${esc(x.operations.join(", "))}</td>
        <td>${x.extractable ? `<button class="btn btn-sm" data-part="${esc(x.name)}">提取</button>` : "—"}</td></tr>`).join("")}
      </tbody></table></div>`;
    body.querySelectorAll("button[data-part]").forEach((b) => {
      b.onclick = () => extractPart(data.ticket, b.dataset.part, b);
    });
    return;
  }

  if (data.kind === "lp") {
    const m = data.metadata;
    body.innerHTML = `<p class="meta">LP ${m.header.version} · 块 ${m.geometry.logical_block_size}B · 逻辑容量 ${human(m.logical_size)}</p>
      <div class="table-wrap"><table><thead><tr><th>分区</th><th>大小</th><th>extent</th><th></th></tr></thead><tbody>
      ${m.partitions.map((p) => `<tr><td class="mono">${esc(p.name)}</td><td>${p.size_human}</td>
        <td class="muted">${p.extent_count}</td>
        <td>${data.ticket ? `<button class="btn btn-sm" data-part="${esc(p.name)}">提取</button>` : ""}</td></tr>`).join("")}
      </tbody></table></div>`;
    body.querySelectorAll("button[data-part]").forEach((b) => {
      b.onclick = () => extractPart(data.ticket, b.dataset.part, b);
    });
    return;
  }

  if (data.kind === "boot") {
    const b = data.boot;
    body.innerHTML = `<div class="info-list">
      ${[["header", "v" + b.header_version], ["内核", human(b.kernel_size) + " @ " + b.kernel_offset],
         ["ramdisk", human(b.ramdisk_size) + " @ " + b.ramdisk_offset], ["系统版本", b.os_version]]
        .map(([k, v]) => `<div class="row2"><span class="k">${esc(k)}</span><span class="v">${esc(v)}</span></div>`).join("")}
      </div><p class="meta">cmdline：${esc(b.cmdline || "—")}</p>`;
    return;
  }

  if (data.kind === "avb") {
    const a = data.avb;
    body.innerHTML = `<div class="info-list">
      ${[["算法", a.algorithm], ["flags", "0x" + a.flags.toString(16)],
         ["verity", a.verity_disabled ? "已关闭" : "启用"], ["工具", a.release_string || "—"]]
        .map(([k, v]) => `<div class="row2"><span class="k">${esc(k)}</span><span class="v">${esc(v)}</span></div>`).join("")}
      </div>`;
    return;
  }

  if (data.kind === "gpt") {
    const t = data.table;
    body.innerHTML = `<p class="meta">扇区 ${t.sector_size}B · ${t.source === "primary" ? "主表" : "备份表"}</p>
      <div class="table-wrap"><table><thead><tr><th>#</th><th>名称</th><th>起始 LBA</th><th>大小</th></tr></thead><tbody>
      ${t.partitions.map((p) => `<tr><td class="muted">${p.index}</td><td class="mono">${esc(p.name)}</td>
        <td class="mono">${p.first_lba}</td><td>${human(p.sectors * t.sector_size)}</td></tr>`).join("")}
      </tbody></table></div>`;
    return;
  }

  if (data.kind === "sparse") {
    const s = data.info;
    body.innerHTML = `<p class="meta">块 ${s.block_size}B · 展开后 ${human(s.expanded_size)} · ${s.total_chunks} 个 chunk</p>`;
  }
}

async function extractPart(ticket, part, btn) {
  const label = btn.textContent;
  btn.disabled = true; btn.textContent = "提取中…";
  try {
    const res = await fetch(`/api/extract?ticket=${encodeURIComponent(ticket)}&part=${encodeURIComponent(part)}`,
      { headers: { "X-Iris-Token": TOKEN } });
    if (!res.ok) throw new Error((await res.text()).slice(0, 160));
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = `${part}.img`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    toast(`已下载 ${part}.img`);
  } catch (e) { toast("提取失败：" + e.message, true); }
  finally { btn.textContent = label; btn.disabled = false; }
}

/* ---------------- 启动 ---------------- */
(function boot() {
  const saved = localStorage.getItem("iris-theme") || "auto";
  if (saved !== "auto") document.documentElement.dataset.theme = saved;
  $("#ver").textContent = window.__IRIS_VERSION__ ? "v" + window.__IRIS_VERSION__ : "";
  buildNav();
  show("device");
  refreshStatus();
})();
