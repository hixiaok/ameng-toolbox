/* Iris 手机版 —— 界面逻辑。数据全部来自 Java 侧的 Android.call()。 */
"use strict";

const $ = (s) => document.querySelector(s);
const state = {
  info: null,
  parts: [],
  modules: [],
  apps: [],
  filePath: "/sdcard",
  fileRoot: false,
  appsAll: false,
  lastBackup: {},
  picked: null,
};

/* ---------------- 原生桥 ---------------- */
let seq = 0;
const pending = new Map();

function native(method, args, onProgress) {
  return new Promise((resolve, reject) => {
    const id = String(++seq);
    const entry = { resolve, reject, onProgress };
    pending.set(id, entry);
    try {
      Android.call(method, JSON.stringify(args || {}), id);
    } catch (e) {
      pending.delete(id);
      reject(e);
    }
  });
}

window.__irisDone = function (id, json) {
  const entry = pending.get(id);
  if (!entry) return;
  pending.delete(id);
  let data;
  try {
    data = JSON.parse(json);
  } catch (e) {
    entry.reject(new Error("返回数据损坏"));
    return;
  }
  if (data && data.ok === false) entry.reject(new Error(data.error || "执行失败"));
  else entry.resolve(data || {});
};

window.__irisProgress = function (id, ratio, label) {
  const entry = pending.get(id);
  if (entry && entry.onProgress) entry.onProgress(ratio, label);
};

let pickWaiter = null;
window.__irisPicked = function (kind, path, name) {
  if (pickWaiter) {
    const w = pickWaiter;
    pickWaiter = null;
    w(path || "", name || "");
  }
};

window.__irisExported = function (ok, msg) {
  if (ok) toast("已导出");
  else if (msg === "已取消") toast("已取消");
  else toast("导出失败：" + msg, true);
};

/* ---------------- 通用 UI ---------------- */
let toastTimer = 0;
function toast(msg, bad) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.toggle("bad", !!bad);
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 2600);
}

function confirmBox(title, text, okText) {
  return new Promise((resolve) => {
    $("#modalTitle").textContent = title;
    $("#modalText").textContent = text;
    $("#modalOk").textContent = okText || "确认";
    $("#modalMask").classList.remove("hidden");
    const done = (value) => {
      $("#modalMask").classList.add("hidden");
      $("#modalOk").onclick = null;
      $("#modalCancel").onclick = null;
      resolve(value);
    };
    $("#modalOk").onclick = () => done(true);
    $("#modalCancel").onclick = () => done(false);
  });
}

function infoBox(text) {
  return new Promise((resolve) => {
    $("#modalTitle").textContent = "预览";
    $("#modalText").textContent = text;
    $("#modalOk").textContent = "关闭";
    $("#modalCancel").style.display = "none";
    $("#modalMask").classList.remove("hidden");
    $("#modalOk").onclick = () => {
      $("#modalMask").classList.add("hidden");
      $("#modalCancel").style.display = "";
      resolve();
    };
  });
}

function human(n) {
  const units = ["B", "KiB", "MiB", "GiB", "TiB"];
  let v = n, i = 0;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return (i === 0 ? v.toFixed(0) : v.toFixed(1)) + units[i];
}

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function empty(text) {
  return el("div", "empty", text);
}

/* ---------------- 标签页 ---------------- */
const loaded = {};
function switchTab(page) {
  document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b.dataset.page === page));
  document.querySelectorAll(".page").forEach((p) => p.classList.toggle("active", p.id === "page-" + page));
  if (page === "parts" && !loaded.parts) loadParts();
  if (page === "modules" && !loaded.modules) loadModules();
  if (page === "files" && !loaded.files) loadFiles();
  if (page === "apps" && !loaded.apps) loadApps();
}

document.querySelectorAll(".tab").forEach((b) => {
  b.addEventListener("click", () => switchTab(b.dataset.page));
});

