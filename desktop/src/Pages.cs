using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;

namespace Iris
{
    static class Ui
    {
        public static Border Input(string placeholder, double height)
        {
            var border = new Border
            {
                Height = height,
                CornerRadius = new CornerRadius(7),
                Background = T.B("#FFFFFF"),
                BorderBrush = T.B("#D5DAE1"),
                BorderThickness = new Thickness(1),
                Padding = new Thickness(10, 0, 10, 0),
            };
            var tb = new TextBox
            {
                BorderThickness = new Thickness(0),
                Background = Brushes.Transparent,
                FontFamily = T.Font,
                FontSize = 13,
                Foreground = new SolidColorBrush(T.Ink),
            };
            tb.ToolTip = placeholder;
            border.Child = tb;
            border.Tag = tb;
            tb.GotFocus += delegate { border.BorderBrush = new SolidColorBrush(T.Accent); };
            tb.LostFocus += delegate { border.BorderBrush = T.B("#D5DAE1"); };
            return border;
        }

        public static TextBox BoxOf(Border input)
        {
            return (TextBox)input.Tag;
        }

        public static FrameworkElement Header(string title, string subtitle)
        {
            var stack = new StackPanel { Margin = new Thickness(0, 0, 0, 16) };
            stack.Children.Add(T.Text(title, 24, T.Ink, FontWeights.SemiBold));
            if (!string.IsNullOrEmpty(subtitle))
            {
                var s = T.Text(subtitle, 12.5, T.Muted);
                s.Margin = new Thickness(0, 4, 0, 0);
                stack.Children.Add(s);
            }
            return new Border { Child = stack };
        }

        public static Border Card(string bg)
        {
            return T.Card(bg);
        }

        public static Border SmallButton(string text, RoutedEventHandler click)
        {
            var b = T.Button(text, false, click);
            b.Height = 30;
            b.Padding = new Thickness(10, 0, 10, 0);
            return b;
        }

        public static ScrollViewer PageScroll()
        {
            return new ScrollViewer
            {
                VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
                HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled,
                Padding = new Thickness(22, 16, 22, 20),
            };
        }

        /// <summary>窗口比内容高时，把内容垂直居中；内容更高时退回顶部并允许滚动。</summary>
        public static void CenterVertically(ScrollViewer scroll, FrameworkElement content)
        {
            double vh = scroll.ActualHeight - scroll.Padding.Top - scroll.Padding.Bottom;
            double vw = scroll.ActualWidth - scroll.Padding.Left - scroll.Padding.Right;
            if (vh <= 0 || vw <= 0)
            {
                return;
            }
            content.Margin = new Thickness(0);
            content.Measure(new Size(vw, double.PositiveInfinity));
            double ch = content.DesiredSize.Height;
            double top = Math.Max(0, (vh - ch) / 2);
            content.Margin = new Thickness(0, top, 0, 0);
        }
    }

    /* ======================= 刷机 ======================= */
    class FlashPage : PageBase
    {
        readonly MainWindow _win;
        readonly StackPanel _list = new StackPanel();
        readonly TextBlock _status;
        readonly TextBlock _targetText;
        readonly Border _imageInput;
        readonly SelectBox _brand;
        readonly SelectBox _partPick;
        readonly Border _flashImageInput;
        readonly TextBlock _flashStatus;
        readonly TextBlock _brandHint;
        readonly Border _xiaomiDir;
        readonly CheckBox _autoReboot;
        readonly CheckBox _waitFb;
        readonly RadioButton _xiaomiClear;
        readonly RadioButton _xiaomiKeep;
        readonly RadioButton _xiaomiLock;
        readonly SelectBox _blCmd;
        string _serial = "";
        string _selectedPart = "";

