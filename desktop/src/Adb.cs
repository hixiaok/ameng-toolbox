using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Text;
using System.Threading.Tasks;

namespace Iris
{
    class DeviceInfo
    {
        public string Serial = "";
        public string State = "";
        public string Brand = "";
        public string Model = "";
        public string Codename = "";
        public string Android = "";
        public string Sdk = "";
        public string Cpu = "";
        public string Kernel = "";
        public string BuildId = "";
        public string Incremental = "";
        public string Resolution = "";
        public string Density = "";
        public string StorageType = "—";
        public string BatteryHealth = "—";
        public string BatteryCapacity = "—";
        public string SecurityPatch = "";
        public string Fingerprint = "";
        public string BuildDate = "";
        public string Baseband = "";
        public string Abi = "";
        public string Cores = "";
        public string Unlocked = "";
        public double BatteryTemp = 0;
        public int BatteryMv = 0;
        public int BatteryLevel = 0;
        public long StorageTotal = 0;
        public long StorageUsed = 0;
        public long MemTotal = 0;
        public long MemAvailable = 0;
        public bool Root = false;
        public string Manager = "";

        public double StoragePercent
        {
            get { return StorageTotal > 0 ? Math.Round(StorageUsed * 100.0 / StorageTotal) : 0; }
        }

        public double MemoryPercent
        {
            get
            {
                if (MemTotal <= 0)
                {
                    return 0;
                }
                long used = MemTotal - MemAvailable;
                return Math.Round(used * 100.0 / MemTotal);
            }
        }

        public string StorageText
        {
            get
            {
                if (StorageTotal <= 0)
                {
                    return "—";
                }
                return Human(StorageUsed) + " / " + Human(StorageTotal);
            }
        }

        public string MemoryText
        {
            get
            {
                if (MemTotal <= 0)
                {
                    return "—";
                }
                return Human(MemTotal - MemAvailable) + " / " + Human(MemTotal);
            }
        }

        public static string Human(long n)
        {
            string[] u = { "B", "KiB", "MiB", "GiB", "TiB" };
            double v = n;
            int i = 0;
            while (v >= 1024 && i < u.Length - 1)
            {
                v /= 1024;
                i++;
            }
            return (i == 0 ? v.ToString("0") : v.ToString("0.0")) + u[i];
        }
    }

    class AdbResult
    {
        public int Code;
        public string Out = "";
        public string Err = "";
        public bool Ok { get { return Code == 0; } }
    }

    static class Adb
    {
        public static string Path = FindAdb();

        static readonly List<Process> Active = new List<Process>();

        static void Register(Process p)
        {
            lock (Active) { Active.Add(p); }
        }

        static void Unregister(Process p)
        {
            lock (Active) { Active.Remove(p); }
        }

        /// <summary>杀掉本程序正在跑的 adb / fastboot 客户端进程（不杀 adb server）。</summary>
        public static void CancelActive()
        {
            Process[] arr;
            lock (Active) { arr = Active.ToArray(); }
            foreach (Process p in arr)
            {
                try { if (!p.HasExited) { p.Kill(); } } catch { }
            }
        }

        /// <summary>停掉本程序的客户端进程，并关闭 adb server。</summary>
        public static void Shutdown()
        {
            CancelActive();
            try { Run("kill-server", 5000); } catch { }
        }

        public static string FindAdb()
        {
            string env = Environment.GetEnvironmentVariable("IRIS_ADB");
            if (!string.IsNullOrEmpty(env) && File.Exists(env))
            {
                return env;
            }
            string exeDir = AppDomain.CurrentDomain.BaseDirectory;
            string sibling = System.IO.Path.Combine(exeDir, "adb.exe");
            if (File.Exists(sibling))
            {
                return sibling;
            }
            var dir = new DirectoryInfo(exeDir);
            for (int i = 0; i < 4 && dir != null; i++)
            {
                string cand = System.IO.Path.Combine(dir.FullName, "platform-tools", "adb.exe");
                if (File.Exists(cand))
                {
                    return cand;
                }
                dir = dir.Parent;
            }
            string pathVar = Environment.GetEnvironmentVariable("PATH") ?? "";
            foreach (string part in pathVar.Split(';'))
            {
                try
                {
                    string cand = System.IO.Path.Combine(part.Trim(), "adb.exe");
                    if (File.Exists(cand))
                    {
                        return cand;
                    }
                }
                catch
                {
                }
            }
            return "adb.exe";
        }

