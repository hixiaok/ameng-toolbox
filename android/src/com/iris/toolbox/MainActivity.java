package com.iris.toolbox;

import android.app.Activity;
import android.content.Intent;
import android.content.res.Configuration;
import android.database.Cursor;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.view.View;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 全部界面在 WebView 里，Java 只做"手"：root 命令、分区 dd、模块、文件、应用。
 *
 * JS 与 Java 的协议：
 *   Android.call(method, argsJson, id)  -> 异步执行
 *   window.__irisDone(id, resultJson)   <- 结果
 *   window.__irisProgress(id, ratio, label) <- 长任务进度
 *   window.__irisPicked(kind, path, name)   <- SAF 选完文件
 *   window.__irisExported(ok, message)      <- SAF 保存完
 */
public class MainActivity extends Activity {

    private static final int REQ_PICK = 1001;
    private static final int REQ_SAVE = 1002;

    private WebView web;
    private final ExecutorService pool = Executors.newFixedThreadPool(2);
    private String pickKind = "img";
    private String exportSrc = "";

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        styleSystemBars();

        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(true);
        s.setAllowFileAccessFromFileURLs(true);
        s.setAllowContentAccess(true);
        s.setSupportZoom(false);
        s.setBuiltInZoomControls(false);
        s.setDisplayZoomControls(false);
        s.setTextZoom(100);
        s.setMediaPlaybackRequiresUserGesture(true);