        public FlashPage(MainWindow win)
        {
            _win = win;
            Title = "刷机";
            Background = Brushes.Transparent;

            var scroll = Ui.PageScroll();
            Children.Add(scroll);
            var stack = new StackPanel();
            scroll.Content = stack;
            stack.Children.Add(Ui.Header("刷机", "按品牌做单分区线刷；整包请用对应品牌工具。"));

            var wire = Ui.Card("#FDF3F9");
            wire.Padding = new Thickness(20);
            wire.Margin = new Thickness(0, 0, 0, 14);
            var wb = new StackPanel();
            wb.Children.Add(T.Text("常规镜像刷入", 15, T.Ink, FontWeights.SemiBold));
            var wrow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 10, 0, 0) };
            _brand = new SelectBox(34) { Width = 170, Margin = new Thickness(0, 0, 10, 0) };
            _brand.SetItems(new[] { "通用 / 其他", "小米 / 红米", "三星", "OPPO / 一加 / realme", "vivo / iQOO", "华为 / 荣耀" }, 0);
            _brand.Changed += delegate { UpdateBrandHint(); };
            wrow.Children.Add(_brand);
            _partPick = new SelectBox(34) { Width = 150, Margin = new Thickness(0, 0, 10, 0) };
            _partPick.SetItems(new[] { "boot", "init_boot", "recovery", "vbmeta", "vendor_boot", "dtbo", "super", "system" }, 0);
            wrow.Children.Add(_partPick);
            _flashImageInput = Ui.Input("选择要刷入的 .img 镜像", 34);
            _flashImageInput.Width = 360;
            wrow.Children.Add(_flashImageInput);
            var pickImg = T.Button("导入镜像", false, delegate { PickFlashImage(); });
            pickImg.Margin = new Thickness(8, 0, 0, 0);
            wrow.Children.Add(pickImg);
            var flashGo = T.Button("开始线刷", true, delegate { StartWireFlash(); });
            flashGo.Margin = new Thickness(8, 0, 0, 0);
            wrow.Children.Add(flashGo);
            wb.Children.Add(wrow);
            var opts = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 6, 0, 0) };
            _autoReboot = new CheckBox { Content = "自动重启", IsChecked = true, FontFamily = T.Font, FontSize = 12.5, Margin = new Thickness(0, 0, 16, 0) };
            _waitFb = new CheckBox { Content = "等待 FB 设备", IsChecked = true, FontFamily = T.Font, FontSize = 12.5 };
            opts.Children.Add(_autoReboot);
            opts.Children.Add(_waitFb);
            wb.Children.Add(opts);

            var xrow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 8, 0, 0) };
            var xlabel = T.Text("小米整包目录", 12, T.Muted);
            xlabel.Margin = new Thickness(0, 0, 8, 0);
            xrow.Children.Add(xlabel);
            _xiaomiDir = Ui.Input("解压后的固件目录（含 flash_all.bat）", 34);
            _xiaomiDir.Width = 430;
            xrow.Children.Add(_xiaomiDir);
            var xpick = T.Button("选择目录", false, delegate { PickXiaomiFolder(); });
            xpick.Margin = new Thickness(8, 0, 0, 0);
            xrow.Children.Add(xpick);
            var xgo = T.Button("整包线刷", true, delegate { StartXiaomiFlash(); });
            xgo.Margin = new Thickness(8, 0, 0, 0);
            xrow.Children.Add(xgo);
            wb.Children.Add(xrow);
            var xopts = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 6, 0, 0) };
            _xiaomiClear = new RadioButton { Content = "清除数据刷机", IsChecked = true, GroupName = "xiaomimode", FontFamily = T.Font, FontSize = 12.5, Margin = new Thickness(0, 0, 16, 0) };
            _xiaomiKeep = new RadioButton { Content = "保留数据刷机", GroupName = "xiaomimode", FontFamily = T.Font, FontSize = 12.5, Margin = new Thickness(0, 0, 16, 0) };
            _xiaomiLock = new RadioButton { Content = "清除数据并回锁 BL", GroupName = "xiaomimode", FontFamily = T.Font, FontSize = 12.5 };
            xopts.Children.Add(_xiaomiClear);
            xopts.Children.Add(_xiaomiKeep);
            xopts.Children.Add(_xiaomiLock);
            wb.Children.Add(xopts);
            _flashStatus = T.Text("", 12, T.Muted);
            _flashStatus.Margin = new Thickness(0, 10, 0, 0);
            _flashStatus.TextWrapping = TextWrapping.Wrap;
            wb.Children.Add(_flashStatus);
            _brandHint = T.Text("", 12, T.Dim);
            _brandHint.Margin = new Thickness(0, 6, 0, 0);
            _brandHint.TextWrapping = TextWrapping.Wrap;
            wb.Children.Add(_brandHint);
            UpdateBrandHint();
            wire.Child = wb;
            stack.Children.Add(wire);

            /* ---------- Bootloader / 扩展 ---------- */
            var bl = Ui.Card("#F3F8FE");
            bl.Padding = new Thickness(20);
            bl.Margin = new Thickness(0, 0, 0, 14);
            var blb = new StackPanel();
            blb.Children.Add(T.Text("Bootloader 操作", 15, T.Ink, FontWeights.SemiBold));
            var blrow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 10, 0, 0) };
            _blCmd = new SelectBox(34) { Width = 300, Margin = new Thickness(0, 0, 10, 0) };
            _blCmd.SetItems(new[]
            {
                "fastboot flashing unlock",
                "fastboot flashing lock",
                "fastboot oem unlock",
                "fastboot oem lock",
                "fastboot reboot bootloader",
                "fastboot getvar current-slot",
            }, 0);
            blrow.Children.Add(_blCmd);
            var blgo = T.Button("执行指令", true, delegate { ExecBootloader(); });
            blrow.Children.Add(blgo);
            blb.Children.Add(blrow);
            var ext = new WrapPanel { Margin = new Thickness(0, 12, 0, 0) };
            AddExt(ext, "格式化设备双清", delegate { Ext("wipe"); });
            AddExt(ext, "修复 ADB 异常", delegate { Ext("adb"); });
            AddExt(ext, "强开 USB 调试", delegate { Ext("usbdebug"); });
            AddExt(ext, "切换文件传输 MTP", delegate { Ext("mtp"); });
            AddExt(ext, "读 DDR / 硬件", delegate { Ext("ddr"); });
            AddExt(ext, "强开基带调试口", delegate { Ext("diag"); });
            blb.Children.Add(ext);
            bl.Child = blb;
            stack.Children.Add(bl);

            var card = Ui.Card("#F4F8FE");
            card.Padding = new Thickness(20);
            card.Margin = new Thickness(0, 0, 0, 14);

            var head = new Grid();
            head.ColumnDefinitions.Add(new ColumnDefinition());
            head.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            head.Children.Add(T.Text("分区表", 15, T.Ink, FontWeights.SemiBold));
            var refresh = Ui.SmallButton("读取分区表", delegate { LoadParts(); });
            Grid.SetColumn(refresh, 1);
            head.Children.Add(refresh);

            _status = T.Text("需要 root；点「读取分区表」开始", 12, T.Muted);
            _status.Margin = new Thickness(0, 8, 0, 10);

            var listScroll = new ScrollViewer { Height = 340, VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
            listScroll.Content = _list;
            var hintEmpty = T.Text("连接设备并授权 root 后，点右上角「读取分区表」", 12.5, T.Dim);
            hintEmpty.HorizontalAlignment = HorizontalAlignment.Center;
            hintEmpty.Margin = new Thickness(0, 140, 0, 0);
            _list.Children.Add(hintEmpty);

            var body = new StackPanel();
            body.Children.Add(head);
            body.Children.Add(_status);
            body.Children.Add(listScroll);
            card.Child = body;
            stack.Children.Add(card);

            var restoreCard = Ui.Card("#FDF3F9");
            restoreCard.Padding = new Thickness(20);
            var restoreStack = new StackPanel();
            restoreStack.Children.Add(T.Text("还原分区", 15, T.Ink, FontWeights.SemiBold));
            var hint = T.Text("先在分区表里点「还原」选中目标，再填电脑上的镜像路径。", 12, T.Muted);
            hint.Margin = new Thickness(0, 4, 0, 12);
            restoreStack.Children.Add(hint);

            var row = new StackPanel { Orientation = Orientation.Horizontal };
            _imageInput = Ui.Input("镜像绝对路径，例如 D:\\boot.img", 38);
            _imageInput.Width = 520;
            row.Children.Add(_imageInput);
            var pick = T.Button("选择文件", false, delegate { PickImage(); });
            pick.Margin = new Thickness(10, 0, 0, 0);
            row.Children.Add(pick);
            var go = T.Button("写入分区", true, delegate { DoRestore(); });
            go.Margin = new Thickness(10, 0, 0, 0);
            row.Children.Add(go);
            restoreStack.Children.Add(row);

            _targetText = T.Text("目标分区：—", 12.5, T.Muted);
            _targetText.Margin = new Thickness(0, 10, 0, 0);
            restoreStack.Children.Add(_targetText);
            restoreCard.Child = restoreStack;
            stack.Children.Add(restoreCard);
        }

        public override void OnShown()
        {
            string serial = FirstUsableSerial();
            if (serial != _serial)
            {
                _serial = serial;
                _list.Children.Clear();
                _status.Text = "需要 root；点「读取分区表」开始";
            }
        }

        static string FirstUsableSerial()
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

        void PickFlashImage()
        {
            var dlg = new Microsoft.Win32.OpenFileDialog { Filter = "镜像 (*.img;*.bin)|*.img;*.bin|所有文件|*.*" };
            if (dlg.ShowDialog() == true)
            {
                Ui.BoxOf(_flashImageInput).Text = dlg.FileName;
            }
        }

        void UpdateBrandHint()
        {
            if (_brandHint == null) { return; }
            switch (_brand.SelectedIndex)
            {
                case 1:
                    _brandHint.Text = "小米/红米：整包线刷用官方 MiFlash 或解压后的 flash_all.bat；这里用于刷单个 boot / init_boot / recovery。";
                    break;
                case 2:
                    _brandHint.Text = "三星：一般用 Odin / Heimdall 刷 AP/BL/CP/CSC，Fastboot 分区刷写不适用于大多数三星机型。";
                    break;
                case 3:
                    _brandHint.Text = "OPPO/一加/realme：部分机型需 fastbootd，整包建议用官方线刷工具；单分区可刷 boot/init_boot。";
                    break;
                case 4:
                    _brandHint.Text = "vivo/iQOO：Fastboot 权限受限，部分机型只能用量产工具；谨慎操作。";
                    break;
                case 5:
                    _brandHint.Text = "华为/荣耀：Fastboot 受限，整包通常用官方工具；单分区刷写可能被校验拦截。";
                    break;
                default:
                    _brandHint.Text = "通用：把镜像刷进指定分区，分区名必须和机型完全匹配。";
                    break;
            }
        }

        void StartWireFlash()
        {
            string image = Ui.BoxOf(_flashImageInput).Text.Trim();
            if (image.Length == 0 || !System.IO.File.Exists(image))
            {
                _win.ShowToast("先导入一个存在的镜像");
                return;
            }
            string part = _partPick.SelectedItem;
            if (MessageBox.Show("把\n" + image + "\n刷进 " + part + " 分区？\n分区错误会导致无法开机。", "线刷",
                MessageBoxButton.OKCancel, MessageBoxImage.Warning) != MessageBoxResult.OK)
            {
                return;
            }
            _flashStatus.Text = "准备中…";
            bool waitFb = _waitFb.IsChecked == true;
            bool autoReboot = _autoReboot.IsChecked == true;
            Task.Run(delegate
            {
                string serial = "";
                foreach (string[] d in Adb.Devices())
                {
                    if (d[1] == "device") { serial = d[0]; break; }
                }
                if (serial.Length > 0 && waitFb)
                {
                    Adb.Reboot(serial, "bootloader");
                    for (int i = 0; i < 12; i++)
                    {
                        System.Threading.Thread.Sleep(1000);
                        if (Adb.FastbootDevices().Count > 0) { break; }
                    }
                }
                List<string> devs = Adb.FastbootDevices();
                if (devs.Count == 0)
                {
                    Dispatcher.Invoke(new Action(delegate
                    {
                        _flashStatus.Text = "没有进入 Fastboot 的设备，请手动进 bootloader 后重试。";
                        _win.ShowToast("没有 Fastboot 设备", true);
                    }));
                    return;
                }
                AdbResult r = Adb.Fastboot("-s " + devs[0] + " flash " + part + " \"" + image + "\"", 600000);
                if (r.Ok && autoReboot)
                {
                    Adb.Fastboot("-s " + devs[0] + " reboot", 30000);
                }
                Dispatcher.Invoke(new Action(delegate
                {
                    _flashStatus.Text = (r.Out + "\n" + r.Err).Trim();
                    _win.ShowToast(r.Ok ? "刷入完成" : "刷入失败", !r.Ok);
                }));
            });
        }

        void AddExt(WrapPanel wrap, string text, RoutedEventHandler click)
        {
            var b = T.Button(text, false, click);
            b.Height = 32;
            b.Padding = new Thickness(10, 0, 10, 0);
            b.Margin = new Thickness(0, 0, 8, 8);
            wrap.Children.Add(b);
        }

        static string AdbSerial()
        {
            foreach (string[] d in Adb.Devices())
            {
                if (d[1] == "device") { return d[0]; }
            }
            return "";
        }

        void ExecBootloader()
        {
            string cmd = _blCmd.SelectedItem;
            if ((cmd.Contains("unlock") || cmd.Contains("lock"))
                && MessageBox.Show("执行 " + cmd + "？\n解锁/回锁会清空数据并有风险。", "Bootloader",
                    MessageBoxButton.OKCancel, MessageBoxImage.Warning) != MessageBoxResult.OK)
            {
                return;
            }
            _flashStatus.Text = "执行：" + cmd;
            Task.Run(delegate
            {
                List<string> devs = Adb.FastbootDevices();
                AdbResult r;
                if (devs.Count > 0 && !cmd.StartsWith("fastboot reboot") && !cmd.StartsWith("fastboot getvar"))
                {
                    r = Adb.Fastboot("-s " + devs[0] + " " + cmd.Substring("fastboot ".Length), 60000);
                }
                else
                {
                    r = Adb.Fastboot(cmd.Substring("fastboot ".Length), 60000);
                }
                Dispatcher.Invoke(new Action(delegate
                {
                    _flashStatus.Text = (r.Out + "\n" + r.Err).Trim();
                    _win.ShowToast(r.Ok ? "命令已执行" : "命令失败", !r.Ok);
                }));
            });
        }

        void Ext(string kind)
        {
            string serial = AdbSerial();
            if (kind == "wipe"
                && MessageBox.Show("格式化设备（双清）会清空数据，继续？", "格式化", MessageBoxButton.OKCancel, MessageBoxImage.Warning) != MessageBoxResult.OK)
            {
                return;
            }
            if (kind == "diag"
                && MessageBox.Show("强开基带调试端口可能影响 USB 功能，继续？", "基带调试", MessageBoxButton.OKCancel, MessageBoxImage.Warning) != MessageBoxResult.OK)
            {
                return;
            }
            Task.Run(delegate
            {
                string result = "";
                try
                {
                    if (kind == "wipe")
                    {
                        if (Adb.FastbootDevices().Count > 0)
                        {
                            result = Adb.Fastboot("-w", 120000).Out;
                        }
                        else if (serial.Length > 0)
                        {
                            result = Adb.Shell(serial, "recovery --wipe_data", 30000).Out;
                        }
                    }
                    else if (kind == "adb")
                    {
                        Adb.Run("kill-server", 8000);
                        Adb.Run("start-server", 10000);
                        result = "ADB 已重启";
                    }
                    else if (serial.Length > 0)
                    {
                        if (kind == "usbdebug")
                        {
                            Adb.Shell(serial, "settings put global adb_enabled 1", 10000);
                            result = "已尝试强开 USB 调试";
                        }
                        else if (kind == "mtp")
                        {
                            result = Adb.Shell(serial, "svc usb setFunctions mtp", 10000).Out;
                        }
                        else if (kind == "ddr")
                        {
                            result = "ddr_type=" + Adb.Shell(serial, "getprop ro.boot.ddr_type", 8000).Out.Trim()
                                + "  hardware=" + Adb.Shell(serial, "getprop ro.hardware", 8000).Out.Trim();
                        }
                        else if (kind == "diag")
                        {
                            result = Adb.Shell(serial, "setprop persist.sys.usb.config diag,adb", 10000).Out;
                        }
                    }
                }
                catch (Exception ex)
                {
                    result = ex.Message;
                }
                Dispatcher.Invoke(new Action(delegate
                {
                    _flashStatus.Text = string.IsNullOrEmpty(result) ? "已执行" : result;
                }));
            });
        }

        void PickXiaomiFolder()
        {
            using (var dlg = new System.Windows.Forms.FolderBrowserDialog())
            {
                dlg.Description = "选择解压后的小米/红米线刷包目录（含 flash_all.bat）";
                if (dlg.ShowDialog() == System.Windows.Forms.DialogResult.OK)
                {
                    Ui.BoxOf(_xiaomiDir).Text = dlg.SelectedPath;
                }
            }
        }

        void StartXiaomiFlash()
        {
            string dir = Ui.BoxOf(_xiaomiDir).Text.Trim();
            if (!System.IO.Directory.Exists(dir))
            {
                _win.ShowToast("先选择解压后的固件目录");
                return;
            }
            string pattern = _xiaomiLock.IsChecked == true
                ? "flash_all_lock*.bat"
                : (_xiaomiKeep.IsChecked == true ? "flash_all_except_storage*.bat" : "flash_all*.bat");
            string bat = "";
            foreach (string f in System.IO.Directory.GetFiles(dir, pattern))
            {
                bat = f;
                break;
            }
            if (bat.Length == 0)
            {
                _win.ShowToast("目录里没有 flash_all*.bat");
                return;
            }
            if (MessageBox.Show("执行整包线刷？\n" + bat + "\n\n会清空数据，请确认已解锁并进入 Fastboot。", "小米整包线刷",
                MessageBoxButton.OKCancel, MessageBoxImage.Warning) != MessageBoxResult.OK)
            {
                return;
            }
            _flashStatus.Text = "整包线刷中，请勿断开…";
            string work = dir;
            string exeDir = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
            Task.Run(delegate
            {
                string output = "";
                int code = 0;
                try
                {
                    var psi = new System.Diagnostics.ProcessStartInfo("cmd.exe", "/c \"\"" + bat + "\"\"")
                    {
                        WorkingDirectory = work,
                        UseShellExecute = false,
                        CreateNoWindow = true,
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        StandardOutputEncoding = System.Text.Encoding.Default,
                        StandardErrorEncoding = System.Text.Encoding.Default,
                    };
                    psi.EnvironmentVariables["PATH"] = exeDir + ";" + (psi.EnvironmentVariables["PATH"] ?? "");
                    using (var p = System.Diagnostics.Process.Start(psi))
                    {
                        string o = p.StandardOutput.ReadToEnd();
                        string e = p.StandardError.ReadToEnd();
                        if (!p.WaitForExit(1800000))
                        {
                            try { p.Kill(); } catch { }
                            output = "超时（30 分钟），已终止。";
                        }
                        else
                        {
                            code = p.ExitCode;
                            output = (o + (e.Length > 0 ? "\n" + e : "")).Trim();
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
                    _flashStatus.Text = (output.Length > 1200 ? output.Substring(output.Length - 1200) : output) + "\n退出码：" + code;
                    _win.ShowToast(code == 0 ? "整包线刷结束" : "整包线刷失败", code != 0);
                }));
            });
        }

        async void LoadParts()
        {
            if (string.IsNullOrEmpty(_serial))
            {
                _serial = FirstUsableSerial();
            }
            if (string.IsNullOrEmpty(_serial))
            {
                _win.ShowToast("没有已连接的设备");
                return;
            }
            _status.Text = "读取中…";
            string serial = _serial;
            List<string[]> parts = null;
            await Task.Run(delegate { parts = Adb.Partitions(serial); });
            _list.Children.Clear();
            if (parts == null || parts.Count == 0)
            {
                _status.Text = "没有读到分区：确认已 root，且设备有 /dev/block/by-name";
                return;
            }
            _status.Text = parts.Count + " 个分区 · " + serial;
            foreach (string[] p in parts)
            {
                string name = p[0];
                var title = T.Text(name, 13, T.Ink2, FontWeights.SemiBold);
                title.Width = 250;
                var size = T.Text(DeviceInfo.Human(ParseLong(p[1])), 12.5, T.Muted);
                size.Width = 110;
                var backup = Ui.SmallButton("备份", delegate { Backup(name); });
                backup.Margin = new Thickness(6, 0, 0, 0);
                var restore = Ui.SmallButton("还原", delegate
                {
                    _selectedPart = name;
                    _targetText.Text = "目标分区：" + name;
                });
                restore.Margin = new Thickness(6, 0, 0, 0);

                var row = new Grid();
                row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(260) });
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
        }

        static long ParseLong(string s)
        {
            long v;
            long.TryParse(s, out v);
            return v;
        }

        async void Backup(string part)
        {
            if (string.IsNullOrEmpty(_serial))
            {
                return;
            }
            string dir = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "backups");
            Directory.CreateDirectory(dir);
            string file = Path.Combine(dir, part + "-" + DateTime.Now.ToString("yyyyMMdd-HHmmss") + ".img");
            if (MessageBox.Show("备份分区 " + part + " 到：\n" + file + "\n\n期间不要拔线。", "备份分区",
                MessageBoxButton.OKCancel, MessageBoxImage.Question) != MessageBoxResult.OK)
            {
                return;
            }
            _win.ShowToast("正在备份 " + part + "…");
            string serial = _serial;
            bool ok = false;
            await Task.Run(delegate { ok = Adb.Backup(serial, part, file, null); });
            _win.ShowToast(ok ? "已备份：" + Path.GetFileName(file) : "备份失败");
        }

        void PickImage()
        {
            var dlg = new Microsoft.Win32.OpenFileDialog { Filter = "镜像文件 (*.img;*.bin)|*.img;*.bin|所有文件|*.*" };
            if (dlg.ShowDialog() == true)
            {
                Ui.BoxOf(_imageInput).Text = dlg.FileName;
            }
        }

        async void DoRestore()
        {
            string image = Ui.BoxOf(_imageInput).Text.Trim();
            if (string.IsNullOrEmpty(_selectedPart))
            {
                _win.ShowToast("先在分区表里点「还原」选择目标分区");
                return;
            }
            if (!File.Exists(image))
            {
                _win.ShowToast("镜像不存在：" + image);
                return;
            }
            if (MessageBox.Show("把\n" + image + "\n写进 " + _selectedPart + "？\n覆盖后无法撤销。", "还原分区",
                MessageBoxButton.OKCancel, MessageBoxImage.Warning) != MessageBoxResult.OK)
            {
                return;
            }
            _win.ShowToast("正在写入 " + _selectedPart + "…");
            string serial = _serial;
            string part = _selectedPart;
            bool ok = false;
            await Task.Run(delegate { ok = Adb.Restore(serial, part, image); });
            _win.ShowToast(ok ? "已写入 " + part : "写入失败，检查镜像与 root");
        }
    }

    /* ======================= 模块 ======================= */
    class ModulesPage : PageBase
    {
        readonly MainWindow _win;
        readonly StackPanel _list = new StackPanel();
        readonly TextBlock _status;
        string _serial = "";

        public ModulesPage(MainWindow win)
        {
            _win = win;
            Title = "模块";
            Background = Brushes.Transparent;

            var scroll = Ui.PageScroll();
            Children.Add(scroll);
            var stack = new StackPanel();
            scroll.Content = stack;
            stack.Children.Add(Ui.Header("模块", "Magisk / KernelSU / APatch 模块的启停与查看。"));

            var card = Ui.Card("#F6F4FC");
            card.Padding = new Thickness(20);
            var head = new Grid();
            head.ColumnDefinitions.Add(new ColumnDefinition());
            head.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            head.Children.Add(T.Text("已安装模块", 15, T.Ink, FontWeights.SemiBold));
            var refresh = Ui.SmallButton("刷新", delegate { LoadModules(); });
            Grid.SetColumn(refresh, 1);
            head.Children.Add(refresh);

            _status = T.Text("需要 root；点「刷新」读取", 12, T.Muted);
            _status.Margin = new Thickness(0, 8, 0, 10);
            var listScroll = new ScrollViewer { Height = 420, VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
            listScroll.Content = _list;

            var body = new StackPanel();
            body.Children.Add(head);
            body.Children.Add(_status);
            body.Children.Add(listScroll);
            card.Child = body;
            stack.Children.Add(card);
        }

        public override void OnShown()
        {
            _serial = First();
        }

        static string First()
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

        async void LoadModules()
        {
            if (string.IsNullOrEmpty(_serial))
            {
                _serial = First();
            }
            if (string.IsNullOrEmpty(_serial))
            {
                _win.ShowToast("没有已连接的设备");
                return;
            }
            _status.Text = "读取中…";
            string serial = _serial;
            List<string[]> mods = null;
            await Task.Run(delegate { mods = Adb.Modules(serial); });
            _list.Children.Clear();
            if (mods == null || mods.Count == 0)
            {
                _status.Text = "没有模块，或当前没有 root";
                return;
            }
            _status.Text = mods.Count + " 个模块";
            foreach (string[] m in mods)
            {
                string name = m[0];
                bool enabled = m[3] != "1";
                var title = T.Text(string.IsNullOrEmpty(m[1]) ? name : m[1], 13.5, T.Ink, FontWeights.SemiBold);
                title.Width = 280;
                var ver = T.Text(m[2], 12.5, T.Muted);
                ver.Width = 110;
                var state = T.Text(enabled ? "启用" : "已禁用", 12.5, enabled ? T.Ok : T.Dim);
                state.Width = 90;
                var toggle = Ui.SmallButton(enabled ? "禁用" : "启用", delegate
                {
                    bool target = !enabled;
                    Task.Run(delegate
                    {
                        Adb.ModuleToggle(serial, name, target);
                        Dispatcher.Invoke(new Action(delegate { LoadModules(); }));
                    });
                });
                toggle.Margin = new Thickness(6, 0, 0, 0);

                var row = new Grid();
                row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(290) });
                row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(120) });
                row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(100) });
                row.ColumnDefinitions.Add(new ColumnDefinition());
                row.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
                row.Children.Add(title);
                Grid.SetColumn(ver, 1);
                row.Children.Add(ver);
                Grid.SetColumn(state, 2);
                row.Children.Add(state);
                Grid.SetColumn(toggle, 4);
                row.Children.Add(toggle);

                _list.Children.Add(new Border
                {
                    Padding = new Thickness(2, 8, 2, 8),
                    BorderBrush = new SolidColorBrush(Color.FromArgb(14, 0, 0, 0)),
                    BorderThickness = new Thickness(0, 0, 0, 1),
                    Child = row,
                });
            }
        }
    }

    /* ======================= 文件 ======================= */
    static class Prompt
    {
        public static string Show(Window owner, string title, string initial)
        {
            var win = new Window
            {
                Title = title,
                Width = 360,
                Height = 150,
                WindowStartupLocation = WindowStartupLocation.CenterOwner,
                Owner = owner,
                ResizeMode = ResizeMode.NoResize,
                FontFamily = T.Font,
                Background = new SolidColorBrush(T.C("#F7F9FC")),
            };
            var panel = new StackPanel { Margin = new Thickness(18) };
            var box = new TextBox
            {
                Text = initial,
                Height = 32,
                FontFamily = T.Font,
                FontSize = 13,
                Padding = new Thickness(6, 0, 6, 0),
                VerticalContentAlignment = VerticalAlignment.Center,
            };
            panel.Children.Add(box);
            var row = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right, Margin = new Thickness(0, 14, 0, 0) };
            string result = null;
            var ok = T.Button("确定", true, delegate { result = box.Text.Trim(); win.Close(); });
            var cancel = T.Button("取消", false, delegate { win.Close(); });
            cancel.Margin = new Thickness(8, 0, 0, 0);
            row.Children.Add(ok);
            row.Children.Add(cancel);
            panel.Children.Add(row);
            win.Content = panel;
            box.Focus();
            box.SelectAll();
            win.ShowDialog();
            return result;
        }
    }

    /* ======================= 应用 ======================= */
    class AppsPage : PageBase
    {
        readonly MainWindow _win;
        readonly StackPanel _list = new StackPanel();
        readonly TextBlock _status;
        readonly Border _filterInput;
        readonly CheckBox _allCheck;
        string _serial = "";
        List<string> _packages = new List<string>();

        public AppsPage(MainWindow win)
        {
            _win = win;
            Title = "应用";
            Background = Brushes.Transparent;

            var scroll = Ui.PageScroll();
            Children.Add(scroll);
            var stack = new StackPanel();
            scroll.Content = stack;
            stack.Children.Add(Ui.Header("应用", "第三方 / 系统应用，支持安装 APK、冻结、清数据、提取和卸载。"));

            var card = Ui.Card("#FDF3F9");
            card.Padding = new Thickness(20);
            var bar = new StackPanel { Orientation = Orientation.Horizontal };
            var filterLabel = T.Text("筛选", 12.5, T.Muted);
            filterLabel.Margin = new Thickness(0, 0, 8, 0);
            bar.Children.Add(filterLabel);
            _filterInput = Ui.Input("按包名筛选", 36);
            _filterInput.Width = 300;
            bar.Children.Add(_filterInput);
            var reload = T.Button("刷新", true, delegate { LoadApps(); });
            reload.Margin = new Thickness(10, 0, 0, 0);
            bar.Children.Add(reload);
            _allCheck = new CheckBox
            {
                Content = "只显示第三方应用",
                Margin = new Thickness(12, 0, 0, 0),
                VerticalAlignment = VerticalAlignment.Center,
                FontFamily = T.Font,
                FontSize = 12.5,
            };
            _allCheck.Checked += delegate { LoadApps(); };
            _allCheck.Unchecked += delegate { LoadApps(); };
            bar.Children.Add(_allCheck);
            var install = T.Button("安装 APK", false, delegate { InstallApk(); });
            install.Margin = new Thickness(10, 0, 0, 0);
            bar.Children.Add(install);
            _status = T.Text("点「刷新」读取应用列表", 12, T.Muted);
            _status.Margin = new Thickness(0, 8, 0, 8);
            var listScroll = new ScrollViewer { Height = 440, VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
            listScroll.Content = _list;
            var emptyHint = T.Text("列表为空：点「刷新」读取", 12.5, T.Dim);
            emptyHint.HorizontalAlignment = HorizontalAlignment.Center;
            emptyHint.Margin = new Thickness(0, 120, 0, 0);
            _list.Children.Add(emptyHint);

            var body = new StackPanel();
            body.Children.Add(bar);
            body.Children.Add(_status);
            body.Children.Add(listScroll);
            card.Child = body;
            stack.Children.Add(card);

            Ui.BoxOf(_filterInput).TextChanged += delegate { Render(); };
        }

        public override void OnShown()
        {
            _serial = First();
        }

        static string First()
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

        async void LoadApps()
        {
            if (string.IsNullOrEmpty(_serial))
            {
                _serial = First();
            }
            if (string.IsNullOrEmpty(_serial))
            {
                _win.ShowToast("没有已连接的设备");
                return;
            }
            _status.Text = "读取中…";
            string serial = _serial;
            bool onlyThird = _allCheck.IsChecked == true;
            List<string> list = null;
            await Task.Run(delegate { list = Adb.Packages(serial, !onlyThird); });
            _packages = list ?? new List<string>();
            Render();
        }

        void Render()
        {
            _list.Children.Clear();
            string filter = Ui.BoxOf(_filterInput).Text.Trim().ToLowerInvariant();
            int shown = 0;
            foreach (string pkg in _packages)
            {
                if (filter.Length > 0 && pkg.IndexOf(filter, StringComparison.OrdinalIgnoreCase) < 0)
                {
                    continue;
                }
                shown++;
                string p = pkg;
                var row = new Grid();
                row.ColumnDefinitions.Add(new ColumnDefinition());
                row.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
                row.Children.Add(T.Text(pkg, 13, T.Ink2));

                var actions = new StackPanel { Orientation = Orientation.Horizontal };
                var freeze = Ui.SmallButton("冻结", delegate { Act(p, "freeze"); });
                var unfreeze = Ui.SmallButton("解冻", delegate { Act(p, "unfreeze"); });
                unfreeze.Margin = new Thickness(6, 0, 0, 0);
                var clear = Ui.SmallButton("清数据", delegate { Act(p, "clear"); });
                clear.Margin = new Thickness(6, 0, 0, 0);
                var extract = Ui.SmallButton("提取", delegate { Act(p, "extract"); });
                extract.Margin = new Thickness(6, 0, 0, 0);
                var uninstall = Ui.SmallButton("卸载", delegate { Act(p, "uninstall"); });
                uninstall.Margin = new Thickness(6, 0, 0, 0);
                actions.Children.Add(freeze);
                actions.Children.Add(unfreeze);
                actions.Children.Add(clear);
                actions.Children.Add(extract);
                actions.Children.Add(uninstall);
                Grid.SetColumn(actions, 1);
                row.Children.Add(actions);

                _list.Children.Add(new Border
                {
                    Padding = new Thickness(2, 7, 2, 7),
                    BorderBrush = new SolidColorBrush(Color.FromArgb(14, 0, 0, 0)),
                    BorderThickness = new Thickness(0, 0, 0, 1),
                    Child = row,
                });
            }
            _status.Text = shown + " 个应用";
            if (shown == 0 && Adb.LastPackagesRaw.Length > 0)
            {
                string detail = Adb.LastPackagesRaw.Replace("\r", "").Replace("\n", " ");
                if (detail.Length > 90) { detail = detail.Substring(0, 90) + "…"; }
                _status.Text += "（pm 返回：" + detail + "）";
            }
            else if (Adb.LastPackagesRaw.StartsWith("第三方查询为空"))
            {
                _status.Text += "（已回退到全部应用）";
            }
        }

        void InstallApk()
        {
            if (_serial.Length == 0) { _win.ShowToast("没有已连接的设备"); return; }
            var dlg = new Microsoft.Win32.OpenFileDialog { Filter = "APK (*.apk)|*.apk" };
            if (dlg.ShowDialog() != true) { return; }
            string serial = _serial;
            string apk = dlg.FileName;
            _win.ShowToast("安装中…");
            Task.Run(delegate
            {
                bool ok = Adb.InstallApk(serial, apk);
                Dispatcher.Invoke(new Action(delegate
                {
                    _win.ShowToast(ok ? "安装成功" : "安装失败", !ok);
                    if (ok) { LoadApps(); }
                }));
            });
        }

        async void Act(string pkg, string action)
        {
            if (action == "uninstall" && MessageBox.Show("卸载 " + pkg + "？", "卸载应用",
                MessageBoxButton.OKCancel, MessageBoxImage.Warning) != MessageBoxResult.OK)
            {
                return;
            }
            if (action == "clear" && MessageBox.Show("清除 " + pkg + " 的全部数据？", "清除数据",
                MessageBoxButton.OKCancel, MessageBoxImage.Warning) != MessageBoxResult.OK)
            {
                return;
            }
            string serial = _serial;
            if (action == "extract")
            {
                string dir = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "shots", "apk");
                bool ok = await Task.Run(delegate { return Adb.ExtractApk(serial, pkg, dir); });
                _win.ShowToast(ok ? "已提取到 shots\\apk\\" + pkg + ".apk" : "提取失败（系统应用可能没有权限）", !ok);
                return;
            }
            await Task.Run(delegate { Adb.AppAction(serial, pkg, action); });
            _win.ShowToast("已执行：" + action + " " + pkg);
        }
    }

    /* ======================= 设置 ======================= */
    class SettingsPage : PageBase
    {
        readonly MainWindow _win;

        public SettingsPage(MainWindow win)
        {
            _win = win;
            Title = "设置";
            Background = Brushes.Transparent;

            var scroll = Ui.PageScroll();
            Children.Add(scroll);
            var stack = new StackPanel();
            scroll.Content = stack;
            stack.Children.Add(Ui.Header("设置", "运行环境与关于。"));

            var card = Ui.Card("#F7F5FD");
            card.Padding = new Thickness(22);
            card.Margin = new Thickness(0, 0, 0, 15);
            var body = new StackPanel();
            body.Children.Add(T.Text("运行环境", 15, T.Ink, FontWeights.SemiBold));
            body.Children.Add(Row("adb 路径", Adb.Path));
            body.Children.Add(Row("截图 / 录屏", Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "shots")));
            body.Children.Add(Row("分区备份", Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "backups")));
            var openShots = T.Button("打开截图目录", false, delegate { OpenFolder("shots"); });
            openShots.Margin = new Thickness(0, 14, 0, 0);
            openShots.HorizontalAlignment = HorizontalAlignment.Left;
            body.Children.Add(openShots);
            card.Child = body;
            stack.Children.Add(card);

            var about = Ui.Card("#F3F8FE");
            about.Padding = new Thickness(22);
            var ab = new StackPanel();
            ab.Children.Add(T.Text("关于 A梦工具箱", 15, T.Ink, FontWeights.SemiBold));
            ab.Children.Add(Row("版本", "v0.5.1"));
            ab.Children.Add(Row("作者 QQ", "17513499"));
            ab.Children.Add(Row("邮箱", "jinkaizhe2@gmail.com"));

            var ossTitle = T.Text("使用的开源项目", 13, T.Ink, FontWeights.SemiBold);
            ossTitle.Margin = new Thickness(0, 16, 0, 0);
            ab.Children.Add(ossTitle);
            var oss = T.Text(
                "scrcpy 5.0.1 · Apache-2.0 · 投屏\n"
                + "Android SDK Platform Tools（adb / fastboot）· Apache-2.0 · 设备通信\n"
                + ".NET Framework / WPF · MIT · 桌面界面与运行环境\n"
                + "NSIS 3.10 · zlib/libpng · 安装程序",
                12.5, T.Muted);
            oss.TextWrapping = TextWrapping.Wrap;
            oss.Margin = new Thickness(0, 6, 0, 0);
            ab.Children.Add(oss);
            about.Child = ab;
            stack.Children.Add(about);
        }

        static FrameworkElement Row(string key, string value)
        {
            var g = new Grid { Margin = new Thickness(0, 10, 0, 0) };
            g.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(120) });
            g.ColumnDefinitions.Add(new ColumnDefinition());
            g.Children.Add(T.Text(key, 12.5, T.Muted));
            var v = T.Text(value, 12.5, T.Ink2);
            Grid.SetColumn(v, 1);
            g.Children.Add(v);
            return g;
        }

        void OpenFolder(string name)
        {
            try
            {
                string path = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, name);
                Directory.CreateDirectory(path);
                Process.Start(new ProcessStartInfo(path) { UseShellExecute = true });
            }
            catch (Exception ex)
            {
                _win.ShowToast("打不开目录：" + ex.Message);
            }
        }
    }
}
