package com.iris.toolbox;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** 应用管理：列表、冻结/解冻、清数据、卸载（当前用户）。 */
final class Apps {

    private Apps() {
    }

    static JSONObject list(boolean all) throws Exception {
        Shell.R r = Shell.sh("pm list packages" + (all ? "" : " -3"), 45000);
        if (!r.ok()) {
            throw new Exception("读取应用列表失败：" + firstLine(r.err.isEmpty() ? r.out : r.err));
        }
        Set<String> disabled = new HashSet<>();
        Shell.R d = Shell.sh("pm list packages -d", 20000);
        if (d.ok()) {
            for (String line : d.out.split("\n")) {
                String t = line.trim();
                if (t.startsWith("package:")) {
                    disabled.add(t.substring(8));
                }
            }
        }
        List<String> pkgs = new ArrayList<>();
        for (String line : r.out.split("\n")) {
            String t = line.trim();
            if (t.startsWith("package:")) {
                pkgs.add(t.substring(8));
            }
        }
        pkgs.sort(new java.util.Comparator<String>() {
            @Override
            public int compare(String a, String b) {
                return a.compareToIgnoreCase(b);
            }
        });

        JSONArray arr = new JSONArray();
        for (String pkg : pkgs) {
            JSONObject o = new JSONObject();
            o.put("pkg", pkg);
            o.put("disabled", disabled.contains(pkg));
            arr.put(o);
        }
        JSONObject out = new JSONObject();
        out.put("apps", arr);
        out.put("count", arr.length());
        return out;
    }

    static JSONObject action(String pkg, String action) throws Exception {
        if (pkg == null || !pkg.matches("[A-Za-z0-9._]+")) {
            throw new Exception("非法包名：" + pkg);
        }
        String cmd;
        String label;
        switch (action) {
            case "freeze":
                cmd = "pm disable-user --user 0 " + pkg;
                label = "冻结";
                break;
            case "unfreeze":
                cmd = "pm enable " + pkg;
                label = "解冻";
                break;
            case "uninstall":
                cmd = "pm uninstall --user 0 " + pkg;
                label = "卸载";
                break;
            case "clear":
                cmd = "pm clear " + pkg;
                label = "清除数据";
                break;
            default:
                throw new Exception("未知操作：" + action);
        }
        Shell.R r = Shell.hasRoot() ? Shell.su(cmd, 60000) : Shell.sh(cmd, 60000);
        String text = (r.out + "\n" + r.err).trim();
        boolean ok = r.ok() && (text.contains("Success") || text.contains("new state"));
        if (!ok) {
            throw new Exception(label + "失败：" + firstLine(text.isEmpty() ? ("退出码 " + r.code) : text));
        }
        JSONObject out = new JSONObject();
        out.put("message", label + "成功：" + pkg);
        return out;
    }

    private static String firstLine(String s) {
        String t = s.trim();
        int i = t.indexOf('\n');
        return i < 0 ? t : t.substring(0, i);
    }
}