        public static bool Available
        {
            get { return Path == "adb.exe" ? FindOnPath("adb.exe") : File.Exists(Path); }
        }

        static bool FindOnPath(string name)
        {
            string pathVar = Environment.GetEnvironmentVariable("PATH") ?? "";
            foreach (string part in pathVar.Split(';'))
            {
                try
                {
                    if (File.Exists(System.IO.Path.Combine(part.Trim(), name)))
                    {
                        return true;
                    }
                }
                catch
                {
                }
            }
            return false;
        }

        public static AdbResult Run(string args, int timeoutMs)
        {
            var r = new AdbResult();
            try
            {
                var psi = new ProcessStartInfo(Path, args)
                {
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    StandardOutputEncoding = Encoding.UTF8,
                    StandardErrorEncoding = Encoding.UTF8,
                };
                using (var p = Process.Start(psi))
                {
                    Register(p);
                    try
                    {
                        var outTask = p.StandardOutput.ReadToEndAsync();
                        var errTask = p.StandardError.ReadToEndAsync();
                        if (!p.WaitForExit(timeoutMs))
                        {
                            try { p.Kill(); } catch { }
                            r.Code = -1;
                            r.Err = "超时";
                            return r;
                        }
                        try
                        {
                            System.Threading.Tasks.Task.WaitAll(new System.Threading.Tasks.Task[] { outTask, errTask }, 2000);
                        }
                        catch
                        {
                        }
                        r.Code = p.ExitCode;
                        r.Out = outTask.IsCompleted ? outTask.Result : "";
                        r.Err = errTask.IsCompleted ? errTask.Result : "";
                    }
                    finally
                    {
                        Unregister(p);
                    }
                }
            }
            catch (Exception ex)
            {
                r.Code = -2;
                r.Err = ex.Message;
            }
            return r;
        }

        public static AdbResult Shell(string serial, string command, int timeoutMs)
        {
            return Run(QuoteSerial(serial) + " shell " + command, timeoutMs);
        }

        public static AdbResult Su(string serial, string command, int timeoutMs)
        {
            return Run(QuoteSerial(serial) + " shell su -c \"" + command.Replace("\"", "\\\"") + "\"", timeoutMs);
        }

        static string QuoteSerial(string serial)
        {
            return string.IsNullOrEmpty(serial) ? "" : "-s " + serial + " ";
        }

        public static List<string[]> Devices()
        {
            var list = new List<string[]>();
            AdbResult r = Run("devices -l", 15000);
            if (!r.Ok)
            {
                return list;
            }
            foreach (string raw in r.Out.Split('\n'))
            {
                string line = raw.Trim();
                if (line.Length == 0 || line.StartsWith("List of devices"))
                {
                    continue;
                }
                string[] parts = line.Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
                if (parts.Length < 2)
                {
                    continue;
                }
                string model = "";
                for (int i = 2; i < parts.Length; i++)
                {
                    if (parts[i].StartsWith("model:"))
                    {
                        model = parts[i].Substring(6);
                    }
                }
                list.Add(new[] { parts[0], parts[1], model });
            }
            return list;
        }

        static readonly Dictionary<string, string> RootCache = new Dictionary<string, string>();

