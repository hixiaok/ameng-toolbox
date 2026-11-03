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
const el = (html) => { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; };
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

/* ---------- 导航 ---------- */
document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    btn.classList.add("active");
    $("#view-" + btn.dataset.view).classList.add("active");
    if (btn.dataset.view === "device") loadDevice(false);
  });
});

/* ---------- 环境自检 ---------- */
const ICONS = { ok: "✓", warn: "!", fail: "✗" };

async function loadDoctor() {
  const list = $("#doctor-list");
  const summary = $("#doctor-summary");
  list.innerHTML = '<div class="card"><span class="icon">…</span><span class="key">检测中</span><span class="val"></span></div>';
  try {
    const data = await api("/api/doctor");
    const fails = data.checks.filter((c) => c.status === "fail").length;
    const warns = data.checks.filter((c) => c.status === "warn").length;
    summary.textContent = `${data.platform} · Python ${data.python} · ${fails} 项失败，${warns} 项警告`;

    list.innerHTML = "";
    for (const c of data.checks) {
      const card = el(`
        <div class="card ${c.status}">
          <span class="icon">${ICONS[c.status] || "?"}</span>
          <span class="key">${esc(c.name)}</span>
          <span class="val">${esc(c.detail)}</span>
        </div>`);
      if (c.hint && c.status !== "ok") {
        card.appendChild(el(`<div class="hint">↳ ${esc(c.hint)}</div>`));
      }
      list.appendChild(card);
    }
    const hasDevice = data.checks.some((c) => c.name.startsWith("device ") && c.status === "ok");
    setConn(hasDevice);
  } catch (e) {
    summary.textContent = "检测失败";
    list.innerHTML = `<div class="card fail"><span class="icon">✗</span><span class="key">错误</span><span class="val">${esc(e.message)}</span></div>`;
  }
}

function setConn(on) {
  $("#conn-dot").classList.toggle("on", on);
  $("#conn-text").textContent = on ? "设备已连接" : "未连接";
}

/* ---------- 设备 ---------- */
const KV_ORDER = [
  ["序列号", "serial"], ["机型", "model_line"], ["代号", "codename"], ["SoC", "soc_line"],
  ["系统", "android_line"], ["架构", "abi"], ["安全补丁", "security_patch"],
  ["A/B", "ab_line"], ["ROOT", "root_line"], ["by-name 根", "by_name_root"],
  ["块设备", "block_device"], ["已知分区", "partitions_line"],
];

async function loadDevice(refresh) {
  const empty = $("#device-empty");
  const content = $("#device-content");
  try {
    const p = await api("/api/info" + (refresh ? "?refresh=1" : ""));
    empty.classList.add("hidden");
    content.classList.remove("hidden");
    setConn(true);

    const view = {
      serial: p.serial,
      model_line: `${p.brand || ""} ${p.model || ""}`.trim() || "-",
      codename: p.codename || "-",
      soc_line: `${p.soc_manufacturer || ""} ${p.soc_model || ""}`.trim() || "-",
      android_line: `Android ${p.android_release || "?"} (SDK ${p.sdk || "?"})`,
      abi: p.abi || "-",
      security_patch: p.security_patch || "未知",
      ab_line: p.ab_update ? `是（槽位 ${p.slot_suffix || "?"}）` : "否（单槽位）",
      root_line: p.root ? "是" : "否",
      by_name_root: p.by_name_root || "未探测到",
      block_device: p.block_device || "未知",
      partitions_line: p.partitions ? `${Object.keys(p.partitions).length} 个` : "0",
    };

    $("#device-kv").innerHTML = KV_ORDER.map(([label, key]) => `
      <div class="item"><div class="k">${esc(label)}</div><div class="v">${esc(view[key])}</div></div>
    `).join("");

    const rows = (p.probes || []).map((pr) => `
      <tr><td class="mono">${esc(pr.name)}</td>
          <td>${pr.ok ? "✓" : "✗"}</td>
          <td class="mono muted">${esc(pr.evidence)}</td></tr>`).join("");
    $("#probe-table").innerHTML = `
      <table><thead><tr><th>探测项</th><th>结果</th><th>证据</th></tr></thead><tbody>${rows}</tbody></table>`;
  } catch (e) {
    setConn(false);
    content.classList.add("hidden");
    empty.classList.remove("hidden");
    empty.querySelector("p").textContent = e.message;
  }
}

