package com.iris.toolbox;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeUnit;

/**
 * 设备侧命令执行。
 *
 * 和 PC 版最大的不同：在手机上可以直接 exec(["su", "-c", cmd])，参数作为
 * 独立 argv 传给 su，不需要拼任何引号——PC 版那层 shlex 在这里天然不存在。
 */
final class Shell {

    static final class R {
        int code = -1;
        String out = "";
        String err = "";
        long ms = 0;
        boolean timedOut = false;

        boolean ok() {
            return code == 0 && !timedOut;
        }
    }

    private Shell() {
    }

    static R exec(String[] argv, long timeoutMs) {
        long started = System.currentTimeMillis();
        R r = new R();
        Process p;
        try {
            p = new ProcessBuilder(argv).start();
        } catch (IOException e) {
            r.err = "无法启动 " + argv[0] + "：" + e.getMessage();
            r.ms = System.currentTimeMillis() - started;
            return r;
        }

        ByteArrayOutputStream outBuf = new ByteArrayOutputStream();
        ByteArrayOutputStream errBuf = new ByteArrayOutputStream();
        Thread tOut = pump(p.getInputStream(), outBuf);
        Thread tErr = pump(p.getErrorStream(), errBuf);

        try {
            boolean done = timeoutMs <= 0 ? waitForever(p) : p.waitFor(timeoutMs, TimeUnit.MILLISECONDS);
            if (!done) {
                r.timedOut = true;
                p.destroy();
                if (!p.waitFor(2, TimeUnit.SECONDS)) {
                    p.destroyForcibly();
                }
            }
            tOut.join(1500);
            tErr.join(1500);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            p.destroyForcibly();
            r.err = "被中断";
        }

        r.out = outBuf.toString(StandardCharsets.UTF_8);
        r.err = errBuf.toString(StandardCharsets.UTF_8);
        r.code = r.timedOut ? -1 : p.exitValue();
        r.ms = System.currentTimeMillis() - started;
        if (r.timedOut && r.err.isEmpty()) {
            r.err = "超时（" + timeoutMs / 1000 + " 秒）";
        }
        return r;
    }

    private static boolean waitForever(Process p) throws InterruptedException {
        p.waitFor();
        return true;
    }

    private static Thread pump(InputStream in, ByteArrayOutputStream sink) {
        Thread t = new Thread(new Runnable() {
            @Override
            public void run() {
                byte[] buf = new byte[8192];
                int n;
                try {
                    while ((n = in.read(buf)) > 0) {
                        sink.write(buf, 0, n);
                    }
                } catch (IOException ignored) {
                }
            }
        });
        t.setDaemon(true);
        t.start();
        return t;
    }

    static R sh(String cmd, long timeoutMs) {
        return exec(new String[]{"/system/bin/sh", "-c", cmd}, timeoutMs);
    }

    static R su(String cmd, long timeoutMs) {
        return exec(new String[]{"su", "-c", cmd}, timeoutMs);
    }

    // ---- root 探测（缓存） ---------------------------------------------
    private static Boolean rootCache;
    private static String managerCache;

    static synchronized boolean hasRoot() {
        if (rootCache == null) {
            R r = exec(new String[]{"su", "-c", "id"}, 25000);
            rootCache = r.ok() && r.out.contains("uid=0");
        }
        return rootCache;
    }

    static synchronized void reset() {
        rootCache = null;
        managerCache = null;
    }

    static synchronized String manager() {
        if (managerCache != null) {
            return managerCache;
        }
        if (!hasRoot()) {
            managerCache = "";
            return managerCache;
        }
        String[][] probes = {
                {"magisk", "-v"},
                {"ksud", "-V"},
                {"apd", "-V"},
        };
        for (String[] probe : probes) {
            R r = su(toolPath() + join(probe), 12000);
            if (r.ok() && !r.out.trim().isEmpty()) {
                managerCache = r.out.trim().split("\n")[0];
                return managerCache;
            }
        }
        if (su("ls -d /data/adb/magisk", 8000).ok()) {
            managerCache = "Magisk";
        } else if (su("ls -d /data/adb/ksu", 8000).ok()) {
            managerCache = "KernelSU";
        } else if (su("ls -d /data/adb/ap", 8000).ok()) {
            managerCache = "APatch";
        } else {
            managerCache = "已 root（管理器未识别）";
        }
        return managerCache;
    }

    static String suPath() {
        R r = sh("which su", 8000);
        return r.ok() ? r.out.trim() : "";
    }

    static String join(String[] parts) {
        StringBuilder sb = new StringBuilder();
        for (String p : parts) {
            if (sb.length() > 0) {
                sb.append(' ');
            }
            sb.append(p);
        }
        return sb.toString();
    }

    /** root shell 里不一定有管理器的 PATH，显式补上常见落点。 */
    static String toolPath() {
        return "PATH=/debug_ramdisk:/data/adb/ksu/bin:/data/adb/ap/bin:/sbin:$PATH; ";
    }

    /** 单层引号：给命令里的路径用（su 不经过本地 shell，但设备 sh 会解析一次）。 */
    static String q(String s) {
        return "'" + s.replace("'", "'\\''") + "'";
    }

    static void copy(InputStream in, OutputStream out, byte[] buf) throws IOException {
        int n;
        while ((n = in.read(buf)) > 0) {
            out.write(buf, 0, n);
        }
    }
}
