const TOKEN = window.__IRIS_TOKEN__;
const EMBED = window.__IRIS_DATA__ || null;   // 单文件快照模式

async function api(path, options = {}) {
  if (EMBED) {
    const key = path.split("?")[0];
    if (EMBED[key] !== undefined) return EMBED[key];
    if (key === "/api/info" && EMBED["/api/info_error"]) throw new Error(EMBED["/api/info_error"]);
    throw new Error("这是导出的静态快照：该功能需要本地服务（双击 启动.bat）");
  }
  const res = await fetch(path, {
    ...options,
    headers: { "X-Iris-Token": TOKEN, ...(options.headers || {}) },
  });
  const text = await res.text();
  let data;
  try { data = JSON.parse(text); } catch { data = { error: text }; }
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function human(n) {
  const units = ["B", "KiB", "MiB", "GiB", "TiB"];
  let v = n, i = 0;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return (i === 0 ? v : v.toFixed(1)) + units[i];
}

/* ---------- 导航 ---------- */
document.querySelectorAll(".nav").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    btn.classList.add("active");
    $("#view-" + btn.dataset.view).classList.add("active");
    if (btn.dataset.view === "device") loadDevice(false);
  });
});

/* ---------- 状态栏 ---------- */
function setStatus({ connected, model, root, adb }) {
  $("#sb-led").classList.toggle("on", !!connected);
  $("#sb-device").textContent = connected ? "已连接" : "未连接";
  if (model !== undefined) $("#sb-model").textContent = model || "—";
  if (root !== undefined) $("#sb-root").textContent = root ? "已 ROOT" : "未 ROOT";
  if (adb !== undefined) $("#sb-adb").textContent = adb || "—";
}

/* ---------- 环境自检 ---------- */
async function loadDoctor() {
  const list = $("#doctor-list");
  const chips = $("#doctor-chips");
  list.innerHTML = '<div class="row"><i class="dot"></i><div class="k">检测中</div><div class="v"></div></div>';
  chips.innerHTML = "";

  try {
    const data = await api("/api/doctor");
    const n = (s) => data.checks.filter((c) => c.status === s).length;

    chips.innerHTML = [
      `<span class="chip fail"><i></i>${n("fail")} 失败</span>`,
      `<span class="chip warn"><i></i>${n("warn")} 警告</span>`,
      `<span class="chip ok"><i></i>${n("ok")} 通过</span>`,
    ].join("");

    list.innerHTML = data.checks.map((c) => `
      <div class="row ${c.status}">
        <i class="dot"></i>
        <div class="k">${esc(c.name)}</div>
        <div class="v">${esc(c.detail)}</div>
        ${c.hint && c.status !== "ok" ? `<div class="hint">${esc(c.hint)}</div>` : ""}
      </div>`).join("");

    const adbCheck = data.checks.find((c) => c.name === "adb");
    const m = adbCheck && adbCheck.detail.match(/version\s+([\d.]+)/i);
    setStatus({
      connected: data.checks.some((c) => c.name.startsWith("device ") && c.status === "ok"),
      adb: m ? m[1] : (adbCheck && adbCheck.status === "ok" ? "已就绪" : "未找到"),
    });
  } catch (e) {
    chips.innerHTML = '<span class="chip fail"><i></i>检测失败</span>';
    list.innerHTML = `<div class="row fail"><i class="dot"></i><div class="k">错误</div>
      <div class="v">${esc(e.message)}</div></div>`;
  }
}

/* ---------- 设备 ---------- */
const FIELDS = [
  ["序列号", (p) => p.serial],
  ["机型", (p) => `${p.brand || ""} ${p.model || ""}`.trim()],
  ["代号", (p) => p.codename],
  ["SoC", (p) => `${p.soc_manufacturer || ""} ${p.soc_model || ""}`.trim()],
  ["系统", (p) => `Android ${p.android_release || "?"} · SDK ${p.sdk || "?"}`],
  ["架构", (p) => p.abi],
  ["安全补丁", (p) => p.security_patch],
  ["槽位", (p) => (p.ab_update ? `A/B（${p.slot_suffix || "?"}）` : "单槽位")],
  ["ROOT", (p) => (p.root ? "是" : "否")],
  ["by-name 根", (p) => p.by_name_root || "未探测到"],
  ["块设备", (p) => p.block_device || "未知"],
  ["已知分区", (p) => (p.partitions ? `${Object.keys(p.partitions).length} 个` : "0")],
];

