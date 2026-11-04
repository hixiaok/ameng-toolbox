using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Ellipse = System.Windows.Shapes.Ellipse;

namespace Iris
{
    class DashboardPage : PageBase
    {
        readonly MainWindow _win;

        DeviceInfo _info;
        string _serial = "";
        bool _busy;

        TextBlock _deviceTitle;
        TextBlock _deviceStatus;
        TextBlock _deviceSerial;
        Ellipse _statusDot;

        Ring _batRing;
        Ring _storRing;
        Ring _memRing;
        TextBlock _batSub;
        TextBlock _storSub;
        TextBlock _memSub;

        TextBlock _brand;
        TextBlock _model;
        TextBlock _cpu;
        TextBlock _res;
        TextBlock _dpi;
        TextBlock _storageType;
        TextBlock _health;
        TextBlock _capacity;
        TextBlock _android;
        TextBlock _sdk;
        TextBlock _kernel;
        TextBlock _build;
        TextBlock _patch;
        TextBlock _buildDate;
        TextBlock _baseband;
        TextBlock _fingerprint;
        TextBlock _abiInfo;
        TextBlock _cores;
        TextBlock _unlocked;
        TextBlock _batteryInfo;

        SelectBox _deviceSelect;
        SelectBox _rebootSelect;
        readonly List<string> _serials = new List<string>();

        public DashboardPage(MainWindow win)
        {
            _win = win;
            Title = "仪表盘";
            Background = Brushes.Transparent;

            var scroll = new ScrollViewer
            {
                VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
                HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled,
                Padding = new Thickness(22, 14, 22, 16),
            };
            Children.Add(scroll);
            var stack = new StackPanel();
            scroll.Content = stack;

            var banner = CardGrad("#FBFDFF", "#F1F8FE");
            banner.Height = 104;
            banner.Padding = new Thickness(19);
            banner.Margin = new Thickness(0, 0, 0, 14);

            var bg = Layout.Columns(0, 0, 0);
            bg.ColumnDefinitions[0].Width = new GridLength(76);
            bg.ColumnDefinitions[2].Width = GridLength.Auto;
            banner.Child = bg;

            var iconBox = new Border
            {
                Width = 62,
                Height = 62,
                CornerRadius = new CornerRadius(16),
                Background = new SolidColorBrush(Color.FromArgb(255, 46, 50, 56)),
                VerticalAlignment = VerticalAlignment.Center,
                Child = T.Icon("\uE8EA", 30, Colors.White),
            };
            bg.Children.Add(iconBox);

            var texts = new StackPanel { VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(18, 0, 0, 0) };
            _deviceTitle = T.Text("未连接设备", 25, T.Ink, FontWeights.SemiBold);
            texts.Children.Add(_deviceTitle);

            var statusRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 4, 0, 0) };
            _statusDot = new Ellipse { Width = 8, Height = 8, Fill = new SolidColorBrush(T.Dim), VerticalAlignment = VerticalAlignment.Center };
            statusRow.Children.Add(_statusDot);
            _deviceStatus = T.Text("未连接", 13, T.Muted);
            _deviceStatus.Margin = new Thickness(7, 0, 0, 0);
            statusRow.Children.Add(_deviceStatus);
            texts.Children.Add(statusRow);

            _deviceSerial = T.Text("序列号：—", 11.5, T.Dim);
            _deviceSerial.Margin = new Thickness(0, 3, 0, 0);
            texts.Children.Add(_deviceSerial);
            Grid.SetColumn(texts, 1);
            bg.Children.Add(texts);

            var bannerRight = new StackPanel { Orientation = Orientation.Horizontal, VerticalAlignment = VerticalAlignment.Center };
            var driver = T.Button("打开设备管理器", false, delegate { OpenDeviceManager(); });
            driver.Margin = new Thickness(0, 0, 10, 0);
            bannerRight.Children.Add(driver);
            var refresh = T.Button("刷新设备", true, delegate { RefreshAsync(); });
            bannerRight.Children.Add(refresh);
            Grid.SetColumn(bannerRight, 2);
            bg.Children.Add(bannerRight);

            stack.Children.Add(banner);

            var stats = Layout.Columns(0, 0, 0);
            stats.Margin = new Thickness(0, 0, 0, 14);

            var batCard = StatCard("\uE859", "电池电量", "#F1F7FE", "#E7F1FC", out _batRing, out _batSub);
            batCard.Margin = new Thickness(0, 0, 14, 0);
            stats.Children.Add(batCard);
            Grid.SetColumn(batCard, 0);