        public static DeviceInfo ReadInfo(string serial)
        {
            var info = new DeviceInfo();
            info.Serial = serial;

            var props = new Dictionary<string, string>();
            AdbResult gp = Shell(serial, "getprop", 20000);
            foreach (string raw in gp.Out.Split('\n'))
            {
                int a = raw.IndexOf('[');
                int b = raw.IndexOf("]: [", StringComparison.Ordinal);
                if (a < 0 || b < 0)
                {
                    continue;
                }
                string k = raw.Substring(a + 1, b - a - 1);
                int end = raw.LastIndexOf(']');
                if (end > b)
                {
                    props[k] = raw.Substring(b + 4, end - b - 4);
                }
            }
            info.Brand = Get(props, "ro.product.brand", "ro.product.vendor.brand");
            info.Model = Get(props, "ro.product.model", "ro.product.vendor.model");
            info.Codename = Get(props, "ro.product.device", "ro.product.vendor.device");
            info.Android = Get(props, "ro.build.version.release");
            info.Sdk = Get(props, "ro.build.version.sdk");
            info.Kernel = Get(props, "ro.kernel.version");
            info.BuildId = Get(props, "ro.build.display.id", "ro.build.id");
            info.Incremental = Get(props, "ro.build.version.incremental");
            info.SecurityPatch = Get(props, "ro.build.version.security_patch");
            info.Fingerprint = Get(props, "ro.build.fingerprint", "ro.system.build.fingerprint");
            info.BuildDate = Get(props, "ro.build.date");
            info.Baseband = Get(props, "gsm.version.baseband", "ro.build.expect.baseband");
            info.Abi = Get(props, "ro.product.cpu.abi", "ro.product.cpu.abilist");
            string locked = Get(props, "ro.boot.flash.locked");
            string vbs = Get(props, "ro.boot.verifiedbootstate");
            info.Unlocked = locked == "0" ? "已解锁" : (locked == "1" ? "已锁定" : (vbs == "orange" ? "已解锁" : (vbs == "green" ? "已锁定" : "未知")));
            string socMaker = Get(props, "ro.soc.manufacturer");
            string socModel = Get(props, "ro.soc.model", "ro.board.platform", "ro.hardware");
            info.Cpu = (socMaker + " " + socModel).Trim();

            AdbResult kernel = Shell(serial, "uname -r", 8000);
            if (kernel.Ok)
            {
                info.Kernel = kernel.Out.Trim();
            }
            AdbResult cores = Shell(serial, "nproc", 8000);
            if (cores.Ok && cores.Out.Trim().Length > 0)
            {
                info.Cores = cores.Out.Trim() + " 核";
            }

            AdbResult size = Shell(serial, "wm size", 8000);
            foreach (string raw in size.Out.Split('\n'))
            {
                if (raw.Contains("Physical size:"))
                {
                    info.Resolution = raw.Substring(raw.IndexOf(':') + 1).Trim();
                }
            }
            AdbResult density = Shell(serial, "wm density", 8000);
            foreach (string raw in density.Out.Split('\n'))
            {
                if (raw.Contains("Physical density:"))
                {
                    info.Density = raw.Substring(raw.IndexOf(':') + 1).Trim();
                }
            }

            AdbResult bat = Shell(serial, "dumpsys battery", 10000);
            foreach (string raw in bat.Out.Split('\n'))
            {
                string line = raw.Trim();
                int c = line.IndexOf(':');
                if (c <= 0)
                {
                    continue;
                }
                string k = line.Substring(0, c).Trim();
                string v = line.Substring(c + 1).Trim();
                if (k == "level")
                {
                    int lvl;
                    if (int.TryParse(v, out lvl))
                    {
                        info.BatteryLevel = lvl;
                    }
                }
                else if (k == "health")
                {
                    info.BatteryHealth = HealthName(v);
                }
                else if (k == "temperature")
                {
                    int t;
                    if (int.TryParse(v, out t)) { info.BatteryTemp = t / 10.0; }
                }
                else if (k == "voltage")
                {
                    int mv;
                    if (int.TryParse(v, out mv)) { info.BatteryMv = mv; }
                }
            }

            // 部分三星/定制系统 dumpsys 的 level 读不到，兜底读 sysfs
            if (info.BatteryLevel <= 0)
            {
                foreach (string node in new[] { "battery", "bms", "max17042" })
                {
                    AdbResult cap = Shell(serial, "cat /sys/class/power_supply/" + node + "/capacity", 5000);
                    int lvl;
                    if (cap.Ok && int.TryParse(cap.Out.Trim(), out lvl) && lvl > 0)
                    {
                        info.BatteryLevel = lvl;
                        break;
                    }
                }
            }
            if (info.BatteryCapacity == "—" || info.BatteryCapacity.Length == 0)
            {
                AdbResult full = Shell(serial, "cat /sys/class/power_supply/battery/charge_full", 5000);
                long uah;
                if (full.Ok && long.TryParse(full.Out.Trim(), out uah) && uah > 0)
                {
                    info.BatteryCapacity = (uah / 1000) + " mAh";
                }
            }
            if (info.BatteryTemp <= 0)
            {
                AdbResult temp = Shell(serial, "cat /sys/class/power_supply/battery/temp", 5000);
                int tenths;
                if (temp.Ok && int.TryParse(temp.Out.Trim(), out tenths) && tenths > 0)
                {
                    info.BatteryTemp = tenths / 10.0;
                }
            }

            AdbResult df = Shell(serial, "df -k /data", 10000);
            foreach (string raw in df.Out.Split('\n'))
            {
                string line = raw.Trim();
                string[] parts = line.Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
                if (parts.Length >= 4)
                {
                    long total, used;
                    if (long.TryParse(parts[1], out total) && long.TryParse(parts[2], out used) && total > 1024)
                    {
                        info.StorageTotal = total * 1024;
                        info.StorageUsed = used * 1024;
                    }
                }
            }

            AdbResult mem = Shell(serial, "cat /proc/meminfo", 10000);
            long memFree = 0;
            foreach (string raw in mem.Out.Split('\n'))
            {
                string line = raw.Trim();
                string[] parts = line.Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
                if (parts.Length < 2)
                {
                    continue;
                }
                long kb;
                if (!long.TryParse(parts[1], out kb))
                {
                    continue;
                }
                if (parts[0] == "MemTotal:")
                {
                    info.MemTotal = kb * 1024;
                }
                else if (parts[0] == "MemAvailable:")
                {
                    info.MemAvailable = kb * 1024;
                }
                else if (parts[0] == "MemFree:")
                {
                    memFree = kb * 1024;
                }
            }
            if (info.MemAvailable <= 0)
            {
                info.MemAvailable = memFree;
            }

            string cachedManager;
            if (RootCache.TryGetValue(serial, out cachedManager))
            {
                info.Root = cachedManager.Length > 0;
                info.Manager = cachedManager;
            }
            else
            {
                AdbResult id = Su(serial, "id", 9000);
                info.Root = id.Ok && id.Out.Contains("uid=0");
                if (info.Root)
                {
                    AdbResult magisk = Su(serial, "magisk -v", 8000);
                    if (magisk.Ok && magisk.Out.Trim().Length > 0)
                    {
                        info.Manager = magisk.Out.Trim().Split('\n')[0];
                    }
                    else
                    {
                        AdbResult ksud = Su(serial, "ksud -V", 8000);
                        if (ksud.Ok && ksud.Out.Trim().Length > 0)
                        {
                            info.Manager = "KernelSU " + ksud.Out.Trim().Split('\n')[0];
                        }
                        else
                        {
                            info.Manager = "已 root";
                        }
                    }
                }
                RootCache[serial] = info.Root ? info.Manager : "";
            }
            return info;
        }

