package com.iris.toolbox;

import android.content.Context;
import android.os.Build;
import android.os.StatFs;

import org.json.JSONObject;

import java.io.File;
import java.util.Locale;

/** 设备画像：Build 属性 + root 状态 + 存储。 */
final class Info {

    private Info() {
    }

    static JSONObject json(Context ctx) throws Exception {
        JSONObject o = new JSONObject();
        o.put("brand", Build.BRAND);
        o.put("model", Build.MODEL);
        o.put("device", Build.DEVICE);
        o.put("release", Build.VERSION.RELEASE);
        o.put("sdk", Build.VERSION.SDK_INT);
        String abi = Build.SUPPORTED_ABIS.length > 0 ? Build.SUPPORTED_ABIS[0] : "";
        o.put("abi", abi);
        o.put("version", ctx.getPackageManager().getPackageInfo(ctx.getPackageName(), 0).versionName);

        boolean root = Shell.hasRoot();
        o.put("root", root);
        o.put("manager", root ? Shell.manager() : "");
        o.put("su", root ? Shell.suPath() : "");

        File base = ctx.getExternalFilesDir(null);
        if (base == null) {
            base = ctx.getFilesDir();
        }
        File backups = new File(base, "backups");
        if (!backups.isDirectory()) {
            backups.mkdirs();
        }
        o.put("backupDir", backups.getAbsolutePath());

        try {
            StatFs fs = new StatFs(backups.getAbsolutePath());
            long total = fs.getTotalBytes();
            long free = fs.getAvailableBytes();
            o.put("total", total);
            o.put("free", free);
            o.put("storage", String.format(Locale.US, "%.1f / %.1f GiB",
                    free / 1073741824.0, total / 1073741824.0));
        } catch (Exception ignored) {
        }
        return o;
    }
}