/* ---------- 镜像分析 ---------- */
const dz = $("#dropzone");
const fileInput = $("#file");

dz.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => fileInput.files[0] && upload(fileInput.files[0]));

["dragenter", "dragover"].forEach((ev) =>
  dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("over"); }));
["dragleave", "drop"].forEach((ev) =>
  dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("over"); }));
dz.addEventListener("drop", (e) => {
  const f = e.dataTransfer.files[0];
  if (f) upload(f);
});

async function upload(file) {
  const errBox = $("#image-error");
  const result = $("#image-result");

  if (EMBED) {
    result.classList.add("hidden");
    errBox.textContent = "静态快照不能解析新文件。要拖拽分析，请双击 启动.bat 启动本地服务。";
    errBox.classList.remove("hidden");
    return;
  }

  errBox.classList.add("hidden");
  $("#image-name").textContent = `${file.name} · ${(file.size / 1048576).toFixed(1)} MB`;
  $("#image-kind").textContent = "分析中…";
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

function renderImage(data) {
  $("#image-kind").textContent = { gpt: "GPT 分区表", lp: "super / LP 元数据", sparse: "sparse 镜像" }[data.kind] || data.kind;
  const body = $("#image-body");

  if (data.kind === "gpt") {
    const t = data.table;
    const rows = t.partitions.map((p) => `
      <tr><td>${p.index}</td><td class="mono">${esc(p.name) || "(未命名)"}</td>
          <td class="mono muted">${p.type.slice(0, 8)}</td>
          <td class="mono">${p.first_lba}</td>
          <td>${human(p.sectors * t.sector_size)}</td></tr>`).join("");
    body.innerHTML = `
      <p class="muted">扇区 ${t.sector_size}B · ${t.source === "primary" ? "主表" : "备份表"} ·
         CRC ${t.crc_ok ? "通过" : "异常"} · 磁盘 ${esc(t.disk_guid)}</p>
      <table><thead><tr><th>#</th><th>名称</th><th>类型</th><th>起始 LBA</th><th>大小</th></tr></thead>
      <tbody>${rows}</tbody></table>`;
  }

  if (data.kind === "lp") {
    const m = data.metadata;
    const rows = m.partitions.map((p) => `
      <tr><td class="mono">${esc(p.name)}</td><td>${p.size_human}</td>
          <td>${p.extent_count}</td><td class="muted">${p.group_index}</td></tr>`).join("");
    body.innerHTML = `
      <p class="muted">版本 ${m.header.version} · header ${m.header.header_size}B ·
         块大小 ${m.geometry.logical_block_size}B · 逻辑总容量 ${human(m.logical_size)}
         ${m.warnings.length ? "· ⚠ " + esc(m.warnings.join("；")) : ""}</p>
      <table><thead><tr><th>分区</th><th>大小</th><th>extent 数</th><th>组</th></tr></thead>
      <tbody>${rows}</tbody></table>`;
  }

  if (data.kind === "sparse") {
    const s = data.info;
    const stats = Object.entries(s.chunk_stats).map(([k, v]) => `${k} ×${v}`).join("，");
    body.innerHTML = `
      <p class="muted">块大小 ${s.block_size}B · ${s.total_blocks} 块 ·
         展开后 ${human(s.expanded_size)} · ${s.total_chunks} 个 chunk（${esc(stats)}）</p>`;
  }
}

function human(n) {
  const units = ["B", "KiB", "MiB", "GiB", "TiB"];
  let v = n, i = 0;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return (i === 0 ? v : v.toFixed(1)) + units[i];
}

/* ---------- 启动 ---------- */
$("#btn-doctor").addEventListener("click", loadDoctor);
$("#btn-refresh").addEventListener("click", () => loadDevice(true));

loadDoctor();
loadDevice(false);