            var storCard = StatCard("\uE7B8", "存储空间", "#F0F9F3", "#E5F5EC", out _storRing, out _storSub);
            storCard.Margin = new Thickness(0, 0, 14, 0);
            Grid.SetColumn(storCard, 1);
            stats.Children.Add(storCard);

            var memCard = StatCard("\uE950", "运行内存", "#FDF3F9", "#F9E8F2", out _memRing, out _memSub);
            Grid.SetColumn(memCard, 2);
            stats.Children.Add(memCard);

            stack.Children.Add(stats);

            var bottom = Layout.Columns(0, 0);
            bottom.ColumnDefinitions[0].Width = new GridLength(1.65, GridUnitType.Star);
            bottom.ColumnDefinitions[1].Width = new GridLength(1, GridUnitType.Star);
            stack.Children.Add(bottom);

            var hw = CardGrad("#F7F5FD", "#F1EEFA");
            hw.Padding = new Thickness(19);
            hw.Margin = new Thickness(0, 0, 14, 0);
            var hwStack = new StackPanel();
            hwStack.Children.Add(SectionTitle("\uE950", "硬件参数"));

            var hwGrid = Layout.Columns(0, 0);
            for (int i = 0; i < 4; i++)
            {
                hwGrid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            }
            hwGrid.Margin = new Thickness(0, 10, 0, 0);
            AddPair(hwGrid, 0, 0, "品牌", out _brand);
            AddPair(hwGrid, 0, 1, "型号", out _model);
            AddPair(hwGrid, 1, 0, "CPU 处理器", out _cpu);
            AddPair(hwGrid, 1, 1, "屏幕分辨率", out _res);
            AddPair(hwGrid, 2, 0, "屏幕密度（DPI）", out _dpi);
            AddPair(hwGrid, 2, 1, "存储类型", out _storageType);
            AddPair(hwGrid, 3, 0, "电池健康度", out _health);
            AddPair(hwGrid, 3, 1, "电池容量", out _capacity);
            hwStack.Children.Add(hwGrid);

            var divider = new Border
            {
                Height = 1,
                Background = new SolidColorBrush(Color.FromArgb(24, 0, 0, 0)),
                Margin = new Thickness(0, 2, 0, 12),
            };
            hwStack.Children.Add(divider);
            hwStack.Children.Add(SectionTitle("\uE7F9", "系统信息"));

            var sysGrid = Layout.Columns(0, 0);
            for (int i = 0; i < 2; i++)
            {
                sysGrid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            }
            sysGrid.Margin = new Thickness(0, 10, 0, 0);
            AddPair(sysGrid, 0, 0, "Android 版本", out _android);
            AddPair(sysGrid, 0, 1, "SDK 版本", out _sdk);
            AddPair(sysGrid, 1, 0, "内核版本", out _kernel);
            AddPair(sysGrid, 1, 1, "详细版本号", out _build);
            hwStack.Children.Add(sysGrid);

            hw.Child = hwStack;
            Grid.SetColumn(hw, 0);
            bottom.Children.Add(hw);

            var right = new StackPanel();
            right.Children.Add(BuildSelectCard());
            right.Children.Add(BuildRebootCard());
            right.Children.Add(BuildToolsCard());
            Grid.SetColumn(right, 1);
            bottom.Children.Add(right);

            /* ---------- 详细参数 ---------- */
            var detail = CardGrad("#F7F5FD", "#F1EEFA");
            detail.Padding = new Thickness(18);
            detail.Margin = new Thickness(0, 14, 0, 0);
            var detailStack = new StackPanel();
            detailStack.Children.Add(SectionTitle("\uE7F1", "详细参数"));
            var dg = Layout.Columns(0, 0);
            for (int i = 0; i < 5; i++)
            {
                dg.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            }
            dg.Margin = new Thickness(0, 10, 0, 0);
            AddPair(dg, 0, 0, "安全补丁", out _patch);
            AddPair(dg, 0, 1, "构建日期", out _buildDate);
            AddPair(dg, 1, 0, "基带版本", out _baseband);
            AddPair(dg, 1, 1, "CPU 核心", out _cores);
            AddPair(dg, 2, 0, "电池温度", out _batteryInfo);
            AddPair(dg, 2, 1, "解锁状态", out _unlocked);
            AddPair(dg, 3, 0, "架构", out _abiInfo);
            var fpCell = new StackPanel { Margin = new Thickness(0, 0, 0, 4) };
            fpCell.Children.Add(T.Text("构建指纹", 12, T.Muted));
            _fingerprint = T.Text("—", 11.5, T.Ink2);
            _fingerprint.Margin = new Thickness(0, 2, 0, 0);
            _fingerprint.TextTrimming = TextTrimming.CharacterEllipsis;
            fpCell.Children.Add(_fingerprint);
            Grid.SetRow(fpCell, 4);
            Grid.SetColumnSpan(fpCell, 2);
            dg.Children.Add(fpCell);
            detailStack.Children.Add(dg);
            detail.Child = detailStack;
            stack.Children.Add(detail);