/* ---------------- 设备信息 ---------------- */
async function loadInfo(refresh) {
  try {
    const info = await native(refresh ? "refreshRoot" : "info");
    state.info = info;
    $("#devline").textContent = `${info.brand} ${info.model} · Android ${info.release}`;
    $("#ver").textContent = "v" + info.version;

    const pill = $("#rootPill");
    if (info.root) {
      pill.textContent = info.manager || "ROOT";
      pill.className = "pill on";
    } else {
      pill.textContent = "未 root";
      pill.className = "pill off";
    }

    const grid = $("#infoGrid");
    grid.innerHTML = "";
    const rows = [
      ["机型", `${info.brand} ${info.model}`],
      ["系统", `Android ${info.release}（SDK ${info.sdk}）`],
      ["架构", info.abi],
      ["ROOT", info.root ? (info.manager || "已授权") : "否"],
      ["su", info.su || "—"],
      ["备份目录", info.backupDir],
    ];
    rows.forEach(([k, v]) => {
      const row = el("div", "row");
      row.appendChild(el("span", "k", k));
      const val = el("span", "v", v);
      val.title = v;
      row.appendChild(val);
      grid.appendChild(row);
    });

    if (info.root) {
      $("#termRoot").checked = true;
      $("#fileRoot").checked = true;
    }
  } catch (e) {
    $("#devline").textContent = "读取设备信息失败";
    toast(e.message, true);
  }
}

$("#rootPill").addEventListener("click", () => loadInfo(true));

/* ---------------- 终端 ---------------- */
const hist = [];
let histPos = 0;

function termLine(text, cls) {
  const out = $("#termOut");
  const div = el("div", cls || "", text);
  out.appendChild(div);
  while (out.childNodes.length > 400) out.removeChild(out.firstChild);
  out.scrollTop = out.scrollHeight;
}

async function runCmd() {
  const cmd = $("#termCmd").value.trim();
  if (!cmd) return;
  $("#termCmd").value = "";
  hist.push(cmd);
  histPos = hist.length;
  const root = $("#termRoot").checked;
  termLine((root ? "# " : "$ ") + cmd, "cmd");
  termLine("执行中…", "meta");
  const placeholder = $("#termOut").lastChild;
  try {
    const r = await native("shell", { cmd, root });
    placeholder.remove();
    const text = [r.out, r.err].filter(Boolean).join("\n").trimEnd();
    termLine(text || "(无输出)", r.ok ? "" : "bad");
    termLine(`[退出码 ${r.code} · ${r.ms}ms${r.timedOut ? " · 超时" : ""}]`, "meta");
  } catch (e) {
    placeholder.remove();
    termLine("失败：" + e.message, "bad");
  }
}

$("#termRun").addEventListener("click", runCmd);
$("#termCmd").addEventListener("keydown", (e) => {
  if (e.key === "Enter") { e.preventDefault(); runCmd(); }
  if (e.key === "ArrowUp") { e.preventDefault(); if (histPos > 0) { histPos--; $("#termCmd").value = hist[histPos]; } }
  if (e.key === "ArrowDown") { e.preventDefault(); if (histPos < hist.length - 1) { histPos++; $("#termCmd").value = hist[histPos]; } else { histPos = hist.length; $("#termCmd").value = ""; } }
});

/* ---------------- 分区 ---------------- */
async function loadParts() {
  const box = $("#partList");
  box.innerHTML = "";
  box.appendChild(empty("读取分区表…（首次会弹 root 授权）"));
  try {
    const r = await native("parts");
    state.parts = r.parts || [];
    loaded.parts = true;
    renderParts();
  } catch (e) {
    box.innerHTML = "";
    box.appendChild(empty(e.message));
  }
}