async function loadDevice(refresh) {
  const empty = $("#device-empty");
  const content = $("#device-content");
  try {
    const p = await api("/api/info" + (refresh ? "?refresh=1" : ""));
    empty.classList.add("hidden");
    content.classList.remove("hidden");

    $("#device-fields").innerHTML = FIELDS.map(([label, get]) =>
      `<div class="field"><em>${esc(label)}</em><b>${esc(get(p) || "—")}</b></div>`).join("");

    const rows = (p.probes || []).map((pr) => `
      <tr><td class="mono">${esc(pr.name)}</td>
          <td>${pr.ok ? '<span style="color:var(--ok)">✓</span>' : '<span style="color:var(--fail)">✗</span>'}</td>
          <td class="mono" style="color:var(--muted)">${esc(pr.evidence)}</td></tr>`).join("");

    $("#probe-table").innerHTML = `
      <table><thead><tr><th>探测项</th><th>结果</th><th>证据</th></tr></thead>
      <tbody>${rows}</tbody></table>`;

    setStatus({ connected: true, model: p.model || "—", root: !!p.root });
  } catch (e) {
    setStatus({ connected: false, model: "—", root: "—" });
    content.classList.add("hidden");
    empty.classList.remove("hidden");
    empty.querySelector("b").textContent = e.message;
  }
}

/* ---------- 镜像分析 ---------- */
const fileInput = $("#file");

$("#pick").addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => fileInput.files[0] && upload(fileInput.files[0]));

// 整窗口拖放
["dragenter", "dragover"].forEach((ev) => window.addEventListener(ev, (e) => e.preventDefault()));
window.addEventListener("drop", (e) => {
  e.preventDefault();
  const f = e.dataTransfer && e.dataTransfer.files[0];
  if (f) {
    document.querySelector('.nav[data-view="image"]').click();
    upload(f);
  }
});

async function upload(file) {
  const errBox = $("#image-error");
  const result = $("#image-result");

  $("#file-name").textContent = `${file.name} · ${(file.size / 1048576).toFixed(1)} MB`;

  if (EMBED) {
    result.classList.add("hidden");
    errBox.textContent = "静态快照不能解析新文件。要拖拽分析，请双击 启动.bat 启动本地服务。";
    errBox.classList.remove("hidden");
    return;
  }

  errBox.classList.add("hidden");
  $("#image-kind").textContent = "分析中…";
  $("#image-name").textContent = file.name;
  result.classList.remove("hidden");
  $("#image-body").innerHTML = "";

  try {
    const data = await api("/api/upload?name=" + encodeURIComponent(file.name), {
      method: "POST",
      body: file,
      headers: { "Content-Type": "application/octet-stream" },
    });
    renderImage(data);
  } catch (e) {
    $("#image-kind").textContent = "无法识别";
    errBox.textContent = e.message;
    errBox.classList.remove("hidden");
  }
}

