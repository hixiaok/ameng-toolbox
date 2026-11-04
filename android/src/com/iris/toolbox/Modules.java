package com.iris.toolbox;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/** Magisk / KernelSU / APatch 模块：目录约定一致，只有安装命令不同。 */
final class Modules {

    static final String DIR = "/data/adb/modules";

    private Modules() {
    }

    static final class M {
        String name = "";
        String version = "";
        String author = "";
        String desc = "";
        boolean enabled = true;
        boolean pendingRemove = false;
    }

    static JSONObject listJson() throws Exception {
        JSONObject out = new JSONObject();
        if (!Shell.hasRoot()) {
            out.put("manager", "");
            out.put("modules", new JSONArray());
            return out;
        }
        out.put("manager", Shell.manager());

        String script = "for d in " + DIR + "/*; do "
                + "[ -d \"$d\" ] || continue; n=$(basename \"$d\"); echo \"=== $n\"; "
                + "cat \"$d/module.prop\" 2>/dev/null; "
                + "[ -e \"$d/disable\" ] && echo \"__DISABLE__\"; "
                + "[ -e \"$d/remove\" ] && echo \"__REMOVE__\"; done";
        Shell.R r = Shell.su(script, 30000);
        if (!r.ok()) {
            throw new Exception("读取模块失败：" + firstLine(r.err.isEmpty() ? r.out : r.err));
        }

        List<M> mods = new ArrayList<>();
        M cur = null;
        String name = "";
        String version = "";
        String author = "";
        String desc = "";
        for (String raw : r.out.split("\n")) {
            String line = raw.trim();
            if (line.startsWith("=== ")) {
                if (cur != null) {
                    mods.add(cur);
                }
                cur = new M();
                cur.name = line.substring(4).trim();
                name = "";
                version = author = desc = "";
                continue;
            }
            if (cur == null) {
                continue;
            }
            if (line.equals("__DISABLE__")) {
                cur.enabled = false;
            } else if (line.equals("__REMOVE__")) {
                cur.pendingRemove = true;
            } else {
                int eq = line.indexOf('=');
                if (eq > 0 && !line.startsWith("#")) {
                    String k = line.substring(0, eq).trim();
                    String v = line.substring(eq + 1).trim();
                    if (k.equals("name") && !v.isEmpty()) {
                        name = v;
                    } else if (k.equals("version")) {
                        version = v;
                    } else if (k.equals("author")) {
                        author = v;
                    } else if (k.equals("description")) {
                        desc = v;
                    }
                }
            }
            cur.version = version;
            cur.author = author;
            cur.desc = desc;
            if (!name.isEmpty()) {
                cur.name = name;
            }
        }
        if (cur != null) {
            mods.add(cur);
        }
        mods.sort(new Comparator<M>() {
            @Override
            public int compare(M a, M b) {
                if (a.enabled != b.enabled) {
                    return a.enabled ? 1 : -1;
                }
                return a.name.compareToIgnoreCase(b.name);
            }
        });

        JSONArray arr = new JSONArray();
        for (M m : mods) {
            JSONObject o = new JSONObject();
            o.put("name", m.name);
            o.put("version", m.version);
            o.put("author", m.author);
            o.put("description", m.desc);
            o.put("enabled", m.enabled);
            o.put("pendingRemove", m.pendingRemove);
            arr.put(o);
        }
        out.put("modules", arr);
        return out;
    }

    static JSONObject toggle(String name, boolean enabled) throws Exception {
        checkName(name);
        String flag = DIR + "/" + name + "/disable";
        Shell.R r = Shell.su((enabled ? "rm -f " : "touch ") + Shell.q(flag), 15000);
        if (!r.ok()) {
            throw new Exception((enabled ? "启用" : "禁用") + "失败：" + firstLine(r.err.isEmpty() ? r.out : r.err));
        }
        JSONObject out = new JSONObject();
        out.put("message", (enabled ? "已启用 " : "已禁用 ") + name + "，重启后完全生效");
        return out;
    }

    static JSONObject remove(String name) throws Exception {
        checkName(name);
        Shell.R r = Shell.su("touch " + Shell.q(DIR + "/" + name + "/remove"), 15000);
        if (!r.ok()) {
            throw new Exception("标记卸载失败：" + firstLine(r.err.isEmpty() ? r.out : r.err));
        }
        JSONObject out = new JSONObject();
        out.put("message", "已标记卸载 " + name + "，重启后生效");
        return out;
    }

    static JSONObject install(String zipPath) throws Exception {
        File zip = new File(zipPath);
        if (!zip.isFile()) {
            throw new Exception("模块包不存在：" + zipPath);
        }
        if (!zip.getName().toLowerCase().endsWith(".zip")) {
            throw new Exception("模块必须是 zip 包");
        }
        if (!Shell.hasRoot()) {
            throw new Exception("需要 root 才能安装模块");
        }
        String mgr = Shell.manager();
        String cmd;
        if (mgr.contains("Magisk")) {
            cmd = Shell.toolPath() + "magisk --install-module " + Shell.q(zip.getAbsolutePath());
        } else if (mgr.contains("KernelSU")) {
            cmd = Shell.toolPath() + "ksud module install " + Shell.q(zip.getAbsolutePath());
        } else if (mgr.contains("APatch")) {
            cmd = Shell.toolPath() + "apd module install " + Shell.q(zip.getAbsolutePath());
        } else {
            throw new Exception("没有识别到模块管理器：" + mgr);
        }
        Shell.R r = Shell.su(cmd, 180000);
        String text = (r.out + "\n" + r.err).trim();
        boolean ok = r.ok() && !text.toLowerCase().contains("installation failed")
                && !text.toLowerCase().contains("install failed");
        if (!ok) {
            throw new Exception("安装失败：" + firstLine(text.isEmpty() ? ("退出码 " + r.code) : text));
        }
        JSONObject out = new JSONObject();
        out.put("message", "已安装到 " + mgr + "，重启后生效");
        return out;
    }

    private static void checkName(String name) throws Exception {
        if (name == null || name.isEmpty() || name.contains("/") || name.contains("\\")
                || name.equals(".") || name.equals("..")) {
            throw new Exception("非法模块名：" + name);
        }
    }

    private static String firstLine(String s) {
        String t = s.trim();
        int i = t.indexOf('\n');
        return i < 0 ? t : t.substring(0, i);
    }
}
