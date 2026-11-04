using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Media.Animation;
using System.Windows.Media.Effects;
using System.Windows.Media.Imaging;
using System.Windows.Shapes;
using System.Windows.Shell;
using Forms = System.Windows.Forms;
using System.Windows.Threading;

namespace Iris
{
    abstract class PageBase : Grid
    {
        public string Title = "";
        public virtual void OnShown() { }
        public virtual void OnTick() { }
    }

    class MainWindow : Window
    {
        readonly Grid _root;
        readonly Grid _body;
        readonly Grid _content;
        readonly Border _nav;
        readonly StackPanel _navItems;
        readonly List<TextBlock> _sectionLabels = new List<TextBlock>();
        readonly TextBlock _titleText;
        readonly TextBlock _versionText;
        bool _collapsed = true;
        readonly Border _toast;
        readonly TextBlock _toastText;
        readonly DispatcherTimer _timer;

        Canvas _blobs;
        readonly System.Collections.Generic.List<Blob> _blobDefs = new System.Collections.Generic.List<Blob>();
        NavItem _settingsItem;
        Border _maxButton;
        Forms.NotifyIcon _tray;
        bool _exiting;
        bool _trayTipShown;
        bool _firstPage = true;
        bool _resizingContent;
        bool _inSizeMove;
        readonly Dictionary<Border, Effect> _shadows = new Dictionary<Border, Effect>();
        DispatcherTimer _shadowTimer;
        ScrollViewer _scrollSv;
        DispatcherTimer _scrollTimer;

        readonly DashboardPage _dashboard;
        readonly QuickPage _quick;
        readonly FlashPage _flash;
        readonly FastbootPage _fastboot;
        readonly RootPage _rootPage;
        readonly CastPage _cast;
        readonly BasebandPage _baseband;
        readonly ModulesPage _modules;
        readonly AppsPage _apps;
        readonly TerminalPage _terminal;
        readonly SettingsPage _settings;

        public MainWindow(bool demo)
        {
            Title = "A梦工具箱";
            Width = 1360;
            Height = 860;
            MinWidth = 900;
            MinHeight = 600;
            UseLayoutRounding = true;
            SnapsToDevicePixels = true;
            SizeChanged += delegate
            {
                if (WindowState == WindowState.Normal)
                {
                    SuppressShadows();
                }
            };
            PreviewMouseWheel += delegate (object s, MouseWheelEventArgs e)
            {
                CacheScrollForWheel(e.OriginalSource as DependencyObject);
            };
            WindowStartupLocation = WindowStartupLocation.CenterScreen;
            WindowStyle = WindowStyle.None;
            FontFamily = T.Font;
            Background = new LinearGradientBrush(
                (Color)ColorConverter.ConvertFromString("#CDE4FA"),
                (Color)ColorConverter.ConvertFromString("#F7D8E7"), new Point(0, 0), new Point(1, 1));

            WindowChrome.SetWindowChrome(this, new WindowChrome
            {
                CaptionHeight = 0,
                ResizeBorderThickness = new Thickness(6),
                GlassFrameThickness = new Thickness(0),
                CornerRadius = new CornerRadius(0),
                UseAeroCaptionButtons = false,
            });

            _root = new Grid();
            Content = _root;
            AddBlobs();

            var rows = Layout.Rows(48, 0);
            _root.Children.Add(rows);

            /* ---------- 标题栏 ---------- */
            var titlebar = new Grid { Background = new SolidColorBrush(Color.FromArgb(30, 255, 255, 255)) };
            titlebar.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(56) });
            titlebar.ColumnDefinitions.Add(new ColumnDefinition());
            titlebar.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

            var menuIcon = T.Icon("\uE700", 14, T.Ink2);
            menuIcon.IsHitTestVisible = false;
            var menu = new Border
            {
                Width = 34,
                Height = 30,
                CornerRadius = new CornerRadius(6),
                Background = Brushes.Transparent,
                Cursor = Cursors.Hand,
                HorizontalAlignment = HorizontalAlignment.Center,
                VerticalAlignment = VerticalAlignment.Center,
                Tag = "caption",
                Child = menuIcon,
            };
            menu.MouseLeftButtonDown += delegate (object s, MouseButtonEventArgs e) { e.Handled = true; };
            menu.MouseEnter += delegate { menu.Background = T.B("#14000000"); };
            menu.MouseLeave += delegate { menu.Background = Brushes.Transparent; };
            menu.MouseLeftButtonUp += delegate { ToggleNav(); };
            titlebar.Children.Add(menu);