        static string Get(Dictionary<string, string> props, params string[] keys)
        {
            foreach (string k in keys)
            {
                string v;
                if (props.TryGetValue(k, out v) && !string.IsNullOrEmpty(v))
                {
                    return v;
                }
            }
            return "";
        }

        static string HealthName(string raw)
        {
            switch (raw)
            {
                case "2": return "良好";
                case "3": return "过热";
                case "4": return "损坏";
                case "5": return "过压";
                case "6": return "故障";
                case "7": return "过冷";
                default: return "未知";
            }
        }

        public static void Reboot(string serial, string target)
        {
            if (target == "shutdown")
            {
                Shell(serial, "reboot -p", 10000);
                return;
            }
            Run(QuoteSerial(serial) + " reboot " + target, 15000);
        }

        public static bool Screenshot(string serial, string outFile)
        {
            try
            {
                var psi = new ProcessStartInfo(Path, QuoteSerial(serial) + " exec-out screencap -p")
                {
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                };
                using (var p = Process.Start(psi))
                {
                    using (var fs = File.Create(outFile))
                    {
                        p.StandardOutput.BaseStream.CopyTo(fs);
                    }
                    p.WaitForExit(20000);
                    return new FileInfo(outFile).Length > 1000;
                }
            }
            catch
            {
                return false;
            }
        }

