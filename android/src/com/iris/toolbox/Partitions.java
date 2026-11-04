package com.iris.toolbox;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * 分区：列表、备份、还原。
 *
 * 备份不落 /data/local/tmp：直接 `su -c dd if=分区`，把 stdout 边读边写进
 * 应用目录并同步算 SHA-256。这样绕开了 FUSE / SELinux 对 root 写
 * /sdcard/Android/data 的各种限制，也省掉一份临时文件。
 *
 * 还原反过来：把镜像喂给 `su -c "dd of=分区"` 的 stdin。
 */
final class Partitions {

    static final class Part {
        String name = "";
        String path = "";
        long size = 0;
    }

    interface Progress {
        void on(double ratio, String label);
    }

    private Partitions() {
    }

    static List<Part> list() throws Exception {
        String script =
                "for f in /dev/block/by-name/* /dev/block/bootdevice/by-name/*; do "
                        + "[ -e \"$f\" ] || continue; n=$(basename \"$f\"); "
                        + "s=$(blockdev --getsize64 \"$f\" 2>/dev/null); "
                        + "[ -n \"$s\" ] && echo \"$n|$f|$s\"; done";
        Shell.R r = Shell.su(script, 40000);
        if (!r.ok()) {
            throw new Exception("读取分区表失败：" + firstLine(r.err.isEmpty() ? r.out : r.err));
        }
        List<Part> out = new ArrayList<>();
        for (String line : r.out.split("\n")) {
            String[] f = line.trim().split("\\|");
            if (f.length != 3) {
                continue;
            }
            try {
                Part p = new Part();
                p.name = f[0];
                p.path = f[1];
                p.size = Long.parseLong(f[2]);
                out.add(p);
            } catch (NumberFormatException ignored) {
            }
        }
        if (out.isEmpty()) {
            throw new Exception("没有读到分区：设备可能没有 by-name，或 su 未授权");
        }
        out.sort(new java.util.Comparator<Part>() {
            @Override
            public int compare(Part a, Part b) {
                return a.name.compareToIgnoreCase(b.name);
            }
        });
        return out;
    }

    static Part find(String name) throws Exception {
        for (Part p : list()) {
            if (p.name.equals(name)) {
                return p;
            }
        }
        throw new Exception("设备上没有分区 " + name);
    }

    static JSONObject listJson() throws Exception {
        JSONArray arr = new JSONArray();
        for (Part p : list()) {
            JSONObject o = new JSONObject();
            o.put("name", p.name);
            o.put("path", p.path);
            o.put("size", p.size);
            arr.put(o);
        }
        JSONObject out = new JSONObject();
        out.put("parts", arr);
        return out;
    }

    static JSONObject backup(String name, File dir, Progress progress) throws Exception {
        if (!Shell.hasRoot()) {
            throw new Exception("需要 root 才能备份分区");
        }
        Part part = find(name);
        if (!dir.isDirectory() && !dir.mkdirs()) {
            throw new Exception("无法创建备份目录：" + dir);
        }
        String stamp = new java.text.SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(new java.util.Date());
        File outFile = new File(dir, name + "-" + stamp + ".img");

        Process p = new ProcessBuilder("su", "-c",
                "dd if=" + Shell.q(part.path) + " bs=4M 2>/dev/null").start();
        Thread errDrain = drain(p.getErrorStream());

        MessageDigest md = MessageDigest.getInstance("SHA-256");
        long done = 0;
        long lastReport = 0;
        boolean ok;
        try (InputStream in = p.getInputStream();
             FileOutputStream fos = new FileOutputStream(outFile)) {
            OutputStream os = new BufferedOutputStream(fos, 1 << 20);
            byte[] buf = new byte[1 << 20];
            int n;
            while ((n = in.read(buf)) > 0) {
                os.write(buf, 0, n);
                md.update(buf, 0, n);
                done += n;
                if (done - lastReport > (16L << 20)) {
                    lastReport = done;
                    if (progress != null) {
                        double ratio = part.size > 0 ? Math.min(1.0, (double) done / part.size) : 0;
                        progress.on(ratio, human(done) + (part.size > 0 ? " / " + human(part.size) : ""));
                    }
                }
            }
            os.flush();
            fos.getFD().sync();
        }
        int code = p.waitFor();
        errDrain.join(1000);
        ok = code == 0 && done > 0;

        if (!ok) {
            outFile.delete();
            throw new Exception("dd 备份失败（退出码 " + code + "）");
        }
        if (part.size > 0 && done != part.size) {
            outFile.delete();
            throw new Exception("备份不完整：读到 " + human(done) + "，分区大小 " + human(part.size));
        }

        StringBuilder sha = new StringBuilder();
        for (byte b : md.digest()) {
            sha.append(String.format("%02x", b));
        }
        JSONObject out = new JSONObject();
        out.put("ok", true);
        out.put("path", outFile.getAbsolutePath());
        out.put("size", done);
        out.put("sha256", sha.toString());
        out.put("name", name);
        return out;
    }

