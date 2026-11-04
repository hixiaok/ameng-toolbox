using System;
using System.Windows;

namespace Iris
{
    static class Program
    {
        [STAThread]
        static void Main(string[] args)
        {
            bool created;
            string mutexName = Environment.GetEnvironmentVariable("IRIS_MUTEX");
            if (string.IsNullOrEmpty(mutexName))
            {
                mutexName = "AMengToolbox.SingleInstance.v051";
            }
            using (var mutex = new System.Threading.Mutex(true, mutexName, out created))
            {
                if (!created)
                {
                    if (args.Length > 0 && args[0] == "--closetest")
                    {
                        System.IO.File.WriteAllText(
                            System.IO.Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "boot.log"),
                            "existing instance");
                    }
                    // 已有实例在跑：广播一条消息让它把主界面显示出来，然后自己退出
                    int msg = RegisterWindowMessage("AMengToolbox.Show");
                    PostMessage(new IntPtr(0xffff), msg, IntPtr.Zero, IntPtr.Zero);
                    return;
                }
                if (args.Length > 0 && args[0] == "--closetest")
                {
                    System.IO.File.WriteAllText(
                        System.IO.Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "boot.log"),
                        "created");
                }
                try
                {
                    Run(args);
                }
                catch (Exception ex)
                {
                    try
                    {
                        System.IO.File.WriteAllText(
                            System.IO.Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "crash.log"),
                            ex.ToString());
                    }
                    catch
                    {
                    }
                    Environment.Exit(2);
                }
                GC.KeepAlive(mutex);
            }
        }

        [System.Runtime.InteropServices.DllImport("user32.dll", CharSet = System.Runtime.InteropServices.CharSet.Unicode)]
        static extern int RegisterWindowMessage(string message);

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        static extern bool PostMessage(IntPtr hWnd, int msg, IntPtr wParam, IntPtr lParam);

        static void Run(string[] args)
        {
            var app = new Application();
            app.ShutdownMode = ShutdownMode.OnMainWindowClose;
            app.DispatcherUnhandledException += delegate (object s, System.Windows.Threading.DispatcherUnhandledExceptionEventArgs e)
            {
                try
                {
                    System.IO.File.WriteAllText(
                        System.IO.Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "crash.log"),
                        e.Exception.ToString());
                }
                catch
                {
                }
                MessageBox.Show("操作出错：" + e.Exception.Message + "\n详细信息已写入 crash.log", "A梦工具箱");
                e.Handled = true;
            };

            bool demo = false;
            bool shot = false;
            string outPath = "iris-shot.png";
            string page = "";
            for (int i = 0; i < args.Length; i++)
            {
                if (args[i] == "--demo")
                {
                    demo = true;
                }
                else if (args[i] == "--page" && i + 1 < args.Length)
                {
                    page = args[i + 1];
                }
                else if (args[i] == "--shot" && i + 1 < args.Length)
                {
                    shot = true;
                    outPath = args[i + 1];
                }
            }

            var win = new MainWindow(demo);
            if (page.Length > 0)
            {
                win.Navigate(page);
            }
            win.Icon = AppIcon.Load();
            app.MainWindow = win;

            if (args.Length > 0 && args[0] == "--diag")
            {
                System.IO.File.WriteAllText(
                    System.IO.Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "diag.txt"),
                    "adb=" + Adb.Path + "\r\navailable=" + Adb.Available + "\r\ndevices=" + Adb.Devices().Count);
                return;
            }

            if (shot)
            {
                win.RenderTo(outPath, 1360, 860);
                return;
            }
            if (args.Length >= 2 && args[0] == "--capture")
            {
                string capturePath = args[1];
                if (args.Length > 2 && args[2] == "max")
                {
                    win.WindowState = WindowState.Maximized;
                }
                else if (args.Length > 2 && args[2] == "nav")
                {
                    win.ToggleNav();
                }
                var capTimer = new System.Windows.Threading.DispatcherTimer { Interval = TimeSpan.FromMilliseconds(900) };
                capTimer.Tick += delegate
                {
                    capTimer.Stop();
                    win.CaptureWindow(capturePath);
                    win.Quit();
                };
                capTimer.Start();
            }
            if (args.Length > 0 && args[0] == "--closetest")
            {
                var closeTimer = new System.Windows.Threading.DispatcherTimer { Interval = TimeSpan.FromMilliseconds(400) };
                closeTimer.Tick += delegate
                {
                    closeTimer.Stop();
                    win.SendCloseMessage();
                };
                closeTimer.Start();
                var checkTimer = new System.Windows.Threading.DispatcherTimer { Interval = TimeSpan.FromMilliseconds(900) };
                checkTimer.Tick += delegate
                {
                    checkTimer.Stop();
                    System.IO.File.WriteAllText(
                        System.IO.Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "closetest.txt"),
                        "visible=" + win.IsVisible + "\r\nstate=" + win.WindowState);
                    win.Quit();
                };
                checkTimer.Start();
            }
            if (args.Length > 0 && args[0] == "--smoke")
            {
                if (args.Length > 1 && args[1] == "--max")
                {
                    win.WindowState = WindowState.Maximized;
                }
                var timer = new System.Windows.Threading.DispatcherTimer { Interval = TimeSpan.FromMilliseconds(1300) };
                timer.Tick += delegate
                {
                    timer.Stop();
                    win.Quit();
                };
                timer.Start();
                var restore = new System.Windows.Threading.DispatcherTimer { Interval = TimeSpan.FromMilliseconds(700) };
                restore.Tick += delegate
                {
                    restore.Stop();
                    win.WindowState = WindowState.Normal;
                };
                restore.Start();
                if (Array.IndexOf(args, "--nav") >= 0)
                {
                    var nav = new System.Windows.Threading.DispatcherTimer { Interval = TimeSpan.FromMilliseconds(400) };
                    nav.Tick += delegate
                    {
                        nav.Stop();
                        win.ToggleNav();
                    };
                    nav.Start();
                }
            }
            app.Run(win);
        }
    }

    static class AppIcon
    {
        public static System.Windows.Media.ImageSource Load()
        {
            try
            {
                string path = System.IO.Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "iris.ico");
                if (!System.IO.File.Exists(path))
                {
                    return null;
                }
                var dec = new System.Windows.Media.Imaging.IconBitmapDecoder(
                    new Uri(path),
                    System.Windows.Media.Imaging.BitmapCreateOptions.None,
                    System.Windows.Media.Imaging.BitmapCacheOption.OnLoad);
                System.Windows.Media.Imaging.BitmapFrame best = null;
                foreach (var frame in dec.Frames)
                {
                    if (best == null || frame.PixelWidth > best.PixelWidth)
                    {
                        best = frame;
                    }
                }
                return best;
            }
            catch
            {
                return null;
            }
        }
    }
}