        public static AdbResult Logcat(string serial)
        {
            return Shell(serial, "logcat -d -t 300", 20000);
        }

        public static bool Tcpip(string serial, int port)
        {
            AdbResult r = Run(QuoteSerial(serial) + " tcpip " + port, 15000);
            return r.Ok;
        }

        public static List<string[]> Files(string serial, string pathValue, bool root)
        {
            var list = new List<string[]>();
            string cmd = "ls -la " + Quote(pathValue);
            AdbResult r = root ? Su(serial, cmd, 20000) : Shell(serial, cmd, 20000);
            if (!r.Ok && r.Out.Trim().Length == 0)
            {
                return list;
            }
            foreach (string raw in r.Out.Split('\n'))
            {
                string line = raw.TrimEnd();
                if (line.StartsWith("total ") || line.Length < 10)
                {
                    continue;
                }
                string[] parts = line.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
                if (parts.Length < 8)
                {
                    continue;
                }
                int idx = line.IndexOf(parts[7]);
                string name = idx >= 0 ? line.Substring(idx) : parts[7];
                if (name == "." || name == "..")
                {
                    continue;
                }
                list.Add(new[] { parts[0], parts[4], name, parts[0].StartsWith("d") ? "1" : "0" });
            }
            return list;
        }

        public static string Quote(string s)
        {
            return "\"" + s.Replace("\"", "\\\"") + "\"";
        }

        public static List<string[]> Modules(string serial)
        {
            var list = new List<string[]>();
            string script = "for d in /data/adb/modules/*; do [ -d \"$d\" ] || continue; n=$(basename \"$d\"); "
                + "v=$(grep '^version=' \"$d/module.prop\" 2>/dev/null | head -n1 | cut -d= -f2-); "
                + "nm=$(grep '^name=' \"$d/module.prop\" 2>/dev/null | head -n1 | cut -d= -f2-); "
                + "f=0; [ -e \"$d/disable\" ] && f=1; echo \"$n|$nm|$v|$f\"; done";
            AdbResult r = Su(serial, script, 30000);
            foreach (string raw in r.Out.Split('\n'))
            {
                string line = raw.Trim();
                if (line.Length == 0 || line.IndexOf('|') < 0)
                {
                    continue;
                }
                string[] p = line.Split('|');
                if (p.Length >= 4)
                {
                    list.Add(p);
                }
            }
            return list;
        }

        public static void ModuleToggle(string serial, string name, bool enabled)
        {
            string flag = "/data/adb/modules/" + name + "/disable";
            Su(serial, (enabled ? "rm -f " : "touch ") + Quote(flag), 12000);
        }

        public static string LastPackagesRaw = "";

        public static List<string> Packages(string serial, bool all)
        {
            string raw;
            string command = all ? "pm list packages" : "pm list packages -3";
            List<string> list = QueryPackages(serial, command, out raw);
            if (list.Count == 0)
            {
                string rawCmd;
                List<string> viaCmd = QueryPackages(serial, "cmd package list packages" + (all ? "" : " -3"), out rawCmd);
                if (viaCmd.Count > 0)
                {
                    LastPackagesRaw = rawCmd;
                    return viaCmd;
                }
                raw = raw + "\n" + rawCmd;
            }
            if (list.Count == 0 && !all)
            {
                string rawAll;
                List<string> allList = QueryPackages(serial, "pm list packages", out rawAll);
                if (allList.Count == 0)
                {
                    string rawAll2;
                    allList = QueryPackages(serial, "cmd package list packages", out rawAll2);
                    rawAll = rawAll + "\n" + rawAll2;
                }
                if (allList.Count > 0)
                {
                    LastPackagesRaw = "第三方查询为空，已回退到全部应用\n" + raw + "\n" + rawAll;
                    return allList;
                }
            }
            LastPackagesRaw = raw;
            return list;
        }