    static JSONObject restore(String name, File image, Progress progress) throws Exception {
        if (!Shell.hasRoot()) {
            throw new Exception("需要 root 才能写分区");
        }
        Part part = find(name);
        long length = image.length();
        if (part.size > 0 && length > part.size) {
            throw new Exception("镜像 " + human(length) + " 大于分区 " + human(part.size) + "，写进去会越界");
        }

        String localSha = sha256(image);
        Process p = new ProcessBuilder("su", "-c",
                "dd of=" + Shell.q(part.path) + " bs=4M 2>/dev/null").start();
        Thread errDrain = drain(p.getErrorStream());
        long done = 0;
        try (InputStream in = new FileInputStream(image);
             OutputStream os = p.getOutputStream()) {
            byte[] buf = new byte[1 << 20];
            int n;
            while ((n = in.read(buf)) > 0) {
                os.write(buf, 0, n);
                done += n;
                if (progress != null && length > 0) {
                    progress.on(Math.min(1.0, (double) done / length), human(done) + " / " + human(length));
                }
            }
            os.flush();
        }
        int code = p.waitFor();
        errDrain.join(1000);
        Shell.su("sync", 120000);
        if (code != 0) {
            throw new Exception("dd 写入失败（退出码 " + code + "）");
        }

        JSONObject out = new JSONObject();
        out.put("ok", true);
        out.put("written", done);
        out.put("name", name);

        if (length <= 256L << 20) {
            Shell.R r = Shell.su("sha256sum " + Shell.q(part.path), 600000);
            String got = r.ok() && !r.out.trim().isEmpty() ? r.out.trim().split("\\s+")[0] : "";
            boolean verified = !got.isEmpty() && got.equalsIgnoreCase(localSha);
            out.put("verified", verified);
            out.put("device_sha256", got);
            if (!got.isEmpty() && !verified) {
                throw new Exception("写入后校验失败：设备上的内容与镜像不一致");
            }
        } else {
            out.put("verified", false);
            out.put("note", "分区较大，跳过整段回读校验");
        }
        return out;
    }

    static String sha256(File f) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        try (InputStream in = new FileInputStream(f)) {
            byte[] buf = new byte[1 << 20];
            int n;
            while ((n = in.read(buf)) > 0) {
                md.update(buf, 0, n);
            }
        }
        StringBuilder sb = new StringBuilder();
        for (byte b : md.digest()) {
            sb.append(String.format("%02x", b));
        }
        return sb.toString();
    }

    static Thread drain(InputStream in) {
        Thread t = new Thread(new Runnable() {
            @Override
            public void run() {
                byte[] buf = new byte[4096];
                try {
                    while (in.read(buf) > 0) {
                        // 丢到 /dev/null 的 stderr 也可能有 su 的提示，读掉防止阻塞
                    }
                } catch (Exception ignored) {
                }
            }
        });
        t.setDaemon(true);
        t.start();
        return t;
    }

    static String human(long n) {
        String[] units = {"B", "KiB", "MiB", "GiB", "TiB"};
        double v = n;
        int i = 0;
        while (v >= 1024 && i < units.length - 1) {
            v /= 1024;
            i++;
        }
        return i == 0 ? String.format(Locale.US, "%.0f%s", v, units[i])
                : String.format(Locale.US, "%.1f%s", v, units[i]);
    }

    private static String firstLine(String s) {
        String t = s.trim();
        int i = t.indexOf('\n');
        return i < 0 ? t : t.substring(0, i);
    }
}