async function extractPart(ticket, part, btn) {
  if (!ticket) {
    alert("当前是导出快照，不能提取。请用 Iris.bat 启动本地服务。");
    return;
  }
  const label = btn.textContent;
  btn.disabled = true;
  btn.textContent = "提取中…";
  try {
    const res = await fetch(
      `/api/extract?ticket=${encodeURIComponent(ticket)}&part=${encodeURIComponent(part)}`,
      { headers: { "X-Iris-Token": TOKEN } },
    );
    if (!res.ok) throw new Error((await res.text()).slice(0, 200) || `HTTP ${res.status}`);
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${part}.img`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
    btn.textContent = "已下载";
  } catch (e) {
    btn.textContent = label;
    btn.disabled = false;
    alert("提取失败：" + e.message);
    return;
  }
  setTimeout(() => {
    btn.textContent = label;
    btn.disabled = false;
  }, 2500);
}

function renderImage(data) {
  $("#image-kind").textContent =
    { gpt: "GPT 分区表", lp: "super 元数据", sparse: "sparse 镜像", payload: "payload.bin" }[data.kind] || data.kind;
  const body = $("#image-body");

  if (data.kind === "payload") {
    const p = data.payload;
    const rows = p.partitions.map((x) => `
      <tr><td class="mono">${esc(x.name)}</td><td>${human(x.size_bytes)}</td>
          <td style="color:var(--muted)">${x.operation_count}</td>
          <td style="color:var(--muted)">${esc(x.operations.join(", "))}</td>
          <td>${x.extractable
            ? `<button class="btn" data-part="${esc(x.name)}">提取</button>`
            : '<span style="color:var(--dim)">增量</span>'}</td></tr>`).join("");
    body.innerHTML = `
      <p class="meta">payload 版本 <b>${p.version}</b> · 块 <b>${p.block_size}B</b> ·
         <b>${p.partition_count}</b> 个分区</p>
      <div class="table-wrap"><table>
        <thead><tr><th>分区</th><th>解包后大小</th><th>操作数</th><th>类型</th><th>操作</th></tr></thead>
        <tbody>${rows}</tbody></table></div>`;
    body.querySelectorAll("button[data-part]").forEach((btn) => {
      btn.onclick = () => extractPart(data.ticket, btn.dataset.part, btn);
    });
    return;
  }

  if (data.kind === "gpt") {
    const t = data.table;
    const rows = t.partitions.map((p) => `
      <tr><td style="color:var(--muted)">${p.index}</td><td class="mono">${esc(p.name) || "(未命名)"}</td>
          <td class="mono" style="color:var(--muted)">${p.type.slice(0, 8)}</td>
          <td class="mono">${p.first_lba}</td><td>${human(p.sectors * t.sector_size)}</td></tr>`).join("");
    body.innerHTML = `
      <p class="meta">扇区 <b>${t.sector_size}B</b> · ${t.source === "primary" ? "主表" : "备份表"} ·
         CRC <b>${t.crc_ok ? "通过" : "异常"}</b> · 磁盘 <b>${esc(t.disk_guid)}</b></p>
      <div class="table-wrap"><table>
        <thead><tr><th>#</th><th>名称</th><th>类型</th><th>起始 LBA</th><th>大小</th></tr></thead>
        <tbody>${rows}</tbody></table></div>`;
  }

  if (data.kind === "lp") {
    const m = data.metadata;
    const rows = m.partitions.map((p) => `
      <tr><td class="mono">${esc(p.name)}</td><td>${p.size_human}</td>
          <td style="color:var(--muted)">${p.extent_count}</td>
          <td style="color:var(--muted)">${p.group_index}</td></tr>`).join("");
    body.innerHTML = `
      <p class="meta">版本 <b>${m.header.version}</b> · header <b>${m.header.header_size}B</b> ·
         块大小 <b>${m.geometry.logical_block_size}B</b> · 逻辑容量 <b>${human(m.logical_size)}</b>
         ${m.warnings.length ? ` · <b style="color:var(--warn)">${esc(m.warnings.join("；"))}</b>` : ""}</p>
      <div class="table-wrap"><table>
        <thead><tr><th>分区</th><th>大小</th><th>extent 数</th><th>组</th></tr></thead>
        <tbody>${rows}</tbody></table></div>`;
  }

  if (data.kind === "sparse") {
    const s = data.info;
    const stats = Object.entries(s.chunk_stats).map(([k, v]) => `${k} ×${v}`).join("，");
    body.innerHTML = `
      <p class="meta">块大小 <b>${s.block_size}B</b> · <b>${s.total_blocks}</b> 块 ·
         展开后 <b>${human(s.expanded_size)}</b> · <b>${s.total_chunks}</b> 个 chunk（${esc(stats)}）</p>`;
  }
}

/* ---------- 关于 ---------- */
$("#about-fields").innerHTML = [
  ["版本", `v${(window.__IRIS_VERSION__ || "0.2.0")}`],
  ["许可证", "GPL-3.0"],
  ["运行时", "Python 标准库，无第三方依赖"],
  ["数据", "全程本地处理，不上传"],
  ["第三方二进制", "不打包"],
  ["前端", "单页 HTML/CSS/JS + http.server"],
].map(([k, v]) => `<div class="field"><em>${esc(k)}</em><b>${esc(v)}</b></div>`).join("");

/* ---------- 主题 ---------- */
const THEMES = ["win", "light", "green", "dark"];

function applyTheme(name) {
  if (!THEMES.includes(name)) name = "win";
  if (name === "green") {
    document.body.removeAttribute("data-theme");
  } else {
    document.body.dataset.theme = name;
  }
  document.querySelectorAll(".theme-btn").forEach((b) =>
    b.setAttribute("aria-pressed", String(b.dataset.t === name)));
  try { localStorage.setItem("iris-theme", name); } catch (e) { /* file:// 可能禁止 */ }
}

document.querySelectorAll(".theme-btn").forEach((b) => {
  b.addEventListener("click", () => applyTheme(b.dataset.t));
});

try {
  applyTheme(localStorage.getItem("iris-theme") || "win");
} catch (e) {
  applyTheme("win");
}

/* ---------- 启动 ---------- */
$("#btn-doctor").addEventListener("click", loadDoctor);
$("#btn-refresh").addEventListener("click", () => loadDevice(true));

loadDoctor();
loadDevice(false);