        static List<string> QueryPackages(string serial, string command, out string raw)
        {
            var list = new List<string>();
            AdbResult r = Shell(serial, command, 30000);
            raw = (r.Out + (r.Err.Length > 0 ? "\n" + r.Err : "")).Trim();
            foreach (string line0 in raw.Split('\n'))
            {
                string line = line0.Trim();
                if (line.StartsWith("package:"))
                {
                    string pkg = line.Substring(8).Trim();
                    if (pkg.Length > 0)
                    {
                        list.Add(pkg);
                    }
                }
                else if (line.IndexOf('.') > 0 && line.IndexOf(' ') < 0)
                {
                    list.Add(line);
                }
            }
            list.Sort(StringComparer.OrdinalIgnoreCase);
            return list;
        }

        public static void AppAction(string serial, string pkg, string action)
        {
            string cmd;
            switch (action)
            {
                case "freeze": cmd = "pm disable-user --user 0 " + pkg; break;
                case "unfreeze": cmd = "pm enable " + pkg; break;
                case "uninstall": cmd = "pm uninstall --user 0 " + pkg; break;
                default: cmd = "pm clear " + pkg; break;
            }
            Su(serial, cmd, 30000);
        }

        public static List<string[]> Partitions(string serial)
        {
            var list = new List<string[]>();
            string script = "for f in /dev/block/by-name/* /dev/block/bootdevice/by-name/*; do "
                + "[ -e \"$f\" ] || continue; n=$(basename \"$f\"); s=$(blockdev --getsize64 \"$f\" 2>/dev/null); "
                + "[ -n \"$s\" ] && echo \"$n|$s\"; done";
            AdbResult r = Su(serial, script, 30000);
            foreach (string raw in r.Out.Split('\n'))
            {
                string line = raw.Trim();
                int bar = line.IndexOf('|');
                if (bar <= 0)
                {
                    continue;
                }
                list.Add(new[] { line.Substring(0, bar), line.Substring(bar + 1) });
            }
            return list;
        }

        public static bool Backup(string serial, string part, string outFile, Action<double> progress)
        {
            try
            {
                var psi = new ProcessStartInfo(Path,
                    QuoteSerial(serial) + " exec-out su -c \"dd if=/dev/block/by-name/" + part + " bs=4M 2>/dev/null\"")
                {
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                };
                using (var p = Process.Start(psi))
                {
                    using (var fs = File.Create(outFile))
                    {
                        var buf = new byte[1 << 20];
                        long done = 0;
                        int n;
                        while ((n = p.StandardOutput.BaseStream.Read(buf, 0, buf.Length)) > 0)
                        {
                            fs.Write(buf, 0, n);
                            done += n;
                            if (progress != null)
                            {
                                progress(done);
                            }
                        }
                    }
                    p.WaitForExit(600000);
                }
                return new FileInfo(outFile).Length > 0;
            }
            catch
            {
                return false;
            }
        }

        public static bool Restore(string serial, string part, string image)
        {
            string remote = "/data/local/tmp/iris-restore.img";
            AdbResult push = Run(QuoteSerial(serial) + " push \"" + image + "\" " + remote, 120000);
            if (!push.Ok)
            {
                return false;
            }
            AdbResult dd = Su(serial, "dd if=" + remote + " of=/dev/block/by-name/" + part + " bs=4M && sync", 600000);
            Shell(serial, "rm -f " + remote, 10000);
            return dd.Ok;
        }

        /* ---------- fastboot ---------- */
        public static string FastbootPath = FindFastbootExe();

        static string FindFastbootExe()
        {
            string exeDir = AppDomain.CurrentDomain.BaseDirectory;
            string[] rels = { "fastboot.exe", "tools\\fastboot.exe", "platform-tools\\fastboot.exe" };
            var dir = new DirectoryInfo(exeDir);
            for (int i = 0; i < 4 && dir != null; i++)
            {
                foreach (string rel in rels)
                {
                    string cand = System.IO.Path.Combine(dir.FullName, rel);
                    if (File.Exists(cand))
                    {
                        return cand;
                    }
                }
                dir = dir.Parent;
            }
            string pathVar = Environment.GetEnvironmentVariable("PATH") ?? "";
            foreach (string part in pathVar.Split(';'))
            {
                try
                {
                    string cand = System.IO.Path.Combine(part.Trim(), "fastboot.exe");
                    if (File.Exists(cand))
                    {
                        return cand;
                    }
                }
                catch
                {
                }
            }
            return "fastboot.exe";
        }