function renderParts() {
  const box = $("#partList");
  const filter = ($("#partFilter").value || "").trim().toLowerCase();
  box.innerHTML = "";
  const parts = state.parts.filter((p) => !filter || p.name.toLowerCase().includes(filter));
  if (!parts.length) {
    box.appendChild(empty("没有匹配的分区"));
    return;
  }
  parts.forEach((p) => {
    const item = el("div", "item");
    const main = el("div", "item-main");
    const grow = el("div", "grow");
    grow.appendChild(el("div", "item-name mono", p.name));
    grow.appendChild(el("div", "item-sub", human(p.size) + " · " + p.path));
    main.appendChild(grow);
    const actions = el("div", "item-actions");
    const bBackup = el("button", "btn", "备份");
    const bRestore = el("button", "btn danger", "还原");
    actions.appendChild(bBackup);
    actions.appendChild(bRestore);
    if (state.lastBackup[p.name]) {
      const bExport = el("button", "btn", "导出备份");
      bExport.addEventListener("click", () => native("export", { path: state.lastBackup[p.name] }).catch((e) => toast(e.message, true)));
      actions.appendChild(bExport);
    }
    item.appendChild(main);
    item.appendChild(actions);
    const bar = el("div", "progress");
    bar.appendChild(el("i"));
    bar.style.display = "none";
    item.appendChild(bar);

    const progress = (ratio, label) => {
      bar.style.display = "";
      bar.firstChild.style.width = Math.round(Math.max(0, Math.min(1, ratio)) * 100) + "%";
      if (label) item.querySelector(".item-sub").textContent = label;
    };

    bBackup.addEventListener("click", async () => {
      bBackup.disabled = true;
      bRestore.disabled = true;
      try {
        const res = await native("backup", { name: p.name }, progress);
        state.lastBackup[p.name] = res.path;
        toast(`已备份 ${p.name}（${human(res.size)}）\n${res.path}`);
        renderParts();
      } catch (e) {
        toast("备份失败：" + e.message, true);
        bBackup.disabled = false;
        bRestore.disabled = false;
      }
    });

    bRestore.addEventListener("click", async () => {
      try {
        toast("选择要写入的镜像…");
        const picked = await new Promise((resolve) => {
          pickWaiter = (path, name) => resolve({ path, name });
          native("pick", { kind: "img" }).catch((e) => { pickWaiter = null; toast(e.message, true); resolve(null); });
        });
        if (!picked || !picked.path) return;
        const ok = await confirmBox("还原分区", `把 ${picked.name}\n写进 ${p.name}？\n\n覆盖后无法撤销。`, "写入");
        if (!ok) return;
        bBackup.disabled = true;
        bRestore.disabled = true;
        const res = await native("restore", { name: p.name, path: picked.path }, progress);
        toast(`已写入 ${p.name}（${human(res.written)}）${res.verified ? "，回读校验通过" : ""}`);
        bBackup.disabled = false;
        bRestore.disabled = false;
        bar.style.display = "none";
      } catch (e) {
        toast("还原失败：" + e.message, true);
        bBackup.disabled = false;
        bRestore.disabled = false;
        bar.style.display = "none";
      }
    });

    box.appendChild(item);
  });
}

$("#partRefresh").addEventListener("click", loadParts);
$("#partFilter").addEventListener("input", () => { if (loaded.parts) renderParts(); });

/* ---------------- 模块 ---------------- */
async function loadModules() {
  const box = $("#modList");
  box.innerHTML = "";
  box.appendChild(empty("读取模块…"));
  try {
    const r = await native("modules");
    state.modules = r.modules || [];
    loaded.modules = true;
    $("#modManager").textContent = r.manager ? "管理器：" + r.manager : "没有识别到 root 管理器";
    renderModules();
  } catch (e) {
    box.innerHTML = "";
    box.appendChild(empty(e.message));
    $("#modManager").textContent = "读取失败";
  }
}

