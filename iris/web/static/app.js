const TOKEN = window.__IRIS_TOKEN__;
const EMBED = window.__IRIS_DATA__ || null;   // 单文件快照模式

async function api(path, options = {}) {
  if (EMBED) {
    const key = path.split("?")[0];
    if (EMBED[key] !== undefined) return EMBED[key];
    if (key === "/api/info" && EMBED["/api/info_error"]) throw new Error(EMBED["/api/info_error"]);
    throw new Error("静态快照：该功能需要本地服务（双击 Start-Iris.bat）");
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

function toast(msg, bad) {
  const el = document.createElement("div");
  el.className = "toast" + (bad ? " bad" : "");
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3200);
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

/* ---------- 侧栏摘要 ---------- */
function setSummary({ connected, codename, bl, slot }) {
  $("#ds-state").textContent = connected ? "已连接" : "未连接";
  if (codename !== undefined) $("#ds-code").textContent = codename || "—";
  if (bl !== undefined) $("#ds-bl").textContent = bl || "—";
  if (slot !== undefined) $("#ds-slot").textContent = slot || "—";
  $("#foot-state").textContent = connected ? "在线" : "离线";
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

    const connected = data.checks.some((c) => c.name.startsWith("device ") && c.status === "ok");
    if (connected) setSummary({ connected: true });
    else setSummary({ connected: false, codename: "—", bl: "—", slot: "—" });
  } catch (e) {
    chips.innerHTML = '<span class="chip fail"><i></i>检测失败</span>';
    list.innerHTML = `<div class="row fail"><i class="dot"></i><div class="k">错误</div>
      <div class="v">${esc(e.message)}</div></div>`;
  }
}

/* ---------- 设备 ---------- */
const FIELDS = [
  ["品牌", (p) => p.brand],
  ["型号", (p) => p.model],
  ["代号", (p) => p.codename],
  ["Android", (p) => `${p.android_release || "?"} (SDK ${p.sdk || "?"})`],
  ["SoC", (p) => p.soc_model],
  ["架构", (p) => p.abi],
  ["安全补丁", (p) => p.security_patch],
  ["槽位", (p) => (p.ab_update ? `A/B ${p.slot_suffix || ""}` : "单槽位")],
  ["ROOT", (p) => (p.root ? "是" : "否")],
  ["by-name 根", (p) => p.by_name_root || "未探测到"],
  ["块设备", (p) => p.block_device || "—"],
  ["分区数", (p) => (p.partitions ? String(Object.keys(p.partitions).length) : "0")],
];

async function loadDevice(refresh) {
  const empty = $("#device-empty");
  try {
    const p = await api("/api/info" + (refresh ? "?refresh=1" : ""));
    empty.classList.add("hidden");

    $("#device-fields").innerHTML = FIELDS.map(([label, get]) =>
      `<div class="row2"><span class="k">${esc(label)}</span><span class="v">${esc(get(p) || "—")}</span></div>`
    ).join("");

    const rows = (p.probes || []).map((pr) => `
      <tr><td class="mono">${esc(pr.name)}</td>
          <td>${pr.ok ? '<span style="color:var(--ok)">✓</span>' : '<span style="color:var(--fail)">✗</span>'}</td>
          <td class="mono" style="color:var(--muted)">${esc(pr.evidence)}</td></tr>`).join("");
    $("#probe-table").innerHTML = `
      <table><thead><tr><th>探测项</th><th>结果</th><th>证据</th></tr></thead>
      <tbody>${rows}</tbody></table>`;

    setSummary({
      connected: true,
      codename: p.codename || "—",
      bl: p.root ? "已 root" : "未 root",
      slot: p.ab_update ? (p.slot_suffix || "A/B") : "单槽位",
    });

    loadStats();
  } catch (e) {
    empty.classList.remove("hidden");
    empty.querySelector("p, b").textContent = e.message;
    setSummary({ connected: false, codename: "—", bl: "—", slot: "—" });
    document.querySelectorAll(".act").forEach((b) => (b.disabled = true));
  }
}

function setRing(dialId, numId, capId, pct, label, cap) {
  const dial = $(dialId);
  if (pct === null || pct === undefined) {
    dial.style.setProperty("--pct", 0);
    $(numId).textContent = "—";
    $(capId).textContent = cap;
    return;
  }
  dial.style.setProperty("--pct", pct);
  $(numId).textContent = label;
  $(capId).textContent = cap;
}

async function loadStats() {
  try {
    const s = await api("/api/device/stats");
    if (s.battery_level !== undefined) {
      setRing("#batt-dial", "#batt-num", "#batt-cap", s.battery_level, `${s.battery_level}%`,
        `${(s.battery_mv || 0) / 1000}V ${s.battery_temp ?? "?"}°C`);
    } else {
      setRing("#batt-dial", "#batt-num", "#batt-cap", null, "—", "不可用");
    }
    if (s.disk_total) {
      const pct = Math.round((s.disk_used / s.disk_total) * 100);
      setRing("#disk-dial", "#disk-num", "#disk-cap", pct, `${pct}%`,
        `${human(s.disk_used)} / ${human(s.disk_total)}`);
    } else {
      setRing("#disk-dial", "#disk-num", "#disk-cap", null, "—", "不可用");
    }
  } catch (e) {
    setRing("#batt-dial", "#batt-num", "#batt-cap", null, "—", "不可用");
    setRing("#disk-dial", "#disk-num", "#disk-cap", null, "—", "不可用");
  }
}

/* ---------- 快捷操作 ---------- */
document.querySelectorAll(".act").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const name = btn.dataset.act;
    const out = $("#action-output");
    btn.disabled = true;
    try {
      const res = await api("/api/device/action?name=" + encodeURIComponent(name));
      if (res.ok) {
        toast(res.message);
        if (name === "logcat" && res.detail) {
          out.textContent = res.detail;
          out.classList.remove("hidden");
        }
      } else {
        toast(res.message, true);
        if (res.detail) {
          out.textContent = res.detail;
          out.classList.remove("hidden");
        }
      }
    } catch (e) {
      toast(e.message, true);
    } finally {
      btn.disabled = false;
    }
  });
});