            SetDisconnected();
        }

        static Border CardGrad(string a, string b)
        {
            var bg = new LinearGradientBrush
            {
                StartPoint = new Point(0, 0),
                EndPoint = new Point(1, 1),
            };
            bg.GradientStops.Add(new GradientStop(T.C(a), 0));
            bg.GradientStops.Add(new GradientStop(T.C(b), 1));
            return new Border
            {
                CornerRadius = new CornerRadius(14),
                Background = bg,
                BorderBrush = new SolidColorBrush(Color.FromArgb(150, 255, 255, 255)),
                BorderThickness = new Thickness(1),
            };
        }

        static FrameworkElement SectionTitle(string glyph, string text)
        {
            var row = new StackPanel { Orientation = Orientation.Horizontal };
            row.Children.Add(T.Icon(glyph, 15, T.Muted));
            var t = T.Text(text, 15, T.Ink, FontWeights.SemiBold);
            t.Margin = new Thickness(8, 0, 0, 0);
            row.Children.Add(t);
            return row;
        }

        Border StatCard(string glyph, string title, string c1, string c2, out Ring ring, out TextBlock sub)
        {
            var card = CardGrad(c1, c2);
            card.Height = 196;
            card.Padding = new Thickness(16, 14, 16, 12);

            var g = new Grid();
            g.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            g.RowDefinitions.Add(new RowDefinition());
            g.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });

            var head = new StackPanel { Orientation = Orientation.Horizontal };
            head.Children.Add(T.Icon(glyph, 15, T.Muted));
            var titleText = T.Text(title, 15, T.Ink, FontWeights.SemiBold);
            titleText.Margin = new Thickness(8, 0, 0, 0);
            head.Children.Add(titleText);
            g.Children.Add(head);

            ring = new Ring
            {
                Width = 120,
                Height = 120,
                HorizontalAlignment = HorizontalAlignment.Center,
                VerticalAlignment = VerticalAlignment.Center,
            };
            Grid.SetRow(ring, 1);
            g.Children.Add(ring);

            sub = T.Text("-", 12, T.Muted);
            sub.HorizontalAlignment = HorizontalAlignment.Center;
            Grid.SetRow(sub, 2);
            g.Children.Add(sub);

            card.Child = g;
            return card;
        }

        static void AddPair(Grid grid, int row, int col, string label, out TextBlock value)
        {
            var cell = new StackPanel { Margin = new Thickness(0, 0, 18, 10) };
            cell.Children.Add(T.Text(label, 12, T.Muted));
            value = T.Text("—", 15, T.Ink, FontWeights.SemiBold);
            value.Margin = new Thickness(0, 2, 0, 0);
            cell.Children.Add(value);
            Grid.SetRow(cell, row);
            Grid.SetColumn(cell, col);
            grid.Children.Add(cell);
        }

        FrameworkElement BuildSelectCard()
        {
            var card = CardGrad("#FDF1F7", "#FBE7F1");
            card.Padding = new Thickness(17);
            card.Margin = new Thickness(0, 0, 0, 10);

            var stack = new StackPanel();
            stack.Children.Add(SectionTitle("\uE8EA", "选择设备"));

            _deviceSelect = new SelectBox(38) { Margin = new Thickness(0, 12, 0, 8) };
            _deviceSelect.SetItems(new[] { "未检测到设备" }, 0);
            _deviceSelect.Changed += delegate
            {
                int i = _deviceSelect.SelectedIndex;
                if (i >= 0 && i < _serials.Count)
                {
                    _serial = _serials[i];
                    RefreshInfo();
                }
            };
            stack.Children.Add(_deviceSelect);

            var btn = T.Button("刷新设备", true, delegate { RefreshAsync(); });
            btn.HorizontalAlignment = HorizontalAlignment.Stretch;
            stack.Children.Add(btn);

            card.Child = stack;
            return card;
        }

        FrameworkElement BuildRebootCard()
        {
            var card = CardGrad("#F3F8FE", "#E9F2FD");
            card.Padding = new Thickness(17);
            card.Margin = new Thickness(0, 0, 0, 10);

            var stack = new StackPanel();
            stack.Children.Add(SectionTitle("\uE7E8", "重启设备"));

            _rebootSelect = new SelectBox(38) { Margin = new Thickness(0, 12, 0, 8) };
            _rebootSelect.SetItems(new[] { "重启系统", "重启到 Recovery", "重启到 Bootloader", "重启到 Fastbootd", "关机" }, 0);
            stack.Children.Add(_rebootSelect);

            var btn = T.Button("执行重启", true, delegate { DoReboot(); });
            btn.HorizontalAlignment = HorizontalAlignment.Stretch;
            stack.Children.Add(btn);

            card.Child = stack;
            return card;
        }

        FrameworkElement BuildToolsCard()
        {
            var card = CardGrad("#F6F4FC", "#EFEBFA");
            card.Padding = new Thickness(17);

            var stack = new StackPanel();
            stack.Children.Add(SectionTitle("\uE90F", "常用工具"));

            var wrap = new WrapPanel { Margin = new Thickness(0, 10, 0, 0) };
            wrap.Children.Add(ToolButton("截图", delegate { Screenshot(); }));
            wrap.Children.Add(ToolButton("录屏 10s", delegate { Record(); }));
            wrap.Children.Add(ToolButton("抓日志", delegate { Logcat(); }));
            wrap.Children.Add(ToolButton("无线调试", delegate { Wireless(); }));
            stack.Children.Add(wrap);

            card.Child = stack;
            return card;
        }

        Border ToolButton(string text, RoutedEventHandler click)
        {
            var b = T.Button(text, false, click);
            b.Height = 32;
            b.Padding = new Thickness(12, 0, 12, 0);
            b.Margin = new Thickness(0, 0, 8, 8);
            return b;
        }

        public override void OnTick()
        {
            if (Visibility == Visibility.Visible)
            {
                RefreshAsync();
            }
        }

        public async void RefreshAsync()
        {
            if (_busy)
            {
                return;
            }
            if (!Adb.Available)
            {
                SetDisconnected();
                _deviceTitle.Text = "未找到 adb";
                _deviceStatus.Text = "把 platform-tools 放到程序目录，或设置 IRIS_ADB";
                return;
            }
            _busy = true;
            try
            {
                List<DeviceInfo> infos = new List<DeviceInfo>();
                List<string[]> devices = null;
                string error = null;
                await Task.Run(delegate
                {
                    try
                    {
                        devices = Adb.Devices();
                        foreach (string[] d in devices)
                        {
                            if (d[1] == "device")
                            {
                                infos.Add(Adb.ReadInfo(d[0]));
                            }
                        }
                    }
                    catch (Exception ex)
                    {
                        error = ex.Message;
                    }
                });

                if (error != null)
                {
                    SetDisconnected();
                    return;
                }

                _serials.Clear();
                var labels = new List<string>();
                foreach (DeviceInfo d in infos)
                {
                    _serials.Add(d.Serial);
                    labels.Add((string.IsNullOrEmpty(d.Model) ? "Android 设备" : d.Model) + "  ·  " + d.Serial);
                }

                if (infos.Count == 0)
                {
                    _deviceSelect.SetItems(new[] { devices != null && devices.Count > 0 ? "设备未授权 / 离线" : "未检测到设备" }, 0);
                    SetDisconnected();
                    return;
                }

                int keep = _serials.IndexOf(_serial);
                if (keep < 0)
                {
                    keep = 0;
                    _serial = _serials[0];
                }
                _deviceSelect.SetItems(labels, keep);
                _info = infos[keep];
                ShowInfo(_info);
            }
            finally
            {
                _busy = false;
            }
        }

        void RefreshInfo()
        {
            if (string.IsNullOrEmpty(_serial))
            {
                return;
            }
            string serial = _serial;
            Task.Run(delegate
            {
                try
                {
                    DeviceInfo info = Adb.ReadInfo(serial);
                    Dispatcher.Invoke(new Action(delegate { ShowInfo(info); }));
                }
                catch
                {
                }
            });
        }

        void SetDisconnected()
        {
            _deviceTitle.Text = "未连接设备";
            _statusDot.Fill = new SolidColorBrush(T.Dim);
            _deviceStatus.Text = "未连接";
            _deviceSerial.Text = "序列号：—";

            _batRing.Value = 0;
            _batRing.CenterText = "0%";
            _batSub.Text = "健康度：—";
            _storRing.Value = 0;
            _storRing.CenterText = "0%";
            _storSub.Text = "—";
            _memRing.Value = 0;
            _memRing.CenterText = "0%";
            _memSub.Text = "—";

            _brand.Text = "—";
            _model.Text = "—";
            _cpu.Text = "—";
            _res.Text = "—";
            _dpi.Text = "—";
            _storageType.Text = "—";
            _health.Text = "—";
            _capacity.Text = "—";
            _android.Text = "—";
            _sdk.Text = "—";
            _kernel.Text = "—";
            _build.Text = "—";
            _patch.Text = "—";
            _buildDate.Text = "—";
            _baseband.Text = "—";
            _fingerprint.Text = "—";
            _abiInfo.Text = "—";
            _cores.Text = "—";
            _unlocked.Text = "—";
            _batteryInfo.Text = "—";
        }

        void ShowInfo(DeviceInfo d)
        {
            _info = d;
            _deviceTitle.Text = (d.Brand + " " + d.Model).Trim();
            _statusDot.Fill = new SolidColorBrush(T.Ok);
            _deviceStatus.Text = "已连接：" + (d.Root ? "ROOT" : "系统");
            _deviceSerial.Text = "序列号：" + d.Serial;

            _batRing.Value = d.BatteryLevel;
            _batRing.CenterText = d.BatteryLevel + "%";
            _batSub.Text = "健康度：" + d.BatteryHealth;

            _storRing.Value = d.StoragePercent;
            _storRing.CenterText = d.StoragePercent + "%";
            _storSub.Text = d.StorageText;

            _memRing.Value = d.MemoryPercent;
            _memRing.CenterText = d.MemoryPercent + "%";
            _memSub.Text = d.MemoryText;

            _brand.Text = d.Brand;
            _model.Text = d.Model;
            _cpu.Text = d.Cpu;
            _res.Text = d.Resolution;
            _dpi.Text = d.Density;
            _storageType.Text = d.StorageType;
            _health.Text = d.BatteryHealth;
            _capacity.Text = d.BatteryCapacity;
            _android.Text = d.Android;
            _sdk.Text = d.Sdk;
            _kernel.Text = d.Kernel;
            _build.Text = d.BuildId;
            _patch.Text = string.IsNullOrEmpty(d.SecurityPatch) ? "—" : d.SecurityPatch;
            _buildDate.Text = string.IsNullOrEmpty(d.BuildDate) ? "—" : d.BuildDate;
            _baseband.Text = string.IsNullOrEmpty(d.Baseband) ? "—" : d.Baseband;
            _fingerprint.Text = string.IsNullOrEmpty(d.Fingerprint) ? "—" : d.Fingerprint;
            _abiInfo.Text = string.IsNullOrEmpty(d.Abi) ? "—" : d.Abi;
            _cores.Text = string.IsNullOrEmpty(d.Cores) ? "—" : d.Cores;
            _unlocked.Text = string.IsNullOrEmpty(d.Unlocked) ? "—" : d.Unlocked;
            _batteryInfo.Text = d.BatteryTemp > 0
                ? d.BatteryTemp.ToString("0.0") + "°C" + (d.BatteryMv > 0 ? " / " + d.BatteryMv + " mV" : "")
                : "—";
        }

        public void SetDemo()
        {
            var d = new DeviceInfo
            {
                Serial = "XM2026A7U",
                Brand = "Xiaomi",
                Model = "Pad 7 Ultra",
                Codename = "uke",
                Android = "16",
                Sdk = "36",
                Cpu = "Xiaomi XRING O1",
                Kernel = "6.6.30-android15-8",
                BuildId = "BP4A.260105.001",
                Resolution = "2880x1800",
                Density = "320",
                BatteryLevel = 86,
                BatteryHealth = "良好",
                BatteryCapacity = "12000 mAh",
                StorageTotal = 512L * 1024 * 1024 * 1024,
                StorageUsed = 213L * 1024 * 1024 * 1024,
                MemTotal = 16L * 1024 * 1024 * 1024,
                MemAvailable = 7L * 1024 * 1024 * 1024,
                Root = true,
                Manager = "Magisk 27.0",
            };
            _serials.Clear();
            _serials.Add(d.Serial);
            _deviceSelect.SetItems(new[] { d.Model + "  ·  " + d.Serial }, 0);
            ShowInfo(d);
        }

        void DoReboot()
        {
            if (string.IsNullOrEmpty(_serial))
            {
                _win.ShowToast("没有已连接的设备");
                return;
            }
            string serial = _serial;
            string target = "system";
            switch (_rebootSelect.SelectedIndex)
            {
                case 1: target = "recovery"; break;
                case 2: target = "bootloader"; break;
                case 3: target = "fastboot"; break;
                case 4: target = "shutdown"; break;
            }
            if (MessageBox.Show("确认对 " + serial + " 执行：" + _rebootSelect.SelectedItem + " ?", "重启设备",
                MessageBoxButton.OKCancel, MessageBoxImage.Question) != MessageBoxResult.OK)
            {
                return;
            }
            Task.Run(delegate
            {
                Adb.Reboot(serial, target);
                Dispatcher.Invoke(new Action(delegate { _win.ShowToast("指令已发送"); }));
            });
        }

        void Screenshot()
        {
            if (string.IsNullOrEmpty(_serial))
            {
                _win.ShowToast("没有已连接的设备");
                return;
            }
            string serial = _serial;
            Task.Run(delegate
            {
                try
                {
                    string dir = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "shots");
                    Directory.CreateDirectory(dir);
                    string file = Path.Combine(dir, "shot-" + DateTime.Now.ToString("yyyyMMdd-HHmmss") + ".png");
                    bool ok = Adb.Screenshot(serial, file);
                    Dispatcher.Invoke(new Action(delegate
                    {
                        _win.ShowToast(ok ? "截图已保存：shots\\" + Path.GetFileName(file) : "截图失败");
                    }));
                }
                catch (Exception ex)
                {
                    Dispatcher.Invoke(new Action(delegate { _win.ShowToast("截图失败：" + ex.Message); }));
                }
            });
        }

        void Record()
        {
            if (string.IsNullOrEmpty(_serial))
            {
                _win.ShowToast("没有已连接的设备");
                return;
            }
            string serial = _serial;
            _win.ShowToast("开始录屏 10 秒…");
            Task.Run(delegate
            {
                string remote = "/sdcard/iris-rec.mp4";
                Adb.Shell(serial, "screenrecord --time-limit 10 " + remote, 30000);
                string dir = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "shots");
                Directory.CreateDirectory(dir);
                string local = Path.Combine(dir, "rec-" + DateTime.Now.ToString("yyyyMMdd-HHmmss") + ".mp4");
                Adb.Run("-s " + serial + " pull " + remote + " \"" + local + "\"", 60000);
                Adb.Shell(serial, "rm -f " + remote, 8000);
                Dispatcher.Invoke(new Action(delegate { _win.ShowToast("录屏已保存到 shots 目录"); }));
            });
        }

        void Logcat()
        {
            if (string.IsNullOrEmpty(_serial))
            {
                _win.ShowToast("没有已连接的设备");
                return;
            }
            string serial = _serial;
            Task.Run(delegate
            {
                AdbResult r = Adb.Logcat(serial);
                string dir = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "shots");
                Directory.CreateDirectory(dir);
                string file = Path.Combine(dir, "logcat-" + DateTime.Now.ToString("yyyyMMdd-HHmmss") + ".txt");
                File.WriteAllText(file, r.Out);
                Dispatcher.Invoke(new Action(delegate { _win.ShowToast("日志已保存：shots\\" + Path.GetFileName(file)); }));
            });
        }

        void Wireless()
        {
            if (string.IsNullOrEmpty(_serial))
            {
                _win.ShowToast("没有已连接的设备");
                return;
            }
            string serial = _serial;
            Task.Run(delegate
            {
                bool ok = Adb.Tcpip(serial, 5555);
                Dispatcher.Invoke(new Action(delegate
                {
                    _win.ShowToast(ok ? "已开启无线调试端口 5555" : "开启失败，确认设备在线");
                }));
            });
        }

        void OpenDeviceManager()
        {
            try
            {
                Process.Start(new ProcessStartInfo("devmgmt.msc") { UseShellExecute = true });
            }
            catch (Exception ex)
            {
                _win.ShowToast("无法打开设备管理器：" + ex.Message);
            }
        }
    }
}
