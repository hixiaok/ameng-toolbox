/*
 * 无设备环境下的前端冒烟测试：用最小 DOM 桩 + 假 Android 桥跑一遍 app.js。
 * 目的不是替代真机，而是保证：脚本能加载、五个页面能渲染、协议字段对得上。
 *
 * 运行：node android/test/ui_smoke.js
 */
"use strict";

const fs = require("fs");
const path = require("path");

/* ---------------- 最小 DOM ---------------- */
class El {
  constructor(tag) {
    this.tag = tag;
    this.children = [];
    this.parent = null;
    this._text = "";
    this._html = "";
    this.className = "";
    this.dataset = {};
    this.style = {};
    this.value = "";
    this.checked = false;
    this.disabled = false;
    this.title = "";
    this.listeners = {};
    this._classes = new Set();
    const self = this;
    this.classList = {
      add: (...c) => c.forEach((x) => self._classes.add(x)),
      remove: (...c) => c.forEach((x) => self._classes.delete(x)),
      contains: (c) => self._classes.has(c),
      toggle: (c, force) => {
        const on = force === undefined ? !self._classes.has(c) : !!force;
        if (on) self._classes.add(c); else self._classes.delete(c);
        return on;
      },
    };
  }
  get classListString() { return Array.from(this._classes).join(" "); }
  get textContent() {
    if (this.children.length) return this.children.map((c) => c.textContent).join("");
    return this._text;
  }
  set textContent(v) { this._text = String(v); this.children = []; }
  get innerHTML() { return this._html; }
  set innerHTML(v) { this._html = String(v); this._text = ""; this.children = []; }
  get childNodes() { return this.children; }
  get firstChild() { return this.children[0]; }
  get lastChild() { return this.children[this.children.length - 1]; }
  appendChild(c) { c.parent = this; this.children.push(c); return c; }
  removeChild(c) {
    const i = this.children.indexOf(c);
    if (i >= 0) this.children.splice(i, 1);
    return c;
  }
  addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); }
  dispatch(type, ev) {
    const e = ev || { preventDefault() {}, stopPropagation() {} };
    (this.listeners[type] || []).forEach((fn) => fn(e));
  }
  click() { this.dispatch("click"); }
  focus() {}
  remove() { if (this.parent) this.parent.removeChild(this); }
  querySelector(sel) {
    const match = (n) => (sel.startsWith(".")
      ? n.className.split(/\s+/).includes(sel.slice(1))
      : n.tag === sel);
    for (const c of this.children) {
      if (match(c)) return c;
      const found = c.querySelector(sel);
      if (found) return found;
    }
    return null;
  }
  querySelectorAll(sel) {
    const out = [];
    const match = (n) => (sel.startsWith(".")
      ? n.className.split(/\s+/).includes(sel.slice(1))
      : n.tag === sel);
    const walk = (n) => {
      n.children.forEach((c) => {
        if (match(c)) out.push(c);
        walk(c);
      });
    };
    walk(this);
    return out;
  }
  closest() { return this.parent || new El("div"); }
}

const ids = [
  "devline", "ver", "rootPill", "infoGrid", "termOut", "termCmd", "termRoot", "termRun",
  "partList", "partFilter", "partRefresh", "modList", "modManager", "modRefresh", "modInstall",
  "filePath", "fileRoot", "fileGo", "fileHome", "fileData", "fileUp", "fileList",
  "appList", "appThird", "appAll", "appFilter",
  "toast", "modalMask", "modalTitle", "modalText", "modalOk", "modalCancel",
];
const byId = {};
ids.forEach((id) => { byId[id] = new El("div"); byId[id].id = id; });

const pages = ["terminal", "parts", "modules", "files", "apps"].map((name) => {
  const p = new El("section");
  p.id = "page-" + name;
  p.className = "page" + (name === "terminal" ? " active" : "");
  return p;
});

const tabs = ["terminal", "parts", "modules", "files", "apps"].map((name) => {
  const b = new El("button");
  b.className = "tab" + (name === "terminal" ? " active" : "");
  b.dataset.page = name;
  return b;
});

const document = {
  querySelector(sel) {
    if (sel.startsWith("#")) return byId[sel.slice(1)] || (byId[sel.slice(1)] = new El("div"));
    return null;
  },
  querySelectorAll(sel) {
    if (sel === ".tab") return tabs;
    if (sel === ".page") return pages;
    return [];
  },
  createElement(tag) { return new El(tag); },
  body: new El("body"),
};

/* ---------------- 假 Android 桥 ---------------- */
const calls = [];
function respond(id, obj, delay) {
  setTimeout(() => { global.window.__irisDone(id, JSON.stringify(obj)); }, delay || 0);
}

