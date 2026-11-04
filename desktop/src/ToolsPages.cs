using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;

namespace Iris
{
    static class Dev
    {
        public static string Serial()
        {
            foreach (string[] d in Adb.Devices())
            {
                if (d[1] == "device")
                {
                    return d[0];
                }
            }
            return "";
        }
    }

    /* ======================= 快捷指令 ======================= */
    class QuickPage : PageBase
    {
        readonly MainWindow _win;
        readonly StackPanel _log = new StackPanel();
        string _serial = "";

        public QuickPage(MainWindow win)
        {
            _win = win;
            Title = "快捷指令";
            Background = Brushes.Transparent;

            var scroll = Ui.PageScroll();
            Children.Add(scroll);
            var stack = new StackPanel();
            scroll.Content = stack;
            stack.Children.Add(Ui.Header("快捷指令", "常用的 adb 一键操作，危险操作会二次确认。"));

            var card = Ui.Card("#F1F7FE");
            card.Padding = new Thickness(20);
            var body = new StackPanel();
            body.Children.Add(T.Text("设备操作", 15, T.Ink, FontWeights.SemiBold));
            var wrap = new WrapPanel { Margin = new Thickness(0, 12, 0, 0) };
            AddCmd(wrap, "重启系统", delegate { Reboot("system"); });
            AddCmd(wrap, "重启 Recovery", delegate { Reboot("recovery"); });
            AddCmd(wrap, "重启 Bootloader", delegate { Reboot("bootloader"); });
            AddCmd(wrap, "重启 Fastbootd", delegate { Reboot("fastboot"); });
            AddCmd(wrap, "关机", delegate { Reboot("shutdown"); });
            body.Children.Add(wrap);

            body.Children.Add(T.Text("显示与系统", 15, T.Ink, FontWeights.SemiBold));
            var wrap2 = new WrapPanel { Margin = new Thickness(0, 12, 0, 0) };
            AddCmd(wrap2, "屏幕常亮", delegate { Shell("svc power stayon true"); });
            AddCmd(wrap2, "取消常亮", delegate { Shell("svc power stayon false"); });
            AddCmd(wrap2, "关闭动画", delegate { Settings("window_animation_scale", "0"); Settings("transition_animation_scale", "0"); Settings("animator_duration_scale", "0"); });
            AddCmd(wrap2, "恢复动画", delegate { Settings("window_animation_scale", "1"); Settings("transition_animation_scale", "1"); Settings("animator_duration_scale", "1"); });
            AddCmd(wrap2, "显示触摸", delegate { Shell("settings put system show_touches 1"); });
            AddCmd(wrap2, "隐藏触摸", delegate { Shell("settings put system show_touches 0"); });
            AddCmd(wrap2, "打开系统设置", delegate { Shell("am start -a android.settings.SETTINGS"); });
            AddCmd(wrap2, "清理缓存", delegate { Shell("pm trim-caches 999G"); });
            body.Children.Add(wrap2);

            body.Children.Add(T.Text("工具", 15, T.Ink, FontWeights.SemiBold));
            var wrap3 = new WrapPanel { Margin = new Thickness(0, 12, 0, 0) };
            AddCmd(wrap3, "重启 ADB", delegate { RestartAdb(); });
            AddCmd(wrap3, "打开设备管理器", delegate { OpenDeviceManager(); });
            AddCmd(wrap3, "无线调试", delegate { Wireless(); });
            AddCmd(wrap3, "抓日志", delegate { Logcat(); });
            AddCmd(wrap3, "停止 ADB", delegate
            {
                Task.Run(delegate
                {
                    Adb.Shutdown();
                    Dispatcher.Invoke(new Action(delegate { Log("已停止 ADB 服务", false); }));
                });
            });
            body.Children.Add(wrap3);

            card.Child = body;
            stack.Children.Add(card);

            var logCard = Ui.Card("#F7F5FD");
            logCard.Padding = new Thickness(20);
            var lb = new StackPanel();
            lb.Children.Add(T.Text("执行结果", 15, T.Ink, FontWeights.SemiBold));
            var ls = new ScrollViewer { Height = 220, VerticalScrollBarVisibility = ScrollBarVisibility.Auto, Margin = new Thickness(0, 10, 0, 0) };
            ls.Content = _log;
            lb.Children.Add(ls);
            logCard.Child = lb;
            stack.Children.Add(logCard);
        }

        Border AddCmd(WrapPanel wrap, string text, RoutedEventHandler click)
        {
            var b = T.Button(text, false, click);
            b.Height = 34;
            b.Padding = new Thickness(12, 0, 12, 0);
            b.Margin = new Thickness(0, 0, 8, 8);
            wrap.Children.Add(b);
            return b;
        }