        public static AdbResult Fastboot(string args, int timeoutMs)
        {
            var r = new AdbResult();
            try
            {
                var psi = new ProcessStartInfo(FastbootPath, args)
                {
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    StandardOutputEncoding = Encoding.UTF8,
                    StandardErrorEncoding = Encoding.UTF8,
                };
                using (var p = Process.Start(psi))
                {
                    Register(p);
                    try
                    {
                        var outTask = p.StandardOutput.ReadToEndAsync();
                        var errTask = p.StandardError.ReadToEndAsync();
                        if (!p.WaitForExit(timeoutMs))
                        {
                            try { p.Kill(); } catch { }
                            r.Code = -1;
                            r.Err = "超时";
                            return r;
                        }
                        try
                        {
                            System.Threading.Tasks.Task.WaitAll(new System.Threading.Tasks.Task[] { outTask, errTask }, 2000);
                        }
                        catch
                        {
                        }
                        r.Code = p.ExitCode;
                        r.Out = outTask.IsCompleted ? outTask.Result : "";
                        r.Err = errTask.IsCompleted ? errTask.Result : "";
                    }
                    finally
                    {
                        Unregister(p);
                    }
                }
            }
            catch (Exception ex)
            {
                r.Code = -2;
                r.Err = ex.Message;
            }
            return r;
        }

        public static List<string> FastbootDevices()
        {
            var list = new List<string>();
            AdbResult r = Fastboot("devices", 15000);
            foreach (string raw in r.Out.Split('\n'))
            {
                string line = raw.Trim();
                if (line.Length == 0 || line.StartsWith("List of devices"))
                {
                    continue;
                }
                string[] parts = line.Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
                if (parts.Length >= 2)
                {
                    list.Add(parts[0]);
                }
            }
            return list;
        }

        /* ---------- 文件 / 应用 ---------- */
        public static bool FileOp(string serial, string command, bool root)
        {
            AdbResult r = root ? Su(serial, command, 30000) : Shell(serial, command, 30000);
            return r.Ok;
        }

        public static bool PushFile(string serial, string local, string remote)
        {
            AdbResult r = Run(QuoteSerial(serial) + " push \"" + local + "\" \"" + remote + "\"", 120000);
            return r.Ok;
        }

        public static bool InstallApk(string serial, string apk)
        {
            AdbResult r = Run(QuoteSerial(serial) + " install -r \"" + apk + "\"", 180000);
            return r.Ok && (r.Out + r.Err).Contains("Success");
        }

        public static bool StartApp(string serial, string pkg)
        {
            AdbResult r = Shell(serial, "monkey -p " + pkg + " -c android.intent.category.LAUNCHER 1", 15000);
            return r.Ok;
        }

        public static bool ExtractApk(string serial, string pkg, string dir)
        {
            AdbResult path = Shell(serial, "pm path " + pkg, 15000);
            string remote = "";
            foreach (string raw in path.Out.Split('\n'))
            {
                if (raw.StartsWith("package:"))
                {
                    remote = raw.Substring(8).Trim();
                    break;
                }
            }
            if (remote.Length == 0)
            {
                return false;
            }
            Directory.CreateDirectory(dir);
            AdbResult pull = Run(QuoteSerial(serial) + " pull \"" + remote + "\" \"" + System.IO.Path.Combine(dir, pkg + ".apk") + "\"", 60000);
            return pull.Ok;
        }

        public static string Sha256(string path)
        {
            try
            {
                using (var sha = System.Security.Cryptography.SHA256.Create())
                using (var fs = File.OpenRead(path))
                {
                    byte[] hash = sha.ComputeHash(fs);
                    var sb = new StringBuilder();
                    foreach (byte b in hash)
                    {
                        sb.Append(b.ToString("x2"));
                    }
                    return sb.ToString();
                }
            }
            catch
            {
                return "";
            }
        }
    }
}