/* ---------- 镜像分析 ---------- */
const fileInput = $("#file");
$("#pick").addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => fileInput.files[0] && upload(fileInput.files[0]));

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
  const result = $("#image-result");
  const errCard = $("#image-error-card");
  errCard.classList.add("hidden");
  $("#file-name").textContent = `${file.name} · ${(file.size / 1048576).toFixed(1)} MB`;

  if (EMBED) {
    result.classList.add("hidden");
    $("#image-error").textContent = "静态快照不能解析新文件。要拖拽分析，请用 Start-Iris.bat 启动服务。";
    errCard.classList.remove("hidden");
    return;
  }

  $("#image-kind").textContent = "分析中…";
  $("#image-title").textContent = file.name;
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
    result.classList.add("hidden");
    $("#image-error").textContent = e.message;
    errCard.classList.remove("hidden");
  }
}

async function extractPart(ticket, part, btn) {
  const label = btn.textContent;
  btn.disabled = true;
  btn.textContent = "提取中…";
  try {
    const res = await fetch(
      `/api/extract?ticket=${encodeURIComponent(ticket)}&part=${encodeURIComponent(part)}`,
      { headers: { "X-Iris-Token": TOKEN } },
    );
    if (!res.ok) throw new Error((await res.text()).slice(0, 200));
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${part}.img`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
    toast(`已下载 ${part}.img`);
  } catch (e) {
    toast("提取失败：" + e.message, true);
  } finally {
    btn.textContent = label;
    btn.disabled = false;
  }
}

function renderImage(data) {
  $("#image-kind").textContent =
    { gpt: "GPT", lp: "super", sparse: "sparse", payload: "payload", boot: "boot", avb: "vbmeta" }[data.kind] || data.kind;
  const body = $("#image-body");

  if (data.kind === "payload") {
    const p = data.payload;
    const rows = p.partitions.map((x) => `
      <tr><td class="mono">${esc(x.name)}</td><td>${human(x.size_bytes)}</td>
          <td style="color:var(--muted)">${x.operation_count}</td>
          <td style="color:var(--muted)">${esc(x.operations.join(", "))}</td>
          <td>${x.extractable ? `<button class="btn" data-part="${esc(x.name)}">提取</button>` : "—"}</td></tr>`).join("");
    body.innerHTML = `
      <p class="meta">payload v${p.version} · 块 ${p.block_size}B · ${p.partition_count} 个分区</p>
      <div class="table-wrap"><table><thead><tr><th>分区</th><th>解包后</th><th>操作数</th><th>类型</th><th></th></tr></thead>
      <tbody>${rows}</tbody></table></div>`;
    body.querySelectorAll("button[data-part]").forEach((b) => {
      b.onclick = () => extractPart(data.ticket, b.dataset.part, b);
    });
    return;
  }

  if (data.kind === "lp") {
    const m = data.metadata;
    const rows = m.partitions.map((p) => `
      <tr><td class="mono">${esc(p.name)}</td><td>${p.size_human}</td>
          <td style="color:var(--muted)">${p.extent_count}</td>
          <td>${data.ticket ? `<button class="btn" data-part="${esc(p.name)}">提取</button>` : ""}</td></tr>`).join("");
    body.innerHTML = `
      <p class="meta">LP ${m.header.version} · 块 ${m.geometry.logical_block_size}B · 逻辑容量 ${human(m.logical_size)}</p>
      <div class="table-wrap"><table><thead><tr><th>分区</th><th>大小</th><th>extent</th><th></th></tr></thead>
      <tbody>${rows}</tbody></table></div>`;
    body.querySelectorAll("button[data-part]").forEach((b) => {
      b.onclick = () => extractPart(data.ticket, b.dataset.part, b);
    });
    return;
  }

  if (data.kind === "boot") {
    const b = data.boot;
    const rows = [
      ["header", `v${b.header_version}`], ["页大小", `${b.page_size}B`],
      ["内核", `${human(b.kernel_size)} @ ${b.kernel_offset}`],
      ["ramdisk", `${human(b.ramdisk_size)} @ ${b.ramdisk_offset}`],
      ["系统版本", b.os_version], ["名称", b.name || "—"],
    ].map(([k, v]) => `<div class="row2"><span class="k">${esc(k)}</span><span class="v">${esc(v)}</span></div>`).join("");
    body.innerHTML = `<div class="kv2">${rows}</div>
      <p class="meta">cmdline：<b>${esc(b.cmdline || "—")}</b></p>`;
    return;
  }

  if (data.kind === "avb") {
    const a = data.avb;
    const rows = [
      ["版本", a.version], ["签名算法", a.algorithm],
      ["flags", `0x${a.flags.toString(16)}`],
      ["dm-verity", a.verity_disabled ? "已关闭" : "启用"],
      ["工具", a.release_string || "—"],
    ].map(([k, v]) => `<div class="row2"><span class="k">${esc(k)}</span><span class="v">${esc(v)}</span></div>`).join("");
    body.innerHTML = `<div class="kv2">${rows}</div>`;
    return;
  }

  if (data.kind === "gpt") {
    const t = data.table;
    const rows = t.partitions.map((p) => `
      <tr><td style="color:var(--muted)">${p.index}</td><td class="mono">${esc(p.name) || "(未命名)"}</td>
          <td class="mono">${p.first_lba}</td><td>${human(p.sectors * t.sector_size)}</td></tr>`).join("");
    body.innerHTML = `
      <p class="meta">扇区 ${t.sector_size}B · ${t.source === "primary" ? "主表" : "备份表"} · CRC ${t.crc_ok ? "通过" : "异常"}</p>
      <div class="table-wrap"><table><thead><tr><th>#</th><th>名称</th><th>起始 LBA</th><th>大小</th></tr></thead>
      <tbody>${rows}</tbody></table></div>`;
    return;
  }

  if (data.kind === "sparse") {
    const s = data.info;
    const stats = Object.entries(s.chunk_stats).map(([k, v]) => `${k} ×${v}`).join("，");
    body.innerHTML = `<p class="meta">块 ${s.block_size}B · ${s.total_blocks} 块 · 展开后 ${human(s.expanded_size)} · ${s.total_chunks} 个 chunk（${esc(stats)}）</p>`;
  }
}

/* ---------- 关于 ---------- */
$("#about-fields").innerHTML = [
  ["版本", "v0.3.0"], ["许可证", "GPL-3.0"],
  ["运行时", "Python 标准库，零依赖"], ["数据", "本地处理，不外传"],
].map(([k, v]) => `<div class="row2"><span class="k">${esc(k)}</span><span class="v">${esc(v)}</span></div>`).join("");

/* ---------- 启动 ---------- */
loadDoctor();
loadDevice(false);