        void Log(string text, bool bad)
        {
            var t = T.Text("• " + text, 12, bad ? T.Danger : T.Ink2);
            t.Margin = new Thickness(0, 3, 0, 3);
            t.TextWrapping = TextWrapping.Wrap;
            _log.Children.Add(t);
        }

        void Reboot(string target)
        {
            string serial = _serial = string.IsNullOrEmpty(_serial) ? Dev.Serial() : _serial;
            if (serial.Length == 0) { _win.ShowToast("没有已连接的设备"); return; }
            if (target == "shutdown" && MessageBox.Show("确认关机？", "快捷指令", MessageBoxButton.OKCancel, MessageBoxImage.Question) != MessageBoxResult.OK) { return; }
            Task.Run(delegate
            {
                Adb.Reboot(serial, target);
                Dispatcher.Invoke(new Action(delegate { Log("已发送重启指令：" + target, false); }));
            });
        }

        void Shell(string cmd)
        {
            _serial = string.IsNullOrEmpty(_serial) ? Dev.Serial() : _serial;
            if (_serial.Length == 0) { _win.ShowToast("没有已连接的设备"); return; }
            string serial = _serial;
            Task.Run(delegate
            {
                AdbResult r = Adb.Shell(serial, cmd, 20000);
                Dispatcher.Invoke(new Action(delegate { Log((r.Ok ? "成功" : "失败") + "：" + cmd, !r.Ok); }));
            });
        }

        void Settings(string key, string value)
        {
            Shell("settings put global " + key + " " + value);
        }

        void RestartAdb()
        {
            Task.Run(delegate
            {
                Adb.Run("kill-server", 10000);
                AdbResult r = Adb.Run("start-server", 15000);
                Dispatcher.Invoke(new Action(delegate { Log(r.Ok ? "ADB 已重启" : "ADB 重启失败", !r.Ok); }));
            });
        }

        void OpenDeviceManager()
        {
            try { Process.Start(new ProcessStartInfo("devmgmt.msc") { UseShellExecute = true }); }
            catch (Exception ex) { _win.ShowToast("打不开设备管理器：" + ex.Message); }
        }

        void Wireless()
        {
            _serial = string.IsNullOrEmpty(_serial) ? Dev.Serial() : _serial;
            if (_serial.Length == 0) { _win.ShowToast("没有已连接的设备"); return; }
            string serial = _serial;
            Task.Run(delegate
            {
                bool ok = Adb.Tcpip(serial, 5555);
                Dispatcher.Invoke(new Action(delegate { Log(ok ? "已开启无线调试端口 5555" : "无线调试失败", !ok); }));
            });
        }