        web.setBackgroundColor(isNight() ? Color.parseColor("#101215") : Color.parseColor("#f4f5f7"));
        web.setOverScrollMode(View.OVER_SCROLL_NEVER);
        web.setWebChromeClient(new WebChromeClient());
        web.setWebViewClient(new WebViewClient());
        web.addJavascriptInterface(new Bridge(), "Android");
        setContentView(web);
        web.loadUrl("file:///android_asset/index.html");
    }

    @Override
    protected void onDestroy() {
        pool.shutdownNow();
        if (web != null) {
            web.destroy();
        }
        super.onDestroy();
    }

    private boolean isNight() {
        int mode = getResources().getConfiguration().uiMode & Configuration.UI_MODE_NIGHT_MASK;
        return mode == Configuration.UI_MODE_NIGHT_YES;
    }

    private void styleSystemBars() {
        boolean night = isNight();
        int bar = night ? Color.parseColor("#191c21") : Color.parseColor("#ffffff");
        getWindow().setStatusBarColor(bar);
        getWindow().setNavigationBarColor(night ? Color.parseColor("#191c21") : Color.parseColor("#ffffff"));
        if (Build.VERSION.SDK_INT >= 23) {
            int flags = getWindow().getDecorView().getSystemUiVisibility();
            if (night) {
                flags &= ~View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
            } else {
                flags |= View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
            }
            getWindow().getDecorView().setSystemUiVisibility(flags);
        }
    }

    /* ---------------- JS 桥 ---------------- */
    private final class Bridge {
        @JavascriptInterface
        public void call(String method, String argsJson, String id) {
            JSONObject args;
            try {
                args = new JSONObject(argsJson == null || argsJson.isEmpty() ? "{}" : argsJson);
            } catch (Exception e) {
                post(id, error("参数不是合法 JSON"));
                return;
            }
            if ("pick".equals(method)) {
                pickKind = args.optString("kind", "img");
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        startPick();
                    }
                });
                post(id, ok());
                return;
            }
            if ("export".equals(method)) {
                final String src = args.optString("path", "");
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        startExport(src);
                    }
                });
                post(id, ok());
                return;
            }
            pool.submit(new Runnable() {
                @Override
                public void run() {
                    JSONObject res;
                    try {
                        res = dispatch(method, args, id);
                        if (!res.has("ok")) {
                            res.put("ok", true);
                        }
                    } catch (Exception e) {
                        res = error(e.getMessage() == null ? e.toString() : e.getMessage());
                    }
                    post(id, res);
                }
            });
        }
    }

    private JSONObject dispatch(String method, JSONObject args, String id) throws Exception {
        switch (method) {
            case "info":
                return Info.json(this);
            case "refreshRoot":
                Shell.reset();
                return Info.json(this);
            case "shell": {
                String cmd = args.optString("cmd", "");
                boolean root = args.optBoolean("root", false);
                if (cmd.trim().isEmpty()) {
                    throw new Exception("命令为空");
                }
                Shell.R r = root ? Shell.su(cmd, 60000) : Shell.sh(cmd, 60000);
                JSONObject o = new JSONObject();
                o.put("ok", true);           // 调用本身成功；命令失败看 code
                o.put("success", r.ok());
                o.put("code", r.code);
                o.put("out", r.out);
                o.put("err", r.err);
                o.put("ms", r.ms);
                o.put("timedOut", r.timedOut);
                return o;
            }
            case "parts":
                return Partitions.listJson();
            case "backup": {
                File base = getExternalFilesDir(null);
                if (base == null) {
                    base = getFilesDir();
                }
                File dir = new File(base, "backups");
                final AtomicInteger last = new AtomicInteger(-1);
                return Partitions.backup(args.getString("name"), dir, new Partitions.Progress() {
                    @Override
                    public void on(double ratio, String label) {
                        int pct = (int) (ratio * 100);
                        if (pct != last.get()) {
                            last.set(pct);
                            progress(id, ratio, label);
                        }
                    }
                });
            }
            case "restore": {
                File img = new File(args.getString("path"));
                final AtomicInteger last = new AtomicInteger(-1);
                return Partitions.restore(args.getString("name"), img, new Partitions.Progress() {
                    @Override
                    public void on(double ratio, String label) {
                        int pct = (int) (ratio * 100);
                        if (pct != last.get()) {
                            last.set(pct);
                            progress(id, ratio, label);
                        }
                    }
                });
            }
            case "modules":
                return Modules.listJson();
            case "moduleToggle":
                return Modules.toggle(args.getString("name"), args.getBoolean("enabled"));
            case "moduleRemove":
                return Modules.remove(args.getString("name"));
            case "moduleInstall":
                return Modules.install(args.getString("path"));
            case "ls":
                return DevFiles.ls(args.optString("path", "/sdcard"), args.optBoolean("root", false));
            case "read":
                return DevFiles.read(args.getString("path"), args.optBoolean("root", false), 262144);
            case "apps":
                return Apps.list(args.optBoolean("all", false));
            case "appAction":
                return Apps.action(args.getString("pkg"), args.getString("action"));
            default:
                throw new Exception("未知操作：" + method);
        }
    }

    private JSONObject ok() {
        JSONObject o = new JSONObject();
        try {
            o.put("ok", true);
        } catch (Exception ignored) {
        }
        return o;
    }

    private JSONObject error(String msg) {
        JSONObject o = new JSONObject();
        try {
            o.put("ok", false);
            o.put("error", msg);
        } catch (Exception ignored) {
        }
        return o;
    }

    private void post(String id, JSONObject res) {
        final String json = res.toString();
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                web.evaluateJavascript(
                        "window.__irisDone(" + JSONObject.quote(id) + "," + JSONObject.quote(json) + ")", null);
            }
        });
    }

    private void progress(String id, double ratio, String label) {
        final String js = "window.__irisProgress(" + JSONObject.quote(id) + "," + ratio + ","
                + JSONObject.quote(label == null ? "" : label) + ")";
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                web.evaluateJavascript(js, null);
            }
        });
    }

    /* ---------------- SAF ---------------- */
    private void startPick() {
        Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        i.addCategory(Intent.CATEGORY_OPENABLE);
        i.setType("*/*");
        try {
            startActivityForResult(Intent.createChooser(i, "选择文件"), REQ_PICK);
        } catch (Exception e) {
            Toast.makeText(this, "没有文件选择器：" + e.getMessage(), Toast.LENGTH_LONG).show();
            picked(pickKind, "", "");
        }
    }

    private void startExport(String src) {
        File f = new File(src);
        if (!f.isFile()) {
            Toast.makeText(this, "文件不存在：" + src, Toast.LENGTH_LONG).show();
            return;
        }
        exportSrc = src;
        Intent i = new Intent(Intent.ACTION_CREATE_DOCUMENT);
        i.addCategory(Intent.CATEGORY_OPENABLE);
        i.setType("application/octet-stream");
        i.putExtra(Intent.EXTRA_TITLE, f.getName());
        try {
            startActivityForResult(Intent.createChooser(i, "保存到"), REQ_SAVE);
        } catch (Exception e) {
            Toast.makeText(this, "没有保存界面：" + e.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    @Override
    protected void onActivityResult(int req, int result, Intent data) {
        super.onActivityResult(req, result, data);
        if (req == REQ_PICK) {
            if (result != RESULT_OK || data == null || data.getData() == null) {
                picked(pickKind, "", "");
                return;
            }
            final Uri uri = data.getData();
            final String kind = pickKind;
            toast("正在读取所选文件…");
            pool.submit(new Runnable() {
                @Override
                public void run() {
                    try {
                        File copy = copyToCache(uri);
                        picked(kind, copy.getAbsolutePath(), displayName(uri));
                    } catch (Exception e) {
                        toastOnUi("读取文件失败：" + e.getMessage());
                        picked(kind, "", "");
                    }
                }
            });
            return;
        }
        if (req == REQ_SAVE) {
            if (result != RESULT_OK || data == null || data.getData() == null) {
                exported(false, "已取消");
                return;
            }
            final Uri target = data.getData();
            final String src = exportSrc;
            toast("正在保存…");
            pool.submit(new Runnable() {
                @Override
                public void run() {
                    try (InputStream in = new java.io.FileInputStream(src);
                         OutputStream out = getContentResolver().openOutputStream(target)) {
                        if (out == null) {
                            throw new Exception("无法打开目标文件");
                        }
                        byte[] buf = new byte[1 << 20];
                        int n;
                        while ((n = in.read(buf)) > 0) {
                            out.write(buf, 0, n);
                        }
                        out.flush();
                        exported(true, "");
                    } catch (Exception e) {
                        exported(false, e.getMessage());
                    }
                }
            });
        }
    }

    private void toast(final String msg) {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                Toast.makeText(MainActivity.this, msg, Toast.LENGTH_SHORT).show();
            }
        });
    }

    private void toastOnUi(final String msg) {
        toast(msg);
    }

    private void picked(String kind, String path, String name) {
        final String js = "window.__irisPicked(" + JSONObject.quote(kind) + "," + JSONObject.quote(path) + "," + JSONObject.quote(name) + ")";
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                web.evaluateJavascript(js, null);
            }
        });
    }

    private void exported(boolean ok, String msg) {
        final String js = "window.__irisExported(" + ok + "," + JSONObject.quote(msg == null ? "" : msg) + ")";
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                web.evaluateJavascript(js, null);
            }
        });
    }

    private File copyToCache(Uri uri) throws Exception {
        String name = displayName(uri);
        if (name.isEmpty()) {
            name = "picked-" + System.currentTimeMillis();
        }
        name = name.replace('/', '_').replace('\\', '_');
        File dir = new File(getCacheDir(), "picked");
        if (!dir.isDirectory() && !dir.mkdirs()) {
            throw new Exception("无法创建缓存目录");
        }
        File out = new File(dir, String.format(Locale.US, "%d-%s", System.currentTimeMillis(), name));
        try (InputStream in = getContentResolver().openInputStream(uri);
             OutputStream os = new FileOutputStream(out)) {
            if (in == null) {
                throw new Exception("无法打开所选文件");
            }
            byte[] buf = new byte[1 << 20];
            int n;
            while ((n = in.read(buf)) > 0) {
                os.write(buf, 0, n);
            }
            os.flush();
        }
        return out;
    }

    private String displayName(Uri uri) {
        try (Cursor c = getContentResolver().query(uri, null, null, null, null)) {
            if (c != null && c.moveToFirst()) {
                int idx = c.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                if (idx >= 0) {
                    String v = c.getString(idx);
                    if (v != null) {
                        return v;
                    }
                }
            }
        } catch (Exception ignored) {
        }
        String last = uri.getLastPathSegment();
        return last == null ? "" : last;
    }
}
