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

/* ---------- 环境自检 ---------- */
async function loadDoctor() {
  const list = $("#doctor-list");
  const chips = $("#doctor-summary");
  list.innerHTML = "";
  chips.innerHTML = '<span class="chip">检测中…</span>';

  try {
    const data = await api("/api/doctor");
    const count = (s) => data.checks.filter((c) => c.status === s).length;
    chips.innerHTML = [
      `<span class="chip fail"><i></i>${count("fail")} 项失败</span>`,
      `<span class="chip warn"><i></i>${count("warn")} 项警告</span>`,
      `<span class="chip ok"><i></i>${count("ok")} 项通过</span>`,
      `<span class="chip">${esc(data.platform)} · Python ${esc(data.python)}</span>`,
    ].join("");

    list.innerHTML = data.checks.map((c) => `
      <div class="check ${c.status}">
        <i class="dot"></i>
        <div class="k">${esc(c.name)}</div>
        <div class="v">${esc(c.detail)}</div>
        ${c.hint && c.status !== "ok" ? `<div class="hint">↳ ${esc(c.hint)}</div>` : ""}
      </div>`).join("");

    setStatus(data.checks.some((c) => c.name.startsWith("device ") && c.status === "ok"));
  } catch (e) {
    chips.innerHTML = '<span class="chip fail"><i></i>检测失败</span>';
    list.innerHTML = `
      <div class="check fail"><i class="dot"></i><div class="k">错误</div>
        <div class="v">${esc(e.message)}</div></div>`;
  }
}

function setStatus(on) {
  $("#status-chip").classList.toggle("on", on);
  $("#status-text").textContent = on ? "设备已连接" : "未连接";
}

/* ---------- 设备 ---------- */
const KV = [
  ["序列号", "serial"], ["机型", "model"], ["代号", "codename"], ["SoC", "soc"],
  ["系统", "android"], ["架构", "abi"], ["安全补丁", "patch"],
  ["A/B 槽位", "ab"], ["ROOT", "root"], ["by-name 根", "by_name"],
  ["块设备", "block"], ["已知分区", "parts"],
];

async function loadDevice(refresh) {
  const empty = $("#device-empty");
  const content = $("#device-content");
  try {
    const p = await api("/api/info" + (refresh ? "?refresh=1" : ""));
    empty.classList.add("hidden");
    content.classList.remove("hidden");
    setStatus(true);

    const v = {
      serial: p.serial,
      model: `${p.brand || ""} ${p.model || ""}`.trim() || "-",
      codename: p.codename || "-",
      soc: `${p.soc_manufacturer || ""} ${p.soc_model || ""}`.trim() || "-",
      android: `Android ${p.android_release || "?"} · SDK ${p.sdk || "?"}`,
      abi: p.abi || "-",
      patch: p.security_patch || "未知",
      ab: p.ab_update ? `A/B（${p.slot_suffix || "?"}）` : "单槽位",
      root: p.root ? "已 ROOT" : "未 ROOT",
      by_name: p.by_name_root || "未探测到",
      block: p.block_device || "未知",
      parts: p.partitions ? `${Object.keys(p.partitions).length} 个` : "0",
    };

    $("#device-kv").innerHTML = KV.map(([label, key]) =>
      `<div class="stat"><span>${esc(label)}</span><b>${esc(v[key])}</b></div>`).join("");

    const rows = (p.probes || []).map((pr) => `
      <tr><td class="mono">${esc(pr.name)}</td>
          <td>${pr.ok ? '<span style="color:var(--ok)">✓</span>' : '<span style="color:var(--fail)">✗</span>'}</td>
          <td class="mono muted">${esc(pr.evidence)}</td></tr>`).join("");

    $("#probe-table").innerHTML = `
      <table><thead><tr><th>探测项</th><th>结果</th><th>证据</th></tr></thead>
      <tbody>${rows}</tbody></table>`;
  } catch (e) {
    setStatus(false);
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
  $("#image-kind").textContent =
    { gpt: "GPT 分区表", lp: "super 元数据", sparse: "sparse 镜像" }[data.kind] || data.kind;
  const body = $("#image-body");

  if (data.kind === "gpt") {
    const t = data.table;
    const rows = t.partitions.map((p) => `
      <tr><td class="muted">${p.index}</td><td class="mono">${esc(p.name) || "(未命名)"}</td>
          <td class="mono muted">${p.type.slice(0, 8)}</td>
          <td class="mono">${p.first_lba}</td>
          <td>${human(p.sectors * t.sector_size)}</td></tr>`).join("");
    body.innerHTML = `
      <p class="meta">扇区 <b>${t.sector_size}B</b> · ${t.source === "primary" ? "主表" : "备份表"} ·
         CRC <b>${t.crc_ok ? "通过" : "异常"}</b> · 磁盘 <b class="mono">${esc(t.disk_guid)}</b></p>
      <div class="table-wrap"><table>
        <thead><tr><th>#</th><th>名称</th><th>类型</th><th>起始 LBA</th><th>大小</th></tr></thead>
        <tbody>${rows}</tbody></table></div>`;
  }

  if (data.kind === "lp") {
    const m = data.metadata;
    const rows = m.partitions.map((p) => `
      <tr><td class="mono">${esc(p.name)}</td><td>${p.size_human}</td>
          <td class="muted">${p.extent_count}</td><td class="muted">${p.group_index}</td></tr>`).join("");
    body.innerHTML = `
      <p class="meta">版本 <b>${m.header.version}</b> · header <b>${m.header.header_size}B</b> ·
         块大小 <b>${m.geometry.logical_block_size}B</b> · 逻辑容量 <b>${human(m.logical_size)}</b>
         ${m.warnings.length ? `· <span style="color:var(--warn)">⚠ ${esc(m.warnings.join("；"))}</span>` : ""}</p>
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

/* ---------- 启动 ---------- */
$("#btn-doctor").addEventListener("click", loadDoctor);
$("#btn-refresh").addEventListener("click", () => loadDevice(true));

loadDoctor();
loadDevice(false);