function renderModules() {
  const box = $("#modList");
  box.innerHTML = "";
  if (!state.modules.length) {
    box.appendChild(empty("没有已安装的模块"));
    return;
  }
  state.modules.forEach((m) => {
    const item = el("div", "item");
    const main = el("div", "item-main");
    const grow = el("div", "grow");
    grow.appendChild(el("div", "item-name", m.name));
    grow.appendChild(el("div", "item-sub", `${m.version || "—"}${m.author ? " · " + m.author : ""}`));
    if (m.description) grow.appendChild(el("div", "item-sub", m.description));
    main.appendChild(grow);

    const sw = el("label", "switch");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = !!m.enabled;
    sw.appendChild(cb);
    sw.appendChild(el("span"));
    main.appendChild(sw);

    const actions = el("div", "item-actions");
    const bRemove = el("button", "btn danger", m.pendingRemove ? "已标记卸载" : "卸载");
    bRemove.disabled = !!m.pendingRemove;
    actions.appendChild(bRemove);

    cb.addEventListener("change", async () => {
      cb.disabled = true;
      try {
        await native("moduleToggle", { name: m.name, enabled: cb.checked });
        toast(`${cb.checked ? "已启用" : "已禁用"} ${m.name}，重启后完全生效`);
      } catch (e) {
        cb.checked = !cb.checked;
        toast(e.message, true);
      }
      cb.disabled = false;
    });

    bRemove.addEventListener("click", async () => {
      const ok = await confirmBox("卸载模块", `标记卸载 ${m.name}？\n重启后由管理器真正删除。`, "标记");
      if (!ok) return;
      try {
        await native("moduleRemove", { name: m.name });
        toast("已标记，重启后生效");
        m.pendingRemove = true;
        bRemove.disabled = true;
        bRemove.textContent = "已标记卸载";
      } catch (e) { toast(e.message, true); }
    });

    item.appendChild(main);
    item.appendChild(actions);
    box.appendChild(item);
  });
}

$("#modRefresh").addEventListener("click", loadModules);
$("#modInstall").addEventListener("click", async () => {
  try {
    toast("选择模块 zip…");
    const picked = await new Promise((resolve) => {
      pickWaiter = (path, name) => resolve({ path, name });
      native("pick", { kind: "zip" }).catch((e) => { pickWaiter = null; toast(e.message, true); resolve(null); });
    });
    if (!picked || !picked.path) return;
    const ok = await confirmBox("安装模块", `安装 ${picked.name}？\n装完重启生效。`, "安装");
    if (!ok) return;
    toast("安装中…");
    const r = await native("moduleInstall", { path: picked.path });
    toast(r.message || "已安装，重启后生效");
    loadModules();
  } catch (e) {
    toast("安装失败：" + e.message, true);
  }
});

/* ---------------- 文件 ---------------- */
async function loadFiles() {
  const box = $("#fileList");
  const path = $("#filePath").value.trim() || "/sdcard";
  const root = $("#fileRoot").checked;
  box.innerHTML = "";
  box.appendChild(empty("读取中…"));
  try {
    const r = await native("ls", { path, root });
    state.filePath = path;
    state.fileRoot = root;
    loaded.files = true;
    renderFiles(r.items || []);
  } catch (e) {
    box.innerHTML = "";
    box.appendChild(empty(e.message));
  }
}

function renderFiles(items) {
  const box = $("#fileList");
  box.innerHTML = "";
  if (!items.length) {
    box.appendChild(empty("空目录"));
    return;
  }
  items.forEach((f) => {
    const item = el("div", "item");
    const main = el("div", "item-main");
    const badge = el("div", "mono", f.dir ? "📁" : "📄");
    badge.style.fontSize = "18px";
    main.appendChild(badge);
    const grow = el("div", "grow");
    grow.appendChild(el("div", "item-name", f.name + (f.dir ? "/" : "")));
    grow.appendChild(el("div", "item-sub", `${f.perm} · ${f.dir ? "目录" : human(f.size)}`));
    main.appendChild(grow);
    item.appendChild(main);

    if (f.dir) {
      item.addEventListener("click", () => {
        $("#filePath").value = state.filePath.replace(/\/$/, "") + "/" + f.name;
        loadFiles();
      });
    } else {
      const actions = el("div", "item-actions");
      const bView = el("button", "btn", "查看");
      const bExport = el("button", "btn", "导出");
      actions.appendChild(bView);
      actions.appendChild(bExport);
      item.appendChild(actions);
      bView.addEventListener("click", async (ev) => {
        ev.stopPropagation();
        try {
          const r = await native("read", { path: state.filePath.replace(/\/$/, "") + "/" + f.name, root: state.fileRoot });
          await infoBox(r.text + (r.truncated ? "\n\n…… 已截断" : ""));
        } catch (e) { toast(e.message, true); }
      });
      bExport.addEventListener("click", async (ev) => {
        ev.stopPropagation();
        try {
          await native("export", { path: state.filePath.replace(/\/$/, "") + "/" + f.name });
        } catch (e) { toast(e.message, true); }
      });
    }
    box.appendChild(item);
  });
}