const Android = {
  call(method, argsJson, id) {
    const args = JSON.parse(argsJson || "{}");
    calls.push({ method, args });
    switch (method) {
      case "info":
        return respond(id, {
          ok: true, brand: "Google", model: "Pixel 10", release: "16", sdk: 36,
          abi: "x86_64", version: "0.3.0", root: true, manager: "Magisk 27.0",
          su: "/system/bin/su", backupDir: "/sdcard/Android/data/com.iris.toolbox/files/backups",
        });
      case "shell":
        return respond(id, { ok: true, success: true, code: 0, out: "uid=0(root)", err: "", ms: 3, timedOut: false });
      case "parts":
        return respond(id, {
          ok: true,
          parts: [
            { name: "boot_a", path: "/dev/block/by-name/boot_a", size: 67108864 },
            { name: "super", path: "/dev/block/by-name/super", size: 8589934592 },
          ],
        });
      case "backup":
        setTimeout(() => global.window.__irisProgress(id, 0.5, "32.0MiB / 64.0MiB"), 0);
        return respond(id, { ok: true, path: "/sdcard/Android/data/com.iris.toolbox/files/backups/boot_a-1.img", size: 67108864, sha256: "abc" }, 5);
      case "restore":
        return respond(id, { ok: true, written: 67108864, verified: true });
      case "modules":
        return respond(id, {
          ok: true, manager: "Magisk 27.0",
          modules: [
            { name: "LSPosed", version: "1.9.3", author: "LSPosed", description: "框架", enabled: true, pendingRemove: false },
          ],
        });
      case "moduleToggle":
      case "moduleRemove":
        return respond(id, { ok: true, message: "done" });
      case "ls":
        return respond(id, {
          ok: true,
          items: [
            { name: "Download", dir: true, perm: "drwxrwx--x", size: 0 },
            { name: "note.txt", dir: false, perm: "-rw-rw----", size: 12 },
          ],
        });
      case "read":
        return respond(id, { ok: true, text: "hello iris", truncated: false });
      case "apps":
        return respond(id, {
          ok: true,
          apps: [
            { pkg: "com.example.a", disabled: false },
            { pkg: "com.example.b", disabled: true },
          ],
        });
      case "appAction":
        return respond(id, { ok: true, message: "ok" });
      case "pick":
      case "export":
        return respond(id, { ok: true });
      default:
        return respond(id, { ok: false, error: "unknown method " + method });
    }
  },
};

/* ---------------- 加载 app.js ---------------- */
const src = fs.readFileSync(path.join(__dirname, "..", "assets", "app.js"), "utf8");
global.window = global;
global.document = document;
global.Android = Android;
global.setTimeout = setTimeout;

const results = [];
function check(name, cond, detail) {
  results.push({ name, ok: !!cond, detail: detail || "" });
  console.log((cond ? "✓ " : "✗ ") + name + (detail ? "  " + detail : ""));
}

(async () => {
  eval(src);
  await new Promise((r) => setTimeout(r, 30));

  check("设备信息渲染", byId.devline.textContent.includes("Pixel 10"), byId.devline.textContent);
  check("root 徽标", byId.rootPill.textContent.includes("Magisk"), byId.rootPill.textContent);

  // 终端
  byId.termCmd.value = "id";
  byId.termCmd.dispatch("keydown", { key: "Enter", preventDefault() {} });
  await new Promise((r) => setTimeout(r, 30));
  check("终端输出", byId.termOut.textContent.includes("uid=0"), byId.termOut.textContent.replace(/\n/g, " | "));

  // 分区
  tabs[1].dispatch("click");
  await new Promise((r) => setTimeout(r, 30));
  check("分区列表", byId.partList.children.length === 2, "items=" + byId.partList.children.length);
  const bootItem = byId.partList.children[0];
  const buttons = bootItem.querySelectorAll(".btn");
  check("分区按钮", buttons.length >= 2, "buttons=" + buttons.length);

  // 备份
  const backupBtn = buttons[0];
  backupBtn.dispatch("click");
  await new Promise((r) => setTimeout(r, 60));
  check("备份调用", calls.some((c) => c.method === "backup" && c.args.name === "boot_a"));
  check("备份提示", byId.toast.textContent.includes("已备份"), byId.toast.textContent);

  // 模块
  tabs[2].dispatch("click");
  await new Promise((r) => setTimeout(r, 30));
  check("模块列表", byId.modList.children.length === 1, "items=" + byId.modList.children.length);
  check("模块管理器", byId.modManager.textContent.includes("Magisk"), byId.modManager.textContent);
  const mod = byId.modList.children[0];
  const sw = mod.querySelector("input");
  check("模块开关存在", !!sw);
  sw.checked = false;
  sw.dispatch("change");
  await new Promise((r) => setTimeout(r, 30));
  check("模块禁用调用", calls.some((c) => c.method === "moduleToggle" && c.args.enabled === false));

  // 文件
  tabs[3].dispatch("click");
  await new Promise((r) => setTimeout(r, 30));
  check("文件列表", byId.fileList.children.length === 2, "items=" + byId.fileList.children.length);

  // 应用
  tabs[4].dispatch("click");
  await new Promise((r) => setTimeout(r, 30));
  check("应用列表", byId.appList.children.length === 2, "items=" + byId.appList.children.length);

  const failed = results.filter((r) => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} 通过`);
  process.exit(failed.length ? 1 : 0);
})();
