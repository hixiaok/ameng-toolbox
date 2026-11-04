/*
 * 桌面端界面的无浏览器冒烟测试：最小 DOM + 假 fetch，把 10 个页面各渲染一遍。
 * 目的：抓 JS 运行时错误和接口字段拼错，不替代真实浏览器。
 *
 * 运行：node tests/desktop_ui_smoke.js
 */
"use strict";

const fs = require("fs");
const path = require("path");

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
  get textContent() { return this.children.length ? this.children.map((c) => c.textContent).join("") : this._text; }
  set textContent(v) { this._text = String(v); this.children = []; }
  get innerHTML() { return this._html; }
  set innerHTML(v) {
    this._html = String(v);
    this._text = "";
    this.children = [];
    // 把 HTML 里的 id 注册成桩，供后面 $("#id") 取到
    const re = /id="([^"]+)"/g;
    let m;
    while ((m = re.exec(this._html))) {
      registry[m[1]] = registry[m[1]] || new El("div");
    }
  }
  get childNodes() { return this.children; }
  get firstChild() { return this.children[0]; }
  appendChild(c) { c.parent = this; this.children.push(c); return c; }
  removeChild(c) { const i = this.children.indexOf(c); if (i >= 0) this.children.splice(i, 1); return c; }
  addEventListener(t, fn) { (this.listeners[t] = this.listeners[t] || []).push(fn); }
  dispatch(t, ev) { (this.listeners[t] || []).forEach((fn) => fn(ev || { preventDefault() {}, stopPropagation() {} })); }
  click() { this.dispatch("click"); }
  focus() {}
  remove() { if (this.parent) this.parent.removeChild(this); }
  querySelector(sel) {
    this._q = this._q || {};
    this._q[sel] = this._q[sel] || new El("span");
    return this._q[sel];
  }
  querySelectorAll() { return []; }
  closest() { return this.parent || new El("div"); }
}

const registry = {};
const documentStub = {
  querySelector(sel) {
    if (!sel.startsWith("#")) return null;
    const id = sel.slice(1);
    registry[id] = registry[id] || new El("div");
    return registry[id];
  },
  querySelectorAll() { return []; },
  createElement(tag) { return new El(tag); },
  documentElement: new El("html"),
  body: new El("body"),
};

const calls = [];
const DATA = {
  "/api/info": {
    brand: "Xiaomi", model: "Pad 7 Ultra", codename: "uke", soc_model: "XRING O1", soc_manufacturer: "Xiaomi",
    android_release: "16", sdk: "36", abi: "arm64-v8a", security_patch: "2026-10-05",
    ab_update: true, slot_suffix: "_a", root: true, by_name_root: "/dev/block/by-name",
    block_device: "/dev/block/sdb", serial: "TEST123", partitions: {},
  },
  "/api/root": { available: true, method: "su", manager: "Magisk", version: "27.0", su_path: "/system/bin/su", reason: "su -> /system/bin/su" },
  "/api/device/stats": { battery_level: 80, battery_temp: 31.0, disk_total: 128849018880, disk_used: 42949672960 },
  "/api/part/table": {
    backup_dir: "D:/deepseek/iris/backups",
    partitions: [
      { name: "boot_a", size: 67108864, size_text: "64.0MiB" },
      { name: "modem_a", size: 104857600, size_text: "100.0MiB" },
    ],
  },
  "/api/modules": { manager: { name: "Magisk", version: "27.0" }, modules: [{ name: "LSPosed", version: "1.9.3", enabled: true, pending_remove: false }] },
  "/api/app/list": { count: 2, packages: ["com.example.a", "com.example.b"] },
  "/api/file/ls": { items: [{ name: "Download", dir: true, perm: "drwxrwx--x", size: "0" }, { name: "a.txt", dir: false, perm: "-rw-rw----", size: "12" }] },
  "/api/shell": { ok: true, code: 0, out: "uid=0(root)", err: "", duration: 0.01, root: true },
  "/api/tool": { result: { ok: true } },
  "/api/analyze": { kind: "avb", avb: { algorithm: "SHA256_RSA2048", flags: 0, verity_disabled: false, release_string: "avbtool 1.3" } },
  "/api/part/plan": { action: "restore", executable: true, warnings: [], blockers: [] },
};

global.window = global;
global.document = documentStub;
global.localStorage = { _m: {}, getItem(k) { return this._m[k] || null; }, setItem(k, v) { this._m[k] = v; } };
global.confirm = () => false;
global.fetch = async (url) => {
  const key = url.split("?")[0];
  calls.push(url);
  if (!(key in DATA)) throw new Error("no fixture: " + key);
  return { ok: true, text: async () => JSON.stringify(DATA[key]) };
};
global.window.__IRIS_TOKEN__ = "t";
global.window.__IRIS_VERSION__ = "0.3.0";

const src = fs.readFileSync(path.join(__dirname, "..", "iris", "web", "static", "app.js"), "utf8");

(async () => {
  let failures = 0;
  const check = (name, ok, detail) => {
    console.log((ok ? "✓ " : "✗ ") + name + (detail ? "  " + detail : ""));
    if (!ok) failures++;
  };

  try {
    eval(src);
    await new Promise((r) => setTimeout(r, 30));

    check("启动渲染设备页", registry.main && registry.main.innerHTML.length > 200);
    check("标题栏状态", registry.tbStatus && registry.tbStatus.classList.contains("on"));

    for (const sec of window.__IRIS_DEBUG__.SECTIONS) {
      const main = { innerHTML: "", dataset: {}, scrollTop: 0, querySelectorAll() { return []; } };
      let err = null;
      try {
        await sec.render(main);
      } catch (e) { err = e; }
      check(`页面 ${sec.name}`, !err && main.innerHTML.length > 120, err ? err.message : `${main.innerHTML.length} 字符`);
    }

    check("调用了设备接口", calls.some((u) => u.includes("/api/part/table")));
  } catch (e) {
    check("脚本加载", false, e.message);
  }

  console.log(`\n${failures === 0 ? "全部通过" : failures + " 项失败"}`);
  process.exit(failures ? 1 : 0);
})();