$("#fileGo").addEventListener("click", loadFiles);
$("#filePath").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); loadFiles(); } });
$("#fileRoot").addEventListener("change", loadFiles);
$("#fileHome").addEventListener("click", () => { $("#filePath").value = "/sdcard"; $("#fileRoot").checked = false; loadFiles(); });
$("#fileData").addEventListener("click", () => { $("#filePath").value = "/data"; $("#fileRoot").checked = true; loadFiles(); });
$("#fileUp").addEventListener("click", () => {
  const cur = $("#filePath").value.trim().replace(/\/$/, "");
  if (!cur || cur === "/") return;
  $("#filePath").value = cur.slice(0, cur.lastIndexOf("/")) || "/";
  loadFiles();
});

/* ---------------- 应用 ---------------- */
async function loadApps() {
  const box = $("#appList");
  box.innerHTML = "";
  box.appendChild(empty("读取应用列表…"));
  try {
    const r = await native("apps", { all: state.appsAll });
    state.apps = r.apps || [];
    loaded.apps = true;
    renderApps();
  } catch (e) {
    box.innerHTML = "";
    box.appendChild(empty(e.message));
  }
}

function renderApps() {
  const box = $("#appList");
  const filter = ($("#appFilter").value || "").trim().toLowerCase();
  box.innerHTML = "";
  const list = state.apps.filter((a) => !filter || a.pkg.toLowerCase().includes(filter));
  if (!list.length) {
    box.appendChild(empty("没有匹配的应用"));
    return;
  }
  list.forEach((a) => {
    const item = el("div", "item");
    const main = el("div", "item-main");
    const grow = el("div", "grow");
    grow.appendChild(el("div", "item-name mono", a.pkg));
    grow.appendChild(el("div", "item-sub", a.disabled ? "已冻结" : "运行中"));
    main.appendChild(grow);
    const actions = el("div", "item-actions");

    if (a.disabled) {
      const b = el("button", "btn", "解冻");
      b.addEventListener("click", () => appAction(a.pkg, "unfreeze", "解冻", false));
      actions.appendChild(b);
    } else {
      const b = el("button", "btn", "冻结");
      b.addEventListener("click", () => appAction(a.pkg, "freeze", "冻结", false));
      actions.appendChild(b);
    }
    const bClear = el("button", "btn", "清数据");
    bClear.addEventListener("click", () => appAction(a.pkg, "clear", "清除数据", true));
    actions.appendChild(bClear);
    const bDel = el("button", "btn danger", "卸载");
    bDel.addEventListener("click", () => appAction(a.pkg, "uninstall", "卸载", true));
    actions.appendChild(bDel);

    item.appendChild(main);
    item.appendChild(actions);
    box.appendChild(item);
  });
}

async function appAction(pkg, action, label, danger) {
  if (danger) {
    const ok = await confirmBox(label, `${label} ${pkg}？`, label);
    if (!ok) return;
  }
  try {
    const r = await native("appAction", { pkg, action });
    toast(r.message || (label + "成功"));
    loadApps();
  } catch (e) {
    toast(label + "失败：" + e.message, true);
  }
}

$("#appThird").addEventListener("click", () => { state.appsAll = false; loadApps(); });
$("#appAll").addEventListener("click", () => { state.appsAll = true; loadApps(); });
$("#appFilter").addEventListener("input", () => { if (loaded.apps) renderApps(); });

/* ---------------- 启动 ---------------- */
loadInfo();
termLine("Iris 手机版 —— 输入命令后回车。勾选右侧开关以 root 执行。", "meta");