            var brand = new StackPanel { Orientation = Orientation.Horizontal, VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(6, 0, 0, 0) };
            var logo = new Border
            {
                Width = 22,
                Height = 22,
                CornerRadius = new CornerRadius(6),
                Background = new LinearGradientBrush(T.C("#3F8CFF"), T.C("#0F5FC4"), 45),
                Child = new TextBlock
                {
                    Text = "A",
                    Foreground = Brushes.White,
                    FontSize = 12,
                    FontWeight = FontWeights.Bold,
                    HorizontalAlignment = HorizontalAlignment.Center,
                    VerticalAlignment = VerticalAlignment.Center,
                    FontFamily = T.Font,
                },
            };
            brand.Children.Add(logo);
            try
            {
                string icoPath = System.IO.Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "iris.ico");
                if (System.IO.File.Exists(icoPath))
                {
                    var decoder = new IconBitmapDecoder(new Uri(icoPath), BitmapCreateOptions.None, BitmapCacheOption.OnLoad);
                    logo.Background = Brushes.Transparent;
                    logo.Child = new Image { Source = decoder.Frames[0], Stretch = Stretch.UniformToFill };
                }
            }
            catch
            {
            }
            _titleText = T.Text("A梦工具箱  -  仪表盘", 12.5, T.Ink2, FontWeights.SemiBold);
            _titleText.Margin = new Thickness(10, 0, 0, 0);
            brand.Children.Add(_titleText);
            Grid.SetColumn(brand, 1);
            titlebar.Children.Add(brand);

            var winBtns = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right, Margin = new Thickness(0, 0, 6, 0) };
            winBtns.Children.Add(WinButton("\uE921", false, delegate { MinimizeToTray(); }));
            _maxButton = WinButton("\uE922", false, delegate { ToggleMaximize(); });
            winBtns.Children.Add(_maxButton);
            winBtns.Children.Add(WinButton("\uE8BB", true, delegate { HideToTray(); }));
            Grid.SetColumn(winBtns, 2);
            titlebar.Children.Add(winBtns);
            ((FrameworkElement)winBtns.Children[0]).ToolTip = "最小化";
            ((FrameworkElement)winBtns.Children[1]).ToolTip = "最大化 / 还原（F11）";
            ((FrameworkElement)winBtns.Children[2]).ToolTip = "关闭";
            StateChanged += delegate { UpdateMaxGlyph(); UpdateChromeForState(); };

            PreviewKeyDown += delegate (object s, KeyEventArgs e)
            {
                if (e.Key == Key.F11)
                {
                    ToggleMaximize();
                    e.Handled = true;
                }
            };

            titlebar.MouseLeftButtonDown += delegate (object s, MouseButtonEventArgs e)
            {
                if (InCaptionControl(e.OriginalSource as DependencyObject))
                {
                    return;
                }
                if (e.ClickCount == 2)
                {
                    ToggleMaximize();
                }
                else if (e.ButtonState == MouseButtonState.Pressed)
                {
                    try
                    {
                        DragMove();
                    }
                    catch (InvalidOperationException)
                    {
                    }
                }
            };
            Grid.SetRow(titlebar, 0);
            rows.Children.Add(titlebar);

            /* ---------- 主体 ---------- */
            _body = new Grid();
            _body.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            _body.ColumnDefinitions.Add(new ColumnDefinition());
            Grid.SetRow(_body, 1);
            rows.Children.Add(_body);

            _nav = new Border
            {
                Width = 56,
                Background = new SolidColorBrush(Color.FromArgb(34, 255, 255, 255)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(16, 0, 0, 0)),
                BorderThickness = new Thickness(0, 0, 1, 0),
            };
            var navGrid = new Grid();
            navGrid.RowDefinitions.Add(new RowDefinition());
            navGrid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            _navItems = new StackPanel { Margin = new Thickness(0, 8, 0, 0) };
            navGrid.Children.Add(_navItems);

            _versionText = T.Text("v0.5.1", 10.5, T.Dim);
            _versionText.HorizontalAlignment = HorizontalAlignment.Center;
            _versionText.Margin = new Thickness(0, 4, 0, 0);
            var foot = new StackPanel { VerticalAlignment = VerticalAlignment.Bottom };
            _settingsItem = new NavItem("\uE713", "设置", "settings");
            _settingsItem.Activated += delegate { ShowPage("settings"); };
            foot.Children.Add(_settingsItem);
            foot.Children.Add(_versionText);
            foot.Margin = new Thickness(0, 0, 0, 8);
            Grid.SetRow(foot, 1);
            navGrid.Children.Add(foot);
            _nav.Child = navGrid;
            _body.Children.Add(_nav);

            _content = new Grid();
            Grid.SetColumn(_content, 1);
            _body.Children.Add(_content);

            /* ---------- 页面 ---------- */
            _dashboard = new DashboardPage(this);
            _quick = new QuickPage(this);
            _flash = new FlashPage(this);
            _fastboot = new FastbootPage(this);
            _rootPage = new RootPage(this);
            _cast = new CastPage(this);
            _baseband = new BasebandPage(this);
            _modules = new ModulesPage(this);
            _apps = new AppsPage(this);
            _terminal = new TerminalPage(this);
            _settings = new SettingsPage(this);

            AddPage(_dashboard);
            AddPage(_quick);
            AddPage(_flash);
            AddPage(_fastboot);
            AddPage(_rootPage);
            AddPage(_cast);
            AddPage(_baseband);
            AddPage(_modules);
            AddPage(_apps);
            AddPage(_terminal);
            AddPage(_settings);

            var dashItem = new NavItem("\uE80F", "仪表盘", "dashboard");
            var quickItem = new NavItem("\uE7F1", "快捷指令", "quick");
            var flashItem = new NavItem("\uE945", "刷机", "flash");
            var fbItem = new NavItem("\uE896", "Fastboot", "fastboot");
            var rootItem = new NavItem("\uE7E8", "ROOT", "root");
            var castItem = new NavItem("\uE8A1", "投屏", "cast");
            var bbItem = new NavItem("\uE8B7", "基带备份", "baseband");
            var modItem = new NavItem("\uE7B8", "模块", "modules");
            var appItem = new NavItem("\uE71D", "应用", "apps");
            var termItem = new NavItem("\uE7C3", "终端", "terminal");
            dashItem.Activated += delegate { ShowPage("dashboard"); };
            quickItem.Activated += delegate { ShowPage("quick"); };
            flashItem.Activated += delegate { ShowPage("flash"); };
            fbItem.Activated += delegate { ShowPage("fastboot"); };
            rootItem.Activated += delegate { ShowPage("root"); };
            castItem.Activated += delegate { ShowPage("cast"); };
            bbItem.Activated += delegate { ShowPage("baseband"); };
            modItem.Activated += delegate { ShowPage("modules"); };
            appItem.Activated += delegate { ShowPage("apps"); };
            termItem.Activated += delegate { ShowPage("terminal"); };
            _navItems.Children.Add(SectionLabel("设备"));
            _navItems.Children.Add(dashItem);
            _navItems.Children.Add(quickItem);
            _navItems.Children.Add(SectionLabel("刷写"));
            _navItems.Children.Add(flashItem);
            _navItems.Children.Add(fbItem);
            _navItems.Children.Add(rootItem);
            _navItems.Children.Add(bbItem);
            _navItems.Children.Add(SectionLabel("工具"));
            _navItems.Children.Add(castItem);
            _navItems.Children.Add(modItem);
            _navItems.Children.Add(appItem);
            _navItems.Children.Add(termItem);
            _navItems.Tag = new[] { dashItem, quickItem, flashItem, fbItem, rootItem, bbItem, castItem, modItem, appItem, termItem };

            // 启动时导航是收起状态：先把文字和版本号收起来，避免 56px 宽里被裁切
            foreach (UIElement el in _navItems.Children)
            {
                var nav = el as NavItem;
                if (nav != null)
                {
                    nav.SetCollapsed(true);
                }
            }
            _settingsItem.SetCollapsed(true);
            _versionText.Visibility = Visibility.Collapsed;

            /* ---------- toast ---------- */
            _toastText = T.Text("", 12.5, Colors.White);
            _toast = new Border
            {
                Background = new SolidColorBrush(Color.FromArgb(235, 32, 36, 42)),
                CornerRadius = new CornerRadius(8),
                Padding = new Thickness(16, 9, 16, 9),
                HorizontalAlignment = HorizontalAlignment.Center,
                VerticalAlignment = VerticalAlignment.Bottom,
                Margin = new Thickness(0, 0, 0, 26),
                Opacity = 0,
                IsHitTestVisible = false,
                Child = _toastText,
            };
            _root.Children.Add(_toast);

            ShowPage("dashboard");
            SetupTray();
            Application.Current.SessionEnding += delegate { _exiting = true; };

            _timer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(10) };
            _timer.Tick += delegate
            {
                PageBase p = CurrentPage();
                if (p != null)
                {
                    p.OnTick();
                }
            };
            _timer.Start();

            Loaded += delegate { _dashboard.RefreshAsync(); };
            if (demo)
            {
                _dashboard.SetDemo();
            }
        }

        void AddPage(PageBase p)
        {
            p.Visibility = Visibility.Collapsed;
            _content.Children.Add(p);
        }

        PageBase CurrentPage()
        {
            foreach (UIElement el in _content.Children)
            {
                var p = el as PageBase;
                if (p != null && p.Visibility == Visibility.Visible)
                {
                    return p;
                }
            }
            return null;
        }

        void ShowPage(string id)
        {
            PageBase target = null;
            switch (id)
            {
                case "dashboard": target = _dashboard; break;
                case "quick": target = _quick; break;
                case "flash": target = _flash; break;
                case "fastboot": target = _fastboot; break;
                case "root": target = _rootPage; break;
                case "cast": target = _cast; break;
                case "baseband": target = _baseband; break;
                case "modules": target = _modules; break;
                case "apps": target = _apps; break;
                case "terminal": target = _terminal; break;
                case "settings": target = _settings; break;
            }
            if (target == null)
            {
                return;
            }
            foreach (UIElement el in _content.Children)
            {
                if (el is PageBase)
                {
                    el.Visibility = el == target ? Visibility.Visible : Visibility.Collapsed;
                }
            }

            // 页面切换：淡入 + 轻微上移，避免生硬跳变
            var tt = target.RenderTransform as TranslateTransform;
            if (tt == null)
            {
                tt = new TranslateTransform();
                target.RenderTransform = tt;
            }
            target.Opacity = 0;
            tt.Y = 0;
            if (_firstPage)
            {
                _firstPage = false;
                target.Opacity = 1;
                tt.Y = 0;
            }
            else
            {
                var story = new Storyboard();
                var fade = new DoubleAnimation(0, 1, TimeSpan.FromMilliseconds(120))
                {
                    EasingFunction = new QuadraticEase { EasingMode = EasingMode.EaseOut },
                };
                Storyboard.SetTarget(fade, target);
                Storyboard.SetTargetProperty(fade, new PropertyPath("Opacity"));
                story.Children.Add(fade);
                story.Begin();
            }

            _titleText.Text = "A梦工具箱  -  " + target.Title;
            var items = _navItems.Tag as NavItem[];
            if (items != null)
            {
                foreach (NavItem item in items)
                {
                    item.SetActive(item.PageId == id);
                }
            }
            if (_settingsItem != null)
            {
                _settingsItem.SetActive(id == "settings");
            }
            target.OnShown();
        }

        public void ToggleNav()
        {
            _collapsed = !_collapsed;
            double targetWidth = _collapsed ? 56 : 200;

            foreach (UIElement el in _navItems.Children)
            {
                var item = el as NavItem;
                if (item != null)
                {
                    item.SetCollapsed(_collapsed);
                }
            }
            _settingsItem.SetCollapsed(_collapsed);
            _versionText.Visibility = _collapsed ? Visibility.Collapsed : Visibility.Visible;
            foreach (TextBlock label in _sectionLabels)
            {
                label.Visibility = _collapsed ? Visibility.Collapsed : Visibility.Visible;
            }

            // 直接切换宽度：只触发一次布局，避免逐帧布局造成的卡顿
            _nav.BeginAnimation(FrameworkElement.WidthProperty, null);
            _nav.Width = targetWidth;
        }

        TextBlock SectionLabel(string text)
        {
            var t = T.Text(text, 9.5, T.Dim, FontWeights.SemiBold);
            t.Margin = new Thickness(0, 10, 0, 2);
            t.Visibility = Visibility.Collapsed;
            _sectionLabels.Add(t);
            return t;
        }

        Border WinButton(string glyph, bool close, RoutedEventHandler onClick)
        {
            var icon = T.Icon(glyph, 10, T.Ink2);
            icon.IsHitTestVisible = false;
            var b = new Border
            {
                Width = 46,
                Height = 36,
                Background = Brushes.Transparent,
                VerticalAlignment = VerticalAlignment.Center,
                Tag = "caption",
                Cursor = Cursors.Arrow,
                Child = icon,
            };
            // 按钮上的按下事件必须吃掉，否则会冒泡到标题栏触发 DragMove，点了等于拖窗口
            b.MouseLeftButtonDown += delegate (object s, MouseButtonEventArgs e) { e.Handled = true; };
            b.MouseEnter += delegate
            {
                b.Background = close ? new SolidColorBrush(Color.FromArgb(255, 196, 43, 28)) : T.B("#14000000");
                if (close)
                {
                    ((TextBlock)b.Child).Foreground = Brushes.White;
                }
            };
            b.MouseLeave += delegate
            {
                b.Background = Brushes.Transparent;
                if (close)
                {
                    ((TextBlock)b.Child).Foreground = new SolidColorBrush(T.Ink2);
                }
            };
            b.MouseLeftButtonUp += delegate { onClick(b, new RoutedEventArgs()); };
            return b;
        }

        static bool InCaptionControl(DependencyObject src)
        {
            while (src != null)
            {
                var b = src as Border;
                if (b != null && (b.Tag as string) == "caption")
                {
                    return true;
                }
                src = VisualTreeHelper.GetParent(src);
            }
            return false;
        }

        void SetupTray()
        {
            _tray = new Forms.NotifyIcon();
            try
            {
                string ico = System.IO.Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "iris.ico");
                _tray.Icon = System.IO.File.Exists(ico) ? new System.Drawing.Icon(ico) : System.Drawing.SystemIcons.Application;
            }
            catch
            {
                _tray.Icon = System.Drawing.SystemIcons.Application;
            }
            _tray.Text = "A梦工具箱";
            _tray.Visible = true;

            var menu = new Forms.ContextMenuStrip();
            var show = new Forms.ToolStripMenuItem("显示主界面");
            show.Font = new System.Drawing.Font(show.Font, System.Drawing.FontStyle.Bold);
            show.Click += delegate { RestoreFromTray(); };
            var exit = new Forms.ToolStripMenuItem("退出");
            exit.Click += delegate { Quit(); };
            menu.Items.Add(show);
            menu.Items.Add(new Forms.ToolStripSeparator());
            menu.Items.Add(exit);
            _tray.ContextMenuStrip = menu;
            _tray.MouseClick += delegate (object s, Forms.MouseEventArgs e)
            {
                if (e.Button == Forms.MouseButtons.Left)
                {
                    if (IsVisible)
                    {
                        HideToTray();
                    }
                    else
                    {
                        RestoreFromTray();
                    }
                }
            };

            Closed += delegate
            {
                if (_tray != null)
                {
                    _tray.Visible = false;
                    _tray.Dispose();
                }
            };
        }

        void HideToTray()
        {
            if (!IsVisible)
            {
                return;
            }
            // 收进托盘时中止还在跑的 adb/fastboot 客户端，避免窗口没了命令还在跑
            Adb.CancelActive();
            // 先透明再隐藏，避免 DWM 收起窗口时闪一下
            Opacity = 0;
            Hide();
            Opacity = 1;
        }

        void MinimizeToTray()
        {
            HideToTray();
        }

        void RestoreFromTray()
        {
            Opacity = 1;
            Show();
            if (WindowState == WindowState.Minimized)
            {
                WindowState = WindowState.Normal;
            }
            Activate();
            Topmost = true;
            Topmost = false;
        }

        public void SendCloseMessage()
        {
            PostMessage(new WindowInteropHelper(this).Handle, 0x0010, IntPtr.Zero, IntPtr.Zero);
        }

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        static extern bool PostMessage(IntPtr hWnd, int msg, IntPtr wParam, IntPtr lParam);

        public void Quit()
        {
            _exiting = true;
            try
            {
                Opacity = 0;
                Hide();
            }
            catch
            {
            }
            Adb.CancelActive();
            try
            {
                // 退出时停掉 adb server，避免窗口关了 adb 还在后台跑
                Adb.Run("kill-server", 3000);
            }
            catch
            {
            }
            try
            {
                Close();
            }
            catch
            {
            }
            try
            {
                Application.Current.Shutdown();
            }
            catch
            {
                Environment.Exit(0);
            }
        }

        protected override void OnClosing(CancelEventArgs e)
        {
            if (!_exiting)
            {
                e.Cancel = true;
                MinimizeToTray();
                return;
            }
            base.OnClosing(e);
        }

        void ToggleMaximize()
        {
            WindowState = WindowState == WindowState.Maximized ? WindowState.Normal : WindowState.Maximized;
        }

        void CacheScrollForWheel(DependencyObject src)
        {
            ScrollViewer sv = FindScrollViewer(src);
            if (sv == null || sv.Content == null)
            {
                return;
            }
            if (_scrollTimer == null)
            {
                _scrollTimer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(220) };
                _scrollTimer.Tick += delegate
                {
                    _scrollTimer.Stop();
                    if (_scrollSv != null)
                    {
                        var c = _scrollSv.Content as UIElement;
                        if (c != null) { c.CacheMode = null; }
                    }
                    _scrollSv = null;
                };
            }
            if (_scrollSv != null && _scrollSv != sv)
            {
                var old = _scrollSv.Content as UIElement;
                if (old != null) { old.CacheMode = null; }
            }
            _scrollSv = sv;
            var content = sv.Content as UIElement;
            if (content != null) { content.CacheMode = new BitmapCache(1.0); }
            _scrollTimer.Stop();
            _scrollTimer.Start();
        }

        static ScrollViewer FindScrollViewer(DependencyObject d)
        {
            while (d != null)
            {
                var sv = d as ScrollViewer;
                if (sv != null)
                {
                    return sv;
                }
                d = VisualTreeHelper.GetParent(d);
            }
            return null;
        }

        void SuppressShadows()
        {
            if (_shadowTimer == null)
            {
                _shadowTimer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(220) };
                _shadowTimer.Tick += delegate
                {
                    RestoreShadows();
                };
            }
            if (_shadows.Count == 0)
            {
                Walk(this, delegate (Border b)
                {
                    if (b.Effect is DropShadowEffect)
                    {
                        _shadows[b] = b.Effect;
                        b.Effect = null;
                    }
                });
            }
            _shadowTimer.Stop();
            _shadowTimer.Start();
        }

        void RestoreShadows()
        {
            if (_shadowTimer != null)
            {
                _shadowTimer.Stop();
            }
            foreach (var kv in _shadows)
            {
                kv.Key.Effect = kv.Value;
            }
            _shadows.Clear();
        }

        static void Walk(DependencyObject d, Action<Border> act)
        {
            int n = VisualTreeHelper.GetChildrenCount(d);
            for (int i = 0; i < n; i++)
            {
                DependencyObject c = VisualTreeHelper.GetChild(d, i);
                var b = c as Border;
                if (b != null)
                {
                    act(b);
                }
                Walk(c, act);
            }
        }

        void UpdateChromeForState()
        {
            try
            {
                var ch = WindowChrome.GetWindowChrome(this);
                if (ch != null)
                {
                    // 最大化时去掉 6px 可缩放边框，避免窗口比工作区大一圈、内容被裁掉
                    ch.ResizeBorderThickness = WindowState == WindowState.Maximized
                        ? new Thickness(0)
                        : new Thickness(6);
                }
            }
            catch
            {
            }
        }

        void UpdateMaxGlyph()
        {
            if (_maxButton == null)
            {
                return;
            }
            var glyph = _maxButton.Child as TextBlock;
            if (glyph != null)
            {
                glyph.Text = WindowState == WindowState.Maximized ? "\uE923" : "\uE922";
            }
        }

        class Blob
        {
            public double X, Y, W, H;
            public string Color;
        }

        void AddBlobs()
        {
            _blobs = new Canvas { IsHitTestVisible = false };
            _root.Children.Add(_blobs);
            AddBlob(0.04, 0.02, 760, 560, "#7AB7D8FF");
            AddBlob(0.70, 0.04, 620, 460, "#5AD0A4FF");
            AddBlob(0.55, 0.62, 820, 600, "#70F2B9DC");
            AddBlob(0.0, 0.72, 560, 460, "#5AA9CBF2");
            SizeChanged += delegate { LayoutBlobs(); };
            LayoutBlobs();
        }

        void AddBlob(double x, double y, double w, double h, string color)
        {
            var brush = new RadialGradientBrush
            {
                GradientOrigin = new Point(0.5, 0.5),
                Center = new Point(0.5, 0.5),
                RadiusX = 0.5,
                RadiusY = 0.5,
            };
            brush.GradientStops.Add(new GradientStop(T.C(color), 0));
            brush.GradientStops.Add(new GradientStop(Color.FromArgb(0, 255, 255, 255), 1));
            var def = new Blob { X = x, Y = y, W = w, H = h, Color = color };
            var e = new Ellipse
            {
                Width = w,
                Height = h,
                Fill = brush,
                IsHitTestVisible = false,
                CacheMode = new BitmapCache(),
            };
            e.Tag = def;
            _blobs.Children.Add(e);
            _blobDefs.Add(def);
        }

        void LayoutBlobs()
        {
            if (_blobs == null)
            {
                return;
            }
            double w = Math.Max(ActualWidth, 900);
            double h = Math.Max(ActualHeight, 600);
            _blobs.Width = w;
            _blobs.Height = h;
            foreach (UIElement el in _blobs.Children)
            {
                var e = el as Ellipse;
                var def = e == null ? null : e.Tag as Blob;
                if (def == null)
                {
                    continue;
                }
                Canvas.SetLeft(e, def.X * w - def.W / 2);
                Canvas.SetTop(e, def.Y * h - def.H / 2);
            }
        }

        public void Navigate(string id)
        {
            ShowPage(id);
        }

        public void ShowToast(string message, bool bad = false)
        {
            _toastText.Text = message;
            _toast.Background = new SolidColorBrush(bad
                ? Color.FromArgb(235, 140, 40, 34)
                : Color.FromArgb(235, 32, 36, 42));
            _toast.BeginAnimation(OpacityProperty, new DoubleAnimation(1, TimeSpan.FromMilliseconds(120)));
            var timer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(2.6) };
            timer.Tick += delegate
            {
                timer.Stop();
                _toast.BeginAnimation(OpacityProperty, new DoubleAnimation(0, TimeSpan.FromMilliseconds(220)));
            };
            timer.Start();
        }

        /* Win10/11 亚克力：DWM 模糊窗口背后内容，再叠一层半透明渐变。 */
        void TryEnableAcrylic(IntPtr hwnd)
        {
            try
            {
                if (Environment.OSVersion.Version.Major < 10)
                {
                    return;
                }
                var accent = new AccentPolicy
                {
                    AccentState = 4, // ACCENT_ENABLE_ACRYLICBLURBEHIND
                    AccentFlags = 2,
                    GradientColor = unchecked((int)0x99F7F9FC), // AABBGGRR 浅色底
                    AnimationId = 0,
                };
                int size = System.Runtime.InteropServices.Marshal.SizeOf(typeof(AccentPolicy));
                IntPtr ptr = System.Runtime.InteropServices.Marshal.AllocHGlobal(size);
                try
                {
                    System.Runtime.InteropServices.Marshal.StructureToPtr(accent, ptr, false);
                    var data = new WindowCompositionAttributeData
                    {
                        Attribute = 19, // WCA_ACCENT_POLICY
                        Data = ptr,
                        SizeOfData = size,
                    };
                    int ok = SetWindowCompositionAttribute(hwnd, ref data);
                    if (ok != 0)
                    {
                        Background = new LinearGradientBrush(
                            Color.FromArgb(0x4D, 0xCD, 0xE4, 0xFA),
                            Color.FromArgb(0x4D, 0xF7, 0xD8, 0xE7),
                            new Point(0, 0), new Point(1, 1));
                    }
                }
                finally
                {
                    System.Runtime.InteropServices.Marshal.FreeHGlobal(ptr);
                }
            }
            catch
            {
            }
        }

        [System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
        struct AccentPolicy
        {
            public int AccentState;
            public int AccentFlags;
            public int GradientColor;
            public int AnimationId;
        }

        [System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
        struct WindowCompositionAttributeData
        {
            public int Attribute;
            public IntPtr Data;
            public int SizeOfData;
        }

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        static extern int SetWindowCompositionAttribute(IntPtr hwnd, ref WindowCompositionAttributeData data);

        protected override void OnSourceInitialized(EventArgs e)
        {
            base.OnSourceInitialized(e);
            try
            {
                IntPtr hwnd = new WindowInteropHelper(this).Handle;
                int pref = 2;
                DwmSetWindowAttribute(hwnd, 33, ref pref, sizeof(int));
                HwndSource.FromHwnd(hwnd).AddHook(WndProcHook);
            }
            catch
            {
            }
        }

        /* 无边框窗口最大化时，Windows 默认会盖住任务栏；这里按显示器工作区修正。 */
        IntPtr WndProcHook(IntPtr hwnd, int msg, IntPtr wParam, IntPtr lParam, ref bool handled)
        {
            // 拖动边框缩放时先收起页面内容，只重绘背景，避免核显上追帧重排
            if (msg == 0x0231) // WM_ENTERSIZEMOVE
            {
                _inSizeMove = true;
            }
            if (msg == 0x0214 && _inSizeMove && !_resizingContent && _content != null)
            {
                _resizingContent = true;
                _content.Visibility = Visibility.Collapsed;
                if (_blobs != null) { _blobs.Visibility = Visibility.Collapsed; }
            }
            if (msg == 0x0232) // WM_EXITSIZEMOVE
            {
                _inSizeMove = false;
                if (_resizingContent)
                {
                    _resizingContent = false;
                    _content.Visibility = Visibility.Visible;
                    if (_blobs != null) { _blobs.Visibility = Visibility.Visible; }
                }
            }
            // 第二个实例广播「显示主界面」
            if (msg == ShowMessageId)
            {
                Dispatcher.BeginInvoke(new Action(RestoreFromTray));
                handled = true;
                return IntPtr.Zero;
            }
            // 自己处理四边/四角命中，交给系统原生缩放，避免 WPF 逐帧重排导致的抖动
            if (msg == 0x0084 && WindowState != WindowState.Maximized)
            {
                long lp = lParam.ToInt64();
                int x = (short)(lp & 0xFFFF);
                int y = (short)((lp >> 16) & 0xFFFF);
                RECT wr;
                if (GetWindowRect(hwnd, out wr))
                {
                    const int b = 8;
                    bool left = x >= wr.Left && x < wr.Left + b;
                    bool right = x <= wr.Right && x > wr.Right - b;
                    bool top = y >= wr.Top && y < wr.Top + b;
                    bool bottom = y <= wr.Bottom && y > wr.Bottom - b;
                    int hit = 0;
                    if (top && left) { hit = 13; }        // HTTOPLEFT
                    else if (top && right) { hit = 14; }  // HTTOPRIGHT
                    else if (bottom && left) { hit = 16; }// HTBOTTOMLEFT
                    else if (bottom && right) { hit = 17;}// HTBOTTOMRIGHT
                    else if (left) { hit = 10; }          // HTLEFT
                    else if (right) { hit = 11; }         // HTRIGHT
                    else if (top) { hit = 12; }           // HTTOP
                    else if (bottom) { hit = 15; }        // HTBOTTOM
                    if (hit != 0)
                    {
                        handled = true;
                        return (IntPtr)hit;
                    }
                }
            }
            // 关闭按钮 / Alt+F4：只隐藏到托盘，避免先触发关闭再取消造成的闪一下
            if (msg == 0x0010 && !_exiting)
            {
                HideToTray();
                handled = true;
                return IntPtr.Zero;
            }
            if (msg == 0x0024) // WM_GETMINMAXINFO
            {
                try
                {
                    var mmi = (MINMAXINFO)System.Runtime.InteropServices.Marshal.PtrToStructure(lParam, typeof(MINMAXINFO));
                    IntPtr monitor = MonitorFromWindow(hwnd, 2); // MONITOR_DEFAULTTONEAREST
                    if (monitor != IntPtr.Zero)
                    {
                        var info = new MONITORINFO();
                        info.cbSize = System.Runtime.InteropServices.Marshal.SizeOf(typeof(MONITORINFO));
                        if (GetMonitorInfo(monitor, ref info))
                        {
                            RECT work = info.rcWork;
                            RECT mon = info.rcMonitor;
                            mmi.ptMaxPosition.X = work.Left - mon.Left;
                            mmi.ptMaxPosition.Y = work.Top - mon.Top;
                            mmi.ptMaxSize.X = work.Right - work.Left;
                            mmi.ptMaxSize.Y = work.Bottom - work.Top;
                            System.Runtime.InteropServices.Marshal.StructureToPtr(mmi, lParam, true);
                        }
                    }
                }
                catch
                {
                }
            }
            return IntPtr.Zero;
        }

        [System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
        struct POINT
        {
            public int X;
            public int Y;
        }

        [System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
        struct RECT
        {
            public int Left;
            public int Top;
            public int Right;
            public int Bottom;
        }

        [System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
        struct MINMAXINFO
        {
            public POINT ptReserved;
            public POINT ptMaxSize;
            public POINT ptMaxPosition;
            public POINT ptMinTrackSize;
            public POINT ptMaxTrackSize;
        }

        [System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
        struct MONITORINFO
        {
            public int cbSize;
            public RECT rcMonitor;
            public RECT rcWork;
            public int dwFlags;
        }

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        static extern IntPtr MonitorFromWindow(IntPtr hwnd, int flags);

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        static extern bool GetMonitorInfo(IntPtr hMonitor, ref MONITORINFO lpmi);

        [System.Runtime.InteropServices.DllImport("dwmapi.dll")]
        static extern int DwmSetWindowAttribute(IntPtr hwnd, int attr, ref int attrValue, int attrSize);

        static readonly int ShowMessageId = RegisterWindowMessage("AMengToolbox.Show");

        [System.Runtime.InteropServices.DllImport("user32.dll", CharSet = System.Runtime.InteropServices.CharSet.Unicode)]
        static extern int RegisterWindowMessage(string message);

        public void CaptureWindow(string path)
        {
            try
            {
                IntPtr hwnd = new WindowInteropHelper(this).Handle;
                RECT rect;
                if (!GetWindowRect(hwnd, out rect))
                {
                    return;
                }
                int w = Math.Max(1, rect.Right - rect.Left);
                int h = Math.Max(1, rect.Bottom - rect.Top);
                using (var bmp = new System.Drawing.Bitmap(w, h))
                using (var g = System.Drawing.Graphics.FromImage(bmp))
                {
                    IntPtr hdc = g.GetHdc();
                    PrintWindow(hwnd, hdc, 2);
                    g.ReleaseHdc(hdc);
                    bmp.Save(path, System.Drawing.Imaging.ImageFormat.Png);
                }
            }
            catch
            {
            }
        }

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        static extern bool GetWindowRect(IntPtr hwnd, out RECT rect);

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        static extern bool PrintWindow(IntPtr hwnd, IntPtr hdc, uint flags);

        public void RenderTo(string path, int width, int height)
        {
            // 截图模式下不等动画：把当前页直接置为最终状态
            foreach (UIElement el in _content.Children)
            {
                if (el.Visibility == Visibility.Visible)
                {
                    el.Opacity = 1;
                    var tt = el.RenderTransform as TranslateTransform;
                    if (tt != null)
                    {
                        tt.Y = 0;
                    }
                }
            }
            Width = width;
            Height = height;
            _root.Measure(new Size(width, height));
            _root.Arrange(new Rect(0, 0, width, height));
            _root.UpdateLayout();
            var bmp = new System.Windows.Media.Imaging.RenderTargetBitmap(width, height, 96, 96, PixelFormats.Pbgra32);
            bmp.Render(_root);
            var enc = new System.Windows.Media.Imaging.PngBitmapEncoder();
            enc.Frames.Add(System.Windows.Media.Imaging.BitmapFrame.Create(bmp));
            using (var fs = System.IO.File.Create(path))
            {
                enc.Save(fs);
            }
        }
    }
}
