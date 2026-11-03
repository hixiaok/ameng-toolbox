const TOKEN = window.__IRIS_TOKEN__;
const EMBED = window.__IRIS_DATA__ || null;

/* ---------------- 基础 ---------------- */
async function api(path, options = {}) {
  if (EMBED) {
    const key = path.split("?")[0];
    if (EMBED[key] !== undefined) return EMBED[key];
    if (key === "/api/info" && EMBED["/api/info_error"]) throw new Error(EMBED["/api/info_error"]);
    throw new Error("静态快照：该功能需要本地服务");
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

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const human = (n) => {
  const u = ["B", "KiB", "MiB", "GiB", "TiB"];
  let v = n, i = 0;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return (i === 0 ? v : v.toFixed(1)) + u[i];
};
function toast(msg, bad) {
  const el = document.createElement("div");
  el.className = "toast" + (bad ? " bad" : "");
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}
const panel = (title, body, extra = "") =>
  `<section class="panel"><div class="panel-head"><h2>${esc(title)}</h2>${extra}</div>${body}</section>`;

/* ---------------- 专区定义（对齐紫罗兰的 17 个入口） ---------------- */
const SECTIONS = [
  { id: "home", name: "主页", render: renderHome },
  { id: "scrcpy", name: "投屏", todo: ["全自动投屏", "虚拟按键", "自定义分辨率 / 帧率", "窗口置顶 / 屏幕常亮"],
    why: "依赖 scrcpy 组件，本仓库不打包第三方二进制。自己放一份 scrcpy.exe 到 tools/ 就能接上。" },
  { id: "flash", name: "基本刷入", todo: ["常规镜像刷入（boot / init_boot）", "解锁 / 回锁指令", "小米官方线刷", "格式化设备", "擦除 FRP", "修复 ADB 异常"],
    why: "写操作需要已解锁 BL 的真机，写错会变砖；没有设备可用于验证，不做半成品。" },
  { id: "visual", name: "可视刷写", render: renderVisual },
  { id: "oplus", name: "欧加线刷", todo: ["普通线刷 / 强力线刷", "AB 通刷", "仅 FastbootD", "修复 Super 真死", "ARB 熔断检测", "售后包模式 / 救砖"],
    why: "同样是写操作，且不同机型的分区布局差异大，需要真机逐台验证。" },
  { id: "edl", name: "EDL 刷写", todo: ["读分区表 / 读 / 写 / 擦", "恢复出厂", "写入 GPT", "格式化 LUN", "备份基带指纹", "强开 OEM"],
    why: "需要 9008 驱动与 firehose 引导文件，且是高危操作。" },
  { id: "downgrade", name: "降级助手", todo: ["OTA 降级", "云端版本解析", "多线程下载 + MD5 校验"],
    why: "依赖 OPPO/一加的私有接口，随时可能失效，也不适合复刻。" },
  { id: "modules", name: "模块专区", todo: ["批量安装 Magisk 模块", "自动识别 ROOT 管理器", "隐藏 ROOT"],
    why: "需要 root 权限与模块源。" },
  { id: "download", name: "断点续传", todo: ["多线程下载", "动态链接续传"],
    why: "依赖厂商下载接口。" },
  { id: "files", name: "文件传输", render: renderFiles },
  { id: "patch", name: "脱机修补", render: renderPatch },
  { id: "apps", name: "应用管理", render: renderApps },
  { id: "common", name: "安卓通用", render: renderCommon },
  { id: "payload", name: "Payload", render: renderPayload },
  { id: "backup", name: "备份助手", todo: ["备份相册 / 视频", "备份通讯录"],
    why: "需要真机，且大批量拉取建议先做传输层限速与断点。" },
  { id: "resources", name: "刷机资源", todo: ["常用刷机文件下载"],
    why: "需要外部下载源。" },
  { id: "rom", name: "ROM 专区", todo: ["卡刷包 / 线刷包 / boot 镜像下载"],
    why: "依赖厂商接口与服务器。" },
];

/* ---------------- 导航 ---------------- */
function buildNav() {
  $("#nav").innerHTML = SECTIONS.map((s, i) =>
    `<button class="nav${i === 0 ? " active" : ""}" data-id="${s.id}">${esc(s.name)}</button>`).join("");
  document.querySelectorAll(".nav").forEach((b) => {
    b.addEventListener("click", () => {
      document.querySelectorAll(".nav").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      show(b.dataset.id);
    });
  });
}

async function show(id) {
  const sec = SECTIONS.find((s) => s.id === id);
  const main = $("#main");
  if (!sec) return;
  if (!sec.render) {
    main.innerHTML = panel(sec.name,
      `<p class="todo-why">${esc(sec.why)}</p>
       <ul class="todo-list">${sec.todo.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>
       <p class="meta">这些是该专区的原始功能项，标出来是为了不假装实现。</p>`);
    return;
  }
  main.innerHTML = '<p class="meta">加载中…</p>';
  try {
    await sec.render(main);
  } catch (e) {
    main.innerHTML = `<div class="alert">${esc(e.message)}</div>`;
  }
}

/* ---------------- 主页 ---------------- */
const HOME_FIELDS = [
  ["品牌", (p) => p.brand], ["型号", (p) => p.model], ["代号", (p) => p.codename],
  ["Android", (p) => `${p.android_release || "?"} (SDK ${p.sdk || "?"})`],
  ["SoC", (p) => p.soc_model], ["架构", (p) => p.abi],
  ["安全补丁", (p) => p.security_patch],
  ["槽位", (p) => (p.ab_update ? `A/B ${p.slot_suffix || ""}` : "单槽位")],
  ["ROOT", (p) => (p.root ? "是" : "否")],
  ["by-name 根", (p) => p.by_name_root || "未探测到"],
];

async function renderHome(main) {
  let p = null;
  try { p = await api("/api/info"); } catch (e) { p = null; }

  const info = p
    ? `<div class="kv2">${HOME_FIELDS.map(([k, f]) =>
        `<div class="row2"><span class="k">${esc(k)}</span><span class="v">${esc(f(p) || "—")}</span></div>`).join("")}</div>`
    : `<p class="empty-inline">未检测到设备：连接手机并开启 USB 调试后刷新本页。</p>`;

  const acts = [
    ["reboot_system", "重启系统"], ["reboot_recovery", "Recovery"], ["reboot_bootloader", "Bootloader"],
    ["reboot_fastbootd", "Fastbootd"], ["screenshot", "截图"], ["record", "录屏 15s"],
    ["tcpip", "无线调试"], ["logcat", "抓日志"], ["shutdown", "关机"],
  ].map(([a, n]) => `<button class="act" data-act="${a}" ${p ? "" : "disabled"}>${n}</button>`).join("");

  main.innerHTML = [
    panel("设备信息", info),
    panel("快捷操作", `<div class="acts">${acts}</div><pre class="output hidden" id="action-out"></pre>`),
  ].join("");

  document.querySelectorAll(".act").forEach((b) => {
    b.addEventListener("click", async () => {
      b.disabled = true;
      try {
        const r = await api("/api/device/action?name=" + b.dataset.act);
        toast(r.message, !r.ok);
        if (r.detail) { const o = $("#action-out"); o.textContent = r.detail; o.classList.remove("hidden"); }
      } catch (e) { toast(e.message, true); }
      finally { b.disabled = false; }
    });
  });

  if (p) {
    $("#ds-state").textContent = "已连接";
    $("#ds-code").textContent = p.codename || p.model || "—";
    $("#ds-root").textContent = p.root ? "是" : "否";
    $("#ds-slot").textContent = p.ab_update ? (p.slot_suffix || "A/B") : "单槽位";
    $("#foot-state").textContent = "在线";
  }
}

/* ---------------- 镜像分析（可视刷写 / Payload 共用） ---------------- */
let lastAnalysis = null;

function imageViewer() {
  return `
    ${panel("选择镜像", `
      <div class="filerow">
        <button class="btn btn-primary" id="pick">选择文件</button>
        <span class="path" id="file-name">支持 payload / super / boot / vbmeta / GPT / sparse</span>
      </div>`, "")}
    <section class="panel hidden" id="result-panel"><div class="panel-head"><h2 id="result-title">结果</h2><span class="tag" id="result-kind">-</span></div><div id="result-body"></div></section>
  `;
}

function bindUploader(main) {
  const input = $("#file");
  input.value = "";
  input.onchange = () => input.files[0] && upload(input.files[0]);
  $("#pick").onclick = () => input.click();
  window.ondragover = (e) => e.preventDefault();
  window.ondrop = (e) => {
    e.preventDefault();
    const f = e.dataTransfer?.files[0];
    if (f) upload(f);
  };
}

async function upload(file) {
  const panelEl = $("#result-panel");
  $("#file-name").textContent = `${file.name} · ${(file.size / 1048576).toFixed(1)} MB`;
  $("#result-title").textContent = file.name;
  $("#result-kind").textContent = "分析中…";
  panelEl.classList.remove("hidden");
  $("#result-body").innerHTML = "";
  try {
    const data = await api("/api/upload?name=" + encodeURIComponent(file.name), {
      method: "POST", body: file, headers: { "Content-Type": "application/octet-stream" },
    });
    lastAnalysis = data;
    renderAnalysis(data);
  } catch (e) {
    $("#result-kind").textContent = "失败";
    $("#result-body").innerHTML = `<div class="alert">${esc(e.message)}</div>`;
  }
}

function renderAnalysis(data) {
  const kindName = { gpt: "GPT", lp: "super", payload: "payload", boot: "boot", avb: "vbmeta", sparse: "sparse" }[data.kind] || data.kind;
  $("#result-kind").textContent = kindName;
  const body = $("#result-body");

  if (data.kind === "payload") {
    const p = data.payload;
    body.innerHTML = `<p class="meta">payload v${p.version} · 块 ${p.block_size}B · ${p.partition_count} 个分区</p>
      <div class="table-wrap"><table><thead><tr><th>分区</th><th>解包后</th><th>类型</th><th></th></tr></thead><tbody>
      ${p.partitions.map((x) => `<tr><td class="mono">${esc(x.name)}</td><td>${human(x.size_bytes)}</td>
        <td class="muted">${esc(x.operations.join(", "))}</td>
        <td>${x.extractable ? `<button class="btn" data-part="${esc(x.name)}">提取</button>` : "—"}</td></tr>`).join("")}
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
        <td>${data.ticket ? `<button class="btn" data-part="${esc(p.name)}">提取</button>` : ""}</td></tr>`).join("")}
      </tbody></table></div>`;
    body.querySelectorAll("button[data-part]").forEach((b) => {
      b.onclick = () => extractPart(data.ticket, b.dataset.part, b);
    });
    return;
  }

  if (data.kind === "boot") {
    const b = data.boot;
    body.innerHTML = `<div class="kv2">
      ${[["header", "v" + b.header_version], ["内核", human(b.kernel_size) + " @ " + b.kernel_offset],
         ["ramdisk", human(b.ramdisk_size) + " @ " + b.ramdisk_offset], ["系统版本", b.os_version]]
        .map(([k, v]) => `<div class="row2"><span class="k">${esc(k)}</span><span class="v">${esc(v)}</span></div>`).join("")}
      </div><p class="meta">cmdline：${esc(b.cmdline || "—")}</p>`;
    return;
  }

  if (data.kind === "avb") {
    const a = data.avb;
    body.innerHTML = `<div class="kv2">
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

async function renderVisual(main) { main.innerHTML = imageViewer(); bindUploader(main); }
async function renderPayload(main) { main.innerHTML = imageViewer(); bindUploader(main); }

/* ---------------- 本地工具 ---------------- */
function toolsCard() {
  return panel("本地文件工具", `
    <div class="filerow">
      <input class="input" id="tool-path" placeholder="文件路径" spellcheck="false">
      <select class="input" id="tool-op" style="flex:0 0 140px">
        <option value="hash">计算哈希</option>
        <option value="bootunpack">拆 boot</option>
        <option value="sparsepack">打包 sparse</option>
        <option value="gptxml">GPT 转 XML</option>
        <option value="supermake">合并 super</option>
        <option value="split">拆分文件</option>
        <option value="join">合并分片</option>
      </select>
      <input class="input" id="tool-arg" placeholder="输出路径 / 大小 / 名字=文件;名字=文件" spellcheck="false">
      <button class="btn btn-primary" id="btn-tool">执行</button>
    </div>
    <pre class="output hidden" id="tool-out"></pre>`);
}

function bindTools() {
  $("#btn-tool").onclick = async () => {
    const target = $("#tool-path").value.trim();
    const op = $("#tool-op").value;
    const arg = $("#tool-arg").value.trim();
    const out = $("#tool-out");
    if (!target) return toast("先填文件路径", true);
    out.classList.remove("hidden"); out.textContent = "执行中…";
    try {
      const r = await api(`/api/tool?op=${op}&path=${encodeURIComponent(target)}&arg=${encodeURIComponent(arg)}`);
      out.textContent = JSON.stringify(r.result, null, 2);
    } catch (e) { out.textContent = "失败：" + e.message; }
  };
}

async function renderCommon(main) {
  main.innerHTML = toolsCard() + panel("说明", `<p class="about-p">
    这些是纯本地操作：不连接手机、不需要 root。路径是你电脑上的真实路径。</p>`);
  bindTools();
}

async function renderPatch(main) {
  main.innerHTML = panel("脱机修补", `
    <p class="about-p">拆 boot 镜像、看 vbmeta 签名。这两步不需要 root，也不需要解锁。</p>
    <div class="filerow">
      <input class="input" id="patch-path" placeholder="boot.img 或 vbmeta.img 路径" spellcheck="false">
      <button class="btn" id="btn-boot">拆 boot</button>
      <button class="btn" id="btn-avb">看 vbmeta</button>
    </div>
    <pre class="output hidden" id="patch-out"></pre>`);

  const run = async (op) => {
    const p = $("#patch-path").value.trim();
    if (!p) return toast("先填路径", true);
    const out = $("#patch-out");
    out.classList.remove("hidden"); out.textContent = "处理中…";
    try {
      const r = await api(`/api/tool?op=${op}&path=${encodeURIComponent(p)}&arg=${encodeURIComponent(p + "-out")}`);
      out.textContent = JSON.stringify(r.result, null, 2);
    } catch (e) { out.textContent = "失败：" + e.message; }
  };
  $("#btn-boot").onclick = () => run("bootunpack");
  $("#btn-avb").onclick = async () => {
    const p = $("#patch-path").value.trim();
    if (!p) return toast("先填路径", true);
    const out = $("#patch-out");
    out.classList.remove("hidden"); out.textContent = "读取中…";
    try {
      const r = await api("/api/analyze?path=" + encodeURIComponent(p));
      out.textContent = JSON.stringify(r, null, 2);
    } catch (e) { out.textContent = "失败：" + e.message; }
  };
}

/* ---------------- 文件传输 ---------------- */
async function renderFiles(main) {
  main.innerHTML = panel("设备文件", `
    <div class="filerow">
      <input class="input" id="remote-path" value="/sdcard" spellcheck="false">
      <button class="btn" id="btn-ls">列出</button>
      <button class="btn" id="btn-pull">拉取到 shots</button>
    </div>
    <div id="file-list"></div>`) + panel("安装 APK", `
    <div class="filerow">
      <button class="btn btn-primary" id="pick-apk">选择 APK</button>
      <span class="path" id="apk-name">未选择</span>
    </div>
    <p class="meta" id="apk-result"></p>`);

  $("#btn-ls").onclick = async () => {
    const list = $("#file-list");
    list.innerHTML = '<p class="meta">读取中…</p>';
    try {
      const r = await api("/api/file/ls?path=" + encodeURIComponent($("#remote-path").value.trim()));
      list.innerHTML = `<div class="table-wrap"><table><thead><tr><th>权限</th><th>大小</th><th>名称</th></tr></thead><tbody>
        ${r.items.map((i) => `<tr><td class="mono muted">${esc(i.perm)}</td><td>${esc(i.size)}</td><td class="mono">${esc(i.name)}</td></tr>`).join("")}
      </tbody></table></div>`;
    } catch (e) { list.innerHTML = `<div class="alert">${esc(e.message)}</div>`; }
  };

  $("#btn-pull").onclick = async () => {
    try {
      const r = await api(`/api/file/pull?remote=${encodeURIComponent($("#remote-path").value.trim())}`);
      toast(r.message, !r.ok);
    } catch (e) { toast(e.message, true); }
  };

  const apkInput = document.createElement("input");
  apkInput.type = "file"; apkInput.accept = ".apk";
  apkInput.onchange = async () => {
    const f = apkInput.files[0];
    if (!f) return;
    $("#apk-name").textContent = f.name;
    $("#apk-result").textContent = "安装中…";
    try {
      const r = await api("/api/app/install?name=" + encodeURIComponent(f.name), {
        method: "POST", body: f, headers: { "Content-Type": "application/vnd.android.package-archive" },
      });
      $("#apk-result").textContent = r.message;
    } catch (e) { $("#apk-result").textContent = "失败：" + e.message; }
  };
  $("#pick-apk").onclick = () => apkInput.click();
}

/* ---------------- 应用管理 ---------------- */
async function renderApps(main) {
  main.innerHTML = panel("应用管理", `
    <div class="filerow">
      <button class="btn" id="btn-apps">读取第三方应用</button>
      <button class="btn" id="btn-apps-all">含系统应用</button>
      <span class="meta" id="apps-count"></span>
    </div>
    <div id="apps-table"></div>`);

  const load = async (all) => {
    const box = $("#apps-table");
    box.innerHTML = '<p class="meta">读取中…</p>';
    try {
      const data = await api("/api/app/list" + (all ? "?all=1" : ""));
      $("#apps-count").textContent = `${data.count} 个`;
      box.innerHTML = `<div class="table-wrap"><table><thead><tr><th>包名</th><th></th></tr></thead><tbody>
        ${data.packages.map((p) => `<tr><td class="mono">${esc(p)}</td><td class="nowrap">
          <button class="btn" data-op="freeze" data-pkg="${esc(p)}">冻结</button>
          <button class="btn" data-op="unfreeze" data-pkg="${esc(p)}">解冻</button>
          <button class="btn" data-op="extract" data-pkg="${esc(p)}">提取</button>
          <button class="btn" data-op="uninstall" data-pkg="${esc(p)}">卸载</button>
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
    } catch (e) { box.innerHTML = `<div class="alert">${esc(e.message)}</div>`; }
  };
  $("#btn-apps").onclick = () => load(false);
  $("#btn-apps-all").onclick = () => load(true);
}

/* ---------------- 启动 ---------------- */
buildNav();
show("home");
