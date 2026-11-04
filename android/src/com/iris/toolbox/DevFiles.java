package com.iris.toolbox;

import org.json.JSONArray;
import org.json.JSONObject;

/** 文件浏览：普通目录走 sh，受保护目录走 su；用 stat 输出，避免 ls 的时间格式差异。 */
final class DevFiles {

    private DevFiles() {
    }

    static JSONObject ls(String path, boolean root) throws Exception {
        if (path == null || path.isEmpty()) {
            path = "/sdcard";
        }
        String base = path.endsWith("/") ? path.substring(0, path.length() - 1) : path;
        if (base.isEmpty()) {
            base = "/";
        }
        String script = "for f in " + Shell.q(base) + "/* " + Shell.q(base) + "/.[!.]*; do "
                + "[ -e \"$f\" ] || continue; n=$(basename \"$f\"); "
                + "s=$(stat -c '%A|%F|%s' \"$f\" 2>/dev/null); "
                + "[ -n \"$s\" ] && echo \"$s|$n\"; done";

        Shell.R r = root ? Shell.su(script, 30000) : Shell.sh(script, 30000);
        if (!r.ok() && r.out.trim().isEmpty()) {
            String hint = r.err.trim().isEmpty() ? ("退出码 " + r.code) : r.err.trim().split("\n")[0];
            throw new Exception("读取失败：" + hint + (root ? "" : "（受保护目录请打开 root 开关）"));
        }

        JSONArray arr = new JSONArray();
        for (String line : r.out.split("\n")) {
            String[] f = line.split("\\|", 4);
            if (f.length < 4) {
                continue;
            }
            String name = f[3];
            while (name.length() > 1 && name.endsWith("/")) {
                name = name.substring(0, name.length() - 1);
            }
            if (name.equals(".") || name.equals("..")) {
                continue;
            }
            JSONObject o = new JSONObject();
            o.put("name", name);
            o.put("perm", f[0]);
            o.put("dir", f[1].contains("directory"));
            try {
                o.put("size", Long.parseLong(f[2]));
            } catch (NumberFormatException e) {
                o.put("size", 0);
            }
            arr.put(o);
        }

        JSONArray sorted = new JSONArray();
        for (int i = 0; i < arr.length(); i++) {
            JSONObject o = arr.getJSONObject(i);
            if (o.getBoolean("dir")) {
                sorted.put(o);
            }
        }
        for (int i = 0; i < arr.length(); i++) {
            JSONObject o = arr.getJSONObject(i);
            if (!o.getBoolean("dir")) {
                sorted.put(o);
            }
        }
        JSONObject out = new JSONObject();
        out.put("items", sorted);
        out.put("path", base);
        return out;
    }

    static JSONObject read(String path, boolean root, int limit) throws Exception {
        int max = Math.max(1024, Math.min(limit, 512 * 1024));
        Shell.R r = (root ? Shell.su("head -c " + max + " " + Shell.q(path), 30000)
                : Shell.sh("head -c " + max + " " + Shell.q(path), 30000));
        if (!r.ok()) {
            throw new Exception("读取失败：" + (r.err.trim().isEmpty() ? ("退出码 " + r.code) : r.err.trim().split("\n")[0]));
        }
        JSONObject out = new JSONObject();
        out.put("text", r.out);
        out.put("truncated", r.out.getBytes("UTF-8").length >= max);
        return out;
    }
}