        void Logcat()
        {
            _serial = string.IsNullOrEmpty(_serial) ? Dev.Serial() : _serial;
            if (_serial.Length == 0) { _win.ShowToast("没有已连接的设备"); return; }
            string serial = _serial;
            Task.Run(delegate
            {
                AdbResult r = Adb.Logcat(serial);
                string dir = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "shots");
                Directory.CreateDirectory(dir);
                string file = Path.Combine(dir, "logcat-" + DateTime.Now.ToString("yyyyMMdd-HHmmss") + ".txt");
                File.WriteAllText(file, r.Out);
                Dispatcher.Invoke(new Action(delegate { Log("日志已保存：" + Path.GetFileName(file), false); }));
            });
        }
    }

    /* ======================= Fastboot ======================= */
    class FastbootPage : PageBase
    {
        readonly MainWindow _win;
        readonly TextBlock _status;
        readonly TextBlock _result;
        readonly Border _partInput;
        readonly Border _imageInput;
        string _serial = "";

        public FastbootPage(MainWindow win)
        {
            _win = win;
            Title = "Fastboot";
            Background = Brushes.Transparent;

            var scroll = Ui.PageScroll();
            Children.Add(scroll);
            var stack = new StackPanel();
            scroll.Content = stack;
            stack.Children.Add(Ui.Header("Fastboot 刷写", "手机需进入 bootloader / fastbootd。写错分区会变砖，请核对。"));

            var card = Ui.Card("#F3F8FE");
            card.Padding = new Thickness(20);
            var body = new StackPanel();
            var head = new Grid();
            head.ColumnDefinitions.Add(new ColumnDefinition());
            head.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            head.Children.Add(T.Text("设备", 15, T.Ink, FontWeights.SemiBold));
            var scan = Ui.SmallButton("刷新设备", delegate { Scan(); });
            Grid.SetColumn(scan, 1);
            head.Children.Add(scan);
            body.Children.Add(head);

            _status = T.Text("未检测", 12.5, T.Muted);
            _status.Margin = new Thickness(0, 8, 0, 14);
            body.Children.Add(_status);

            body.Children.Add(T.Text("分区名", 12, T.Muted));
            _partInput = Ui.Input("例如 boot / init_boot / vbmeta", 36);
            _partInput.Margin = new Thickness(0, 4, 0, 10);
            body.Children.Add(_partInput);

            body.Children.Add(T.Text("镜像文件", 12, T.Muted));
            var row = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 4, 0, 0) };
            _imageInput = Ui.Input("本地镜像路径", 36);
            _imageInput.Width = 520;
            row.Children.Add(_imageInput);
            var pick = T.Button("选择文件", false, delegate { Pick(); });
            pick.Margin = new Thickness(8, 0, 0, 0);
            row.Children.Add(pick);
            body.Children.Add(row);

            var actions = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 16, 0, 0) };
            var check = T.Button("预检", false, delegate { Precheck(); });
            actions.Children.Add(check);
            var flash = T.Button("刷入分区", true, delegate { DoFlash(); });
            flash.Margin = new Thickness(8, 0, 0, 0);
            actions.Children.Add(flash);
            var reboot = T.Button("重启系统", false, delegate { Fb("reboot"); });
            reboot.Margin = new Thickness(8, 0, 0, 0);
            actions.Children.Add(reboot);
            body.Children.Add(actions);

            _result = T.Text("", 12, T.Muted);
            _result.Margin = new Thickness(0, 12, 0, 0);
            _result.TextWrapping = TextWrapping.Wrap;
            body.Children.Add(_result);

            card.Child = body;
            stack.Children.Add(card);

            var tips = Ui.Card("#FDF3F9");
            tips.Padding = new Thickness(20);
            var tp = new StackPanel();
            tp.Children.Add(T.Text("常用命令", 15, T.Ink, FontWeights.SemiBold));
            var wrap = new WrapPanel { Margin = new Thickness(0, 10, 0, 0) };
            AddCmd(wrap, "重启到系统", delegate { Fb("reboot"); });
            AddCmd(wrap, "重启到 bootloader", delegate { Fb("reboot bootloader"); });
            AddCmd(wrap, "重启到 fastbootd", delegate { Fb("reboot fastboot"); });
            AddCmd(wrap, "查看设备", delegate { Scan(); });
            tp.Children.Add(wrap);
            tips.Child = tp;
            stack.Children.Add(tips);
        }

        void AddCmd(WrapPanel wrap, string text, RoutedEventHandler click)
        {
            var b = T.Button(text, false, click);
            b.Height = 32;
            b.Padding = new Thickness(12, 0, 12, 0);
            b.Margin = new Thickness(0, 0, 8, 8);
            wrap.Children.Add(b);
        }

        public override void OnShown()
        {
            Scan();
        }

        void Scan()
        {
            _status.Text = "检测中…";
            Task.Run(delegate
            {
                List<string> devs = Adb.FastbootDevices();
                Dispatcher.Invoke(new Action(delegate
                {
                    _serial = devs.Count > 0 ? devs[0] : "";
                    _status.Text = devs.Count > 0 ? "已连接：" + string.Join(", ", devs.ToArray()) : "没有处于 fastboot 模式的设备";
                }));
            });
        }

        void Pick()
        {
            var dlg = new Microsoft.Win32.OpenFileDialog { Filter = "镜像 (*.img;*.bin)|*.img;*.bin|所有文件|*.*" };
            if (dlg.ShowDialog() == true)
            {
                Ui.BoxOf(_imageInput).Text = dlg.FileName;
            }
        }

        void Precheck()
        {
            string part = Ui.BoxOf(_partInput).Text.Trim();
            string image = Ui.BoxOf(_imageInput).Text.Trim();
            if (part.Length == 0 || image.Length == 0)
            {
                _win.ShowToast("先填分区名和镜像路径");
                return;
            }
            if (!File.Exists(image))
            {
                _win.ShowToast("镜像不存在");
                return;
            }
            string h = Adb.Sha256(image);
            _result.Text = string.Format("文件：{0}\n大小：{1:0.0} MiB\nSHA-256：{2}\n设备：{3}",
                Path.GetFileName(image), new FileInfo(image).Length / 1048576.0, h,
                _serial.Length > 0 ? _serial : "未检测到 fastboot 设备");
        }

        void DoFlash()
        {
            string part = Ui.BoxOf(_partInput).Text.Trim();
            string image = Ui.BoxOf(_imageInput).Text.Trim();
            if (part.Length == 0 || image.Length == 0 || !File.Exists(image))
            {
                _win.ShowToast("分区名或镜像无效");
                return;
            }
            if (MessageBox.Show("把\n" + image + "\n刷进 " + part + "？\n刷错分区会导致设备变砖。", "Fastboot",
                MessageBoxButton.OKCancel, MessageBoxImage.Warning) != MessageBoxResult.OK)
            {
                return;
            }
            _result.Text = "刷入中…";
            Task.Run(delegate
            {
                AdbResult r = Adb.Fastboot("-s " + _serial + " flash " + part + " \"" + image + "\"", 600000);
                Dispatcher.Invoke(new Action(delegate
                {
                    _result.Text = (r.Out + "\n" + r.Err).Trim();
                    _win.ShowToast(r.Ok ? "刷入完成" : "刷入失败，见输出", !r.Ok);
                }));
            });
        }

        void Fb(string args)
        {
            Task.Run(delegate
            {
                AdbResult r = Adb.Fastboot((_serial.Length > 0 ? "-s " + _serial + " " : "") + args, 30000);
                Dispatcher.Invoke(new Action(delegate
                {
                    _result.Text = (r.Out + "\n" + r.Err).Trim();
                }));
            });
        }
    }

    /* ======================= ROOT ======================= */
    class RootPage : PageBase
    {
        readonly MainWindow _win;
        readonly TextBlock _status;
        readonly TextBlock _manager;
        string _serial = "";

        public RootPage(MainWindow win)
        {
            _win = win;
            Title = "ROOT";
            Background = Brushes.Transparent;

            var scroll = Ui.PageScroll();
            Children.Add(scroll);
            var stack = new StackPanel();
            scroll.Content = stack;
            stack.Children.Add(Ui.Header("ROOT", "查看 root 状态，备份 boot / init_boot，配合手机端 Magisk 完成修补。"));

            var card = Ui.Card("#F7F5FD");
            card.Padding = new Thickness(20);
            var body = new StackPanel();
            body.Children.Add(T.Text("当前状态", 15, T.Ink, FontWeights.SemiBold));
            _status = T.Text("检测中…", 13, T.Muted);
            _status.Margin = new Thickness(0, 8, 0, 2);
            body.Children.Add(_status);
            _manager = T.Text("", 12.5, T.Muted);
            body.Children.Add(_manager);

            var wrap = new WrapPanel { Margin = new Thickness(0, 14, 0, 0) };
            AddBtn(wrap, "备份 boot", delegate { Backup("boot"); });
            AddBtn(wrap, "备份 init_boot", delegate { Backup("init_boot"); });
            AddBtn(wrap, "备份 vbmeta", delegate { Backup("vbmeta"); });
            AddBtn(wrap, "打开 Magisk", delegate { OpenApp("com.topjohnwu.magisk"); });
            AddBtn(wrap, "打开 KernelSU", delegate { OpenApp("me.weishu.kernelsu"); });
            AddBtn(wrap, "重启到 Bootloader", delegate { Reboot("bootloader"); });
            body.Children.Add(wrap);
            card.Child = body;
            stack.Children.Add(card);

            var help = Ui.Card("#F3F8FE");
            help.Padding = new Thickness(20);
            var hp = new StackPanel();
            hp.Children.Add(T.Text("修补流程", 15, T.Ink, FontWeights.SemiBold));
            var txt = T.Text("1. 点「备份 boot / init_boot」把原镜像取到电脑的 backups\\ 目录；\n"
                + "2. 把镜像传到手机，在 Magisk 里「安装 → 选择并修补文件」；\n"
                + "3. 把修补后的镜像拉回电脑，用「Fastboot」页刷回对应分区；\n"
                + "4. 重启后打开 Magisk 确认版本。\n\n"
                + "没有 root 时无法 dd 读取分区，本页不会伪装成「一键 root」。", 12.5, T.Muted);
            txt.TextWrapping = TextWrapping.Wrap;
            txt.Margin = new Thickness(0, 8, 0, 0);
            hp.Children.Add(txt);
            help.Child = hp;
            stack.Children.Add(help);
        }

        void AddBtn(WrapPanel wrap, string text, RoutedEventHandler click)
        {
            var b = T.Button(text, false, click);
            b.Height = 32;
            b.Padding = new Thickness(12, 0, 12, 0);
            b.Margin = new Thickness(0, 0, 8, 8);
            wrap.Children.Add(b);
        }

        public override void OnShown()
        {
            _serial = Dev.Serial();
            if (_serial.Length == 0)
            {
                _status.Text = "未连接设备";
                _manager.Text = "";
                return;
            }
            string serial = _serial;
            _status.Text = "检测中…";
            Task.Run(delegate
            {
                DeviceInfo info = Adb.ReadInfo(serial);
                Dispatcher.Invoke(new Action(delegate
                {
                    _status.Text = info.Root ? "已 root" : "未 root";
                    _status.Foreground = new SolidColorBrush(info.Root ? T.Ok : T.Danger);
                    _manager.Text = info.Root ? "管理器：" + info.Manager : "没有 root，分区备份与 Magisk 修补不可用";
                }));
            });
        }

        void Backup(string part)
        {
            if (_serial.Length == 0) { _win.ShowToast("没有已连接的设备"); return; }
            string dir = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "backups");
            Directory.CreateDirectory(dir);
            string file = Path.Combine(dir, part + "-" + DateTime.Now.ToString("yyyyMMdd-HHmmss") + ".img");
            string serial = _serial;
            _win.ShowToast("正在备份 " + part + "…");
            Task.Run(delegate
            {
                bool ok = Adb.Backup(serial, part, file, null);
                Dispatcher.Invoke(new Action(delegate
                {
                    _win.ShowToast(ok ? "已备份：" + Path.GetFileName(file) : "备份失败（确认已 root 且分区存在）", !ok);
                }));
            });
        }

        void OpenApp(string pkg)
        {
            if (_serial.Length == 0) { _win.ShowToast("没有已连接的设备"); return; }
            string serial = _serial;
            Task.Run(delegate
            {
                bool ok = Adb.StartApp(serial, pkg);
                Dispatcher.Invoke(new Action(delegate { if (!ok) { _win.ShowToast("设备上没找到 " + pkg); } }));
            });
        }

        void Reboot(string target)
        {
            if (_serial.Length == 0) { _win.ShowToast("没有已连接的设备"); return; }
            string serial = _serial;
            Task.Run(delegate
            {
                Adb.Reboot(serial, target);
                Dispatcher.Invoke(new Action(delegate { _win.ShowToast("已发送重启指令"); }));
            });
        }
    }

    /* ======================= 投屏 ======================= */
    class CastPage : PageBase
    {
        readonly MainWindow _win;
        readonly TextBlock _status;
        readonly SelectBox _sizeBox;
        readonly SelectBox _bitrateBox;
        readonly CheckBox _topmost;
        Process _proc;
        string _serial = "";

        public CastPage(MainWindow win)
        {
            _win = win;
            Title = "投屏";
            Background = Brushes.Transparent;

            var scroll = Ui.PageScroll();
            Children.Add(scroll);
            var stack = new StackPanel();
            scroll.Content = stack;
            stack.Children.Add(Ui.Header("投屏", "调用 scrcpy 做 USB 投屏；程序不内置 scrcpy，需要你放一份。"));

            var card = Ui.Card("#F0F9F3");
            card.Padding = new Thickness(20);
            var body = new StackPanel();
            body.Children.Add(T.Text("参数", 15, T.Ink, FontWeights.SemiBold));
            var form = new Grid { Margin = new Thickness(0, 12, 0, 0) };
            form.ColumnDefinitions.Add(new ColumnDefinition());
            form.ColumnDefinitions.Add(new ColumnDefinition());
            form.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

            var sizeStack = new StackPanel { Margin = new Thickness(0, 0, 12, 0) };
            sizeStack.Children.Add(T.Text("分辨率", 12, T.Muted));
            _sizeBox = new SelectBox(36) { Margin = new Thickness(0, 4, 0, 0) };
            _sizeBox.SetItems(new[] { "原生", "1920", "1280", "1024" }, 0);
            sizeStack.Children.Add(_sizeBox);
            form.Children.Add(sizeStack);

            var bitStack = new StackPanel { Margin = new Thickness(0, 0, 12, 0) };
            bitStack.Children.Add(T.Text("码率", 12, T.Muted));
            _bitrateBox = new SelectBox(36) { Margin = new Thickness(0, 4, 0, 0) };
            _bitrateBox.SetItems(new[] { "8M", "4M", "2M" }, 0);
            bitStack.Children.Add(_bitrateBox);
            Grid.SetColumn(bitStack, 1);
            form.Children.Add(bitStack);

            _topmost = new CheckBox { Content = "窗口置顶", VerticalAlignment = VerticalAlignment.Bottom, Margin = new Thickness(0, 0, 0, 2), FontFamily = T.Font, FontSize = 12.5 };
            Grid.SetColumn(_topmost, 2);
            form.Children.Add(_topmost);
            body.Children.Add(form);

            var actions = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 16, 0, 0) };
            var start = T.Button("开始投屏", true, delegate { Start(); });
            actions.Children.Add(start);
            var stop = T.Button("停止", false, delegate { Stop(); });
            stop.Margin = new Thickness(8, 0, 0, 0);
            actions.Children.Add(stop);
            body.Children.Add(actions);

            _status = T.Text("", 12.5, T.Muted);
            _status.Margin = new Thickness(0, 12, 0, 0);
            _status.TextWrapping = TextWrapping.Wrap;
            body.Children.Add(_status);
            card.Child = body;
            stack.Children.Add(card);
        }

        public override void OnShown()
        {
            _serial = Dev.Serial();
            string exe = FindScrcpy();
            _status.Text = exe.Length > 0
                ? "scrcpy：" + exe + (_serial.Length > 0 ? "\n设备：" + _serial : "\n未连接设备")
                : "内置 scrcpy 缺失，请重新安装";
        }

        static string FindScrcpy()
        {
            string dir = AppDomain.CurrentDomain.BaseDirectory;
            string[] cands =
            {
                Path.Combine(dir, "scrcpy.exe"),
                Path.Combine(dir, "tools", "scrcpy.exe"),
                Path.Combine(dir, "scrcpy", "scrcpy.exe"),
            };
            foreach (string c in cands)
            {
                if (File.Exists(c)) { return c; }
            }
            string pathVar = Environment.GetEnvironmentVariable("PATH") ?? "";
            foreach (string part in pathVar.Split(';'))
            {
                try
                {
                    string c = Path.Combine(part.Trim(), "scrcpy.exe");
                    if (File.Exists(c)) { return c; }
                }
                catch { }
            }
            return "";
        }

        void Start()
        {
            string exe = FindScrcpy();
            if (exe.Length == 0)
            {
                _win.ShowToast("没有找到 scrcpy.exe");
                return;
            }
            _serial = Dev.Serial();
            if (_serial.Length == 0)
            {
                _win.ShowToast("没有已连接的设备");
                return;
            }
            if (_proc != null && !_proc.HasExited)
            {
                _win.ShowToast("投屏已经在运行");
                return;
            }
            string args = "-s " + _serial + " --window-title \"A梦工具箱 投屏\"";
            if (_sizeBox.SelectedIndex > 0) { args += " --max-size " + _sizeBox.SelectedItem; }
            args += " --video-bit-rate " + _bitrateBox.SelectedItem;
            if (_topmost.IsChecked == true) { args += " --always-on-top"; }
            try
            {
                _proc = Process.Start(new ProcessStartInfo(exe, args) { UseShellExecute = false });
                _status.Text = "投屏已启动：" + _serial;
            }
            catch (Exception ex)
            {
                _win.ShowToast("启动失败：" + ex.Message);
            }
        }

        void Stop()
        {
            try
            {
                if (_proc != null && !_proc.HasExited)
                {
                    _proc.Kill();
                    _status.Text = "已停止投屏";
                }
            }
            catch { }
        }

    }

    /* ======================= 基带备份 ======================= */
    class BasebandPage : PageBase
    {
        readonly MainWindow _win;
        readonly StackPanel _list = new StackPanel();
        readonly TextBlock _status;
        readonly CheckBox _all;
        string _serial = "";
        List<string[]> _parts = new List<string[]>();
        static readonly string[] Keys = { "modem", "baseband", "radio", "fsg", "fsc", "modemst", "nvdata", "nvram", "persist" };

        public BasebandPage(MainWindow win)
        {
            _win = win;
            Title = "基带备份";
            Background = Brushes.Transparent;

            var scroll = Ui.PageScroll();
            Children.Add(scroll);
            var stack = new StackPanel();
            scroll.Content = stack;
            stack.Children.Add(Ui.Header("基带备份", "modem / fsg / persist 等分区的备份与还原。"));

            var card = Ui.Card("#FDF3F9");
            card.Padding = new Thickness(20);
            var body = new StackPanel();
            var head = new Grid();
            head.ColumnDefinitions.Add(new ColumnDefinition());
            head.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            head.Children.Add(T.Text("分区", 15, T.Ink, FontWeights.SemiBold));
            var load = Ui.SmallButton("读取分区表", delegate { LoadParts(); });
            Grid.SetColumn(load, 1);
            head.Children.Add(load);
            body.Children.Add(head);

            _status = T.Text("需要 root；点「读取分区表」", 12, T.Muted);
            _status.Margin = new Thickness(0, 8, 0, 8);
            body.Children.Add(_status);

            _all = new CheckBox { Content = "显示全部分区", FontFamily = T.Font, FontSize = 12.5, Margin = new Thickness(0, 0, 0, 8) };
            _all.Checked += delegate { Render(); };
            _all.Unchecked += delegate { Render(); };
            body.Children.Add(_all);

            var ls = new ScrollViewer { Height = 420, VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
            ls.Content = _list;
            body.Children.Add(ls);
            card.Child = body;
            stack.Children.Add(card);
        }

        public override void OnShown()
        {
            _serial = Dev.Serial();
        }

        void LoadParts()
        {
            if (_serial.Length == 0) { _serial = Dev.Serial(); }
            if (_serial.Length == 0) { _win.ShowToast("没有已连接的设备"); return; }
            _status.Text = "读取中…";
            string serial = _serial;
            Task.Run(delegate
            {
                List<string[]> parts = Adb.Partitions(serial);
                Dispatcher.Invoke(new Action(delegate
                {
                    _parts = parts;
                    _status.Text = parts.Count + " 个分区";
                    Render();
                }));
            });
        }

        void Render()
        {
            _list.Children.Clear();
            bool all = _all.IsChecked == true;
            int shown = 0;
            foreach (string[] p in _parts)
            {
                bool match = all;
                foreach (string k in Keys)
                {
                    if (p[0].ToLowerInvariant().Contains(k)) { match = true; break; }
                }
                if (!match) { continue; }
                shown++;
                string name = p[0];
                var title = T.Text(name, 13, T.Ink, FontWeights.SemiBold);
                title.Width = 240;
                var size = T.Text(DeviceInfo.Human(ParseLong(p[1])), 12.5, T.Muted);
                size.Width = 110;
                var backup = Ui.SmallButton("备份", delegate { Backup(name); });
                backup.Margin = new Thickness(6, 0, 0, 0);
                var restore = Ui.SmallButton("还原", delegate { Restore(name); });
                restore.Margin = new Thickness(6, 0, 0, 0);

                var row = new Grid();
                row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(250) });
                row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(120) });
                row.ColumnDefinitions.Add(new ColumnDefinition());
                row.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
                row.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
                row.Children.Add(title);
                Grid.SetColumn(size, 1);
                row.Children.Add(size);
                Grid.SetColumn(backup, 3);
                row.Children.Add(backup);
                Grid.SetColumn(restore, 4);
                row.Children.Add(restore);
                _list.Children.Add(new Border
                {
                    Padding = new Thickness(2, 7, 2, 7),
                    BorderBrush = new SolidColorBrush(Color.FromArgb(14, 0, 0, 0)),
                    BorderThickness = new Thickness(0, 0, 0, 1),
                    Child = row,
                });
            }
            if (shown == 0)
            {
                var t = T.Text("没有匹配的基带分区，勾选「显示全部分区」看看", 12.5, T.Dim);
                t.HorizontalAlignment = HorizontalAlignment.Center;
                t.Margin = new Thickness(0, 60, 0, 0);
                _list.Children.Add(t);
            }
        }

        static long ParseLong(string s)
        {
            long v;
            long.TryParse(s, out v);
            return v;
        }

        void Backup(string part)
        {
            string dir = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "backups");
            Directory.CreateDirectory(dir);
            string file = Path.Combine(dir, part + "-" + DateTime.Now.ToString("yyyyMMdd-HHmmss") + ".img");
            string serial = _serial;
            _win.ShowToast("正在备份 " + part + "…");
            Task.Run(delegate
            {
                bool ok = Adb.Backup(serial, part, file, null);
                Dispatcher.Invoke(new Action(delegate { _win.ShowToast(ok ? "已备份：" + Path.GetFileName(file) : "备份失败", !ok); }));
            });
        }

        void Restore(string part)
        {
            var dlg = new Microsoft.Win32.OpenFileDialog { Filter = "镜像 (*.img)|*.img|所有文件|*.*" };
            if (dlg.ShowDialog() != true) { return; }
            if (MessageBox.Show("把\n" + dlg.FileName + "\n还原到 " + part + "？", "还原分区",
                MessageBoxButton.OKCancel, MessageBoxImage.Warning) != MessageBoxResult.OK)
            {
                return;
            }
            string serial = _serial;
            string image = dlg.FileName;
            _win.ShowToast("写入中…");
            Task.Run(delegate
            {
                bool ok = Adb.Restore(serial, part, image);
                Dispatcher.Invoke(new Action(delegate { _win.ShowToast(ok ? "已写入 " + part : "写入失败", !ok); }));
            });
        }
    }

    /* ======================= 终端 ======================= */
    class TerminalPage : PageBase
    {
        readonly MainWindow _win;
        readonly TextBox _out;
        readonly Border _input;
        readonly CheckBox _root;
        readonly SelectBox _target;
        readonly List<string> _history = new List<string>();
        int _pos;
        string _serial = "";

        public TerminalPage(MainWindow win)
        {
            _win = win;
            Title = "终端";
            Background = Brushes.Transparent;

            var grid = new Grid { Margin = new Thickness(20, 14, 20, 18) };
            grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            grid.RowDefinitions.Add(new RowDefinition());
            grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            Children.Add(grid);

            grid.Children.Add(Ui.Header("终端", "设备 adb shell，或直接调用本机 CMD。"));

            _out = new TextBox
            {
                IsReadOnly = true,
                AcceptsReturn = true,
                FontFamily = new FontFamily("Cascadia Mono, Consolas"),
                FontSize = 12,
                Background = new SolidColorBrush(Color.FromArgb(255, 250, 251, 253)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(20, 0, 0, 0)),
                BorderThickness = new Thickness(1),
                Padding = new Thickness(10),
                VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
                TextWrapping = TextWrapping.Wrap,
                Margin = new Thickness(0, 10, 0, 10),
            };
            Grid.SetRow(_out, 1);
            grid.Children.Add(_out);

            var bar = new StackPanel { Orientation = Orientation.Horizontal };
            _target = new SelectBox(36) { Width = 150, Margin = new Thickness(0, 0, 8, 0) };
            _target.SetItems(new[] { "设备 adb shell", "本机 CMD" }, 0);
            bar.Children.Add(_target);
            _input = Ui.Input("输入命令，回车执行", 36);
            _input.Width = 640;
            bar.Children.Add(_input);
            var run = T.Button("执行", true, delegate { Run(); });
            run.Margin = new Thickness(8, 0, 0, 0);
            bar.Children.Add(run);
            _root = new CheckBox { Content = "root", FontFamily = T.Font, FontSize = 12.5, VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(10, 0, 10, 0) };
            bar.Children.Add(_root);
            var clear = T.Button("清屏", false, delegate { _out.Clear(); });
            bar.Children.Add(clear);
            Grid.SetRow(bar, 2);
            grid.Children.Add(bar);

            Ui.BoxOf(_input).KeyDown += delegate (object s, KeyEventArgs e)
            {
                if (e.Key == Key.Enter) { Run(); e.Handled = true; }
                if (e.Key == Key.Up && _pos > 0) { _pos--; Ui.BoxOf(_input).Text = _history[_pos]; }
                if (e.Key == Key.Down && _pos < _history.Count - 1) { _pos++; Ui.BoxOf(_input).Text = _history[_pos]; }
            };
            Append("就绪。命令通过 adb shell 执行。");
        }

        public override void OnShown()
        {
            _serial = Dev.Serial();
        }

        void Append(string text)
        {
            _out.AppendText(text + Environment.NewLine);
            _out.ScrollToEnd();
        }

        void RunLocal(string cmd)
        {
            Task.Run(delegate
            {
                string output;
                int code = 0;
                try
                {
                    var psi = new ProcessStartInfo("cmd.exe", "/c " + cmd)
                    {
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        UseShellExecute = false,
                        CreateNoWindow = true,
                        StandardOutputEncoding = Encoding.Default,
                        StandardErrorEncoding = Encoding.Default,
                    };
                    using (var p = Process.Start(psi))
                    {
                        string o = p.StandardOutput.ReadToEnd();
                        string e = p.StandardError.ReadToEnd();
                        if (!p.WaitForExit(60000))
                        {
                            try { p.Kill(); } catch { }
                            output = "命令超时（60 秒），已终止。";
                        }
                        else
                        {
                            code = p.ExitCode;
                            output = (o + (e.Length > 0 ? "\n" + e : "")).TrimEnd();
                        }
                    }
                }
                catch (Exception ex)
                {
                    output = ex.Message;
                    code = -1;
                }
                Dispatcher.Invoke(new Action(delegate
                {
                    Append(output.Length > 0 ? output : "(无输出)");
                    Append("[退出码 " + code + "]");
                }));
            });
        }

        void Run()
        {
            string cmd = Ui.BoxOf(_input).Text.Trim();
            if (cmd.Length == 0) { return; }
            _history.Add(cmd);
            _pos = _history.Count;
            Ui.BoxOf(_input).Clear();
            if (_target.SelectedIndex == 1)
            {
                Append("> " + cmd);
                RunLocal(cmd);
                return;
            }
            if (_serial.Length == 0) { _serial = Dev.Serial(); }
            if (_serial.Length == 0) { Append("没有已连接的设备"); return; }
            string serial = _serial;
            bool root = _root.IsChecked == true;
            Append((root ? "# " : "$ ") + cmd);
            Task.Run(delegate
            {
                AdbResult r = root ? Adb.Su(serial, cmd, 60000) : Adb.Shell(serial, cmd, 60000);
                Dispatcher.Invoke(new Action(delegate
                {
                    string body = (r.Out + (r.Err.Length > 0 ? "\n" + r.Err : "")).TrimEnd();
                    Append(body.Length > 0 ? body : "(无输出)");
                    Append("[退出码 " + r.Code + "]");
                }));
            });
        }
    }
}
