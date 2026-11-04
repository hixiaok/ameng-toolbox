using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Text;
using System.Windows.Forms;
using Microsoft.Win32;

namespace AmengSetup
{
    static class Program
    {
        [STAThread]
        static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new SetupForm());
        }
    }

    class SetupForm : Form
    {
        readonly TextBox _path;
        readonly CheckBox _desktop;
        readonly CheckBox _run;
        readonly Button _install;
        readonly ProgressBar _bar;
        readonly Label _status;
        const string Version = "0.5.0";

        public SetupForm()
        {
            Text = "A梦工具箱 安装程序";
            Width = 560;
            Height = 340;
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            MinimizeBox = false;
            StartPosition = FormStartPosition.CenterScreen;
            BackColor = System.Drawing.Color.FromArgb(247, 249, 252);
            Font = new System.Drawing.Font("Microsoft YaHei UI", 9f);

            var title = new Label
            {
                Text = "A梦工具箱",
                Font = new System.Drawing.Font("Microsoft YaHei UI", 18f, System.Drawing.FontStyle.Bold),
                ForeColor = System.Drawing.Color.FromArgb(30, 36, 48),
                Left = 24,
                Top = 18,
                Width = 400,
                Height = 40,
            };
            Controls.Add(title);

            Controls.Add(new Label { Text = "安卓刷机 / 文件 / 应用工具箱 · v" + Version, Left = 26, Top = 60, Width = 460, ForeColor = System.Drawing.Color.FromArgb(110, 118, 132) });

            Controls.Add(new Label { Text = "安装目录", Left = 26, Top = 96, Width = 80, ForeColor = System.Drawing.Color.FromArgb(80, 88, 102) });
            _path = new TextBox
            {
                Left = 26,
                Top = 118,
                Width = 410,
                Text = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "A梦工具箱"),
            };
            Controls.Add(_path);
            var browse = new Button { Text = "浏览…", Left = 444, Top = 117, Width = 82 };
            browse.Click += delegate
            {
                using (var dlg = new FolderBrowserDialog())
                {
                    if (dlg.ShowDialog() == DialogResult.OK) { _path.Text = dlg.SelectedPath; }
                }
            };
            Controls.Add(browse);

            _desktop = new CheckBox { Text = "创建桌面快捷方式", Left = 26, Top = 154, Width = 220, Checked = true };
            _run = new CheckBox { Text = "安装完成后立即运行", Left = 260, Top = 154, Width = 220, Checked = true };
            Controls.Add(_desktop);
            Controls.Add(_run);

            _install = new Button
            {
                Text = "安装",
                Left = 388,
                Top = 196,
                Width = 138,
                Height = 38,
                BackColor = System.Drawing.Color.FromArgb(32, 108, 189),
                ForeColor = System.Drawing.Color.White,
                FlatStyle = FlatStyle.Flat,
            };
            _install.Click += delegate { Install(); };
            Controls.Add(_install);

            _bar = new ProgressBar { Left = 26, Top = 202, Width = 340, Height = 18 };
            Controls.Add(_bar);
            _status = new Label { Text = "准备安装", Left = 26, Top = 246, Width = 500, Height = 40, ForeColor = System.Drawing.Color.FromArgb(110, 118, 132) };
            Controls.Add(_status);

            Controls.Add(new Label
            {
                Text = "安装到 Program Files 需要管理员权限；程序运行时也需要管理员权限。",
                Left = 26,
                Top = 282,
                Width = 500,
                ForeColor = System.Drawing.Color.FromArgb(150, 118, 60),
            });
        }

        void Install()
        {
            int running = Process.GetProcessesByName("A梦工具箱").Length;
            if (running > 0)
            {
                MessageBox.Show("请先退出正在运行的 A梦工具箱（托盘右键 → 退出），再安装。", "A梦工具箱");
                return;
            }
            string dir = _path.Text.Trim();
            if (dir.Length == 0) { MessageBox.Show("请选择安装目录"); return; }
            try
            {
                if (Directory.Exists(dir) && File.Exists(Path.Combine(dir, "A梦工具箱.exe")))
                {
                    if (MessageBox.Show("目录已存在旧版本，覆盖安装？", "A梦工具箱", MessageBoxButtons.OKCancel, MessageBoxIcon.Question) != DialogResult.OK)
                    {
                        return;
                    }
                }
                _install.Enabled = false;
                _status.Text = "正在释放文件…";
                Directory.CreateDirectory(dir);

                string temp = Path.Combine(Path.GetTempPath(), "ameng-setup-" + Guid.NewGuid().ToString("N") + ".zip");
                using (Stream res = Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip"))
                using (FileStream fs = File.Create(temp))
                {
                    res.CopyTo(fs);
                }

                int done = 0;
                using (ZipArchive zip = ZipFile.OpenRead(temp))
                {
                    int total = zip.Entries.Count;
                    foreach (ZipArchiveEntry entry in zip.Entries)
                    {
                        string name = entry.FullName.Replace('\\', '/');
                        int slash = name.IndexOf('/');
                        if (slash >= 0) { name = name.Substring(slash + 1); }
                        if (name.Length == 0) { continue; }
                        string dest = Path.Combine(dir, name.Replace('/', '\\'));
                        if (name.EndsWith("/"))
                        {
                            Directory.CreateDirectory(dest);
                        }
                        else
                        {
                            Directory.CreateDirectory(Path.GetDirectoryName(dest));
                            entry.ExtractToFile(dest, true);
                        }
                        done++;
                        if (done % 5 == 0 || done == total)
                        {
                            _bar.Value = Math.Min(100, done * 100 / Math.Max(1, total));
                            _status.Text = "正在释放文件… " + done + "/" + total;
                            Application.DoEvents();
                        }
                    }
                }
                try { File.Delete(temp); } catch { }

                string exe = Path.Combine(dir, "A梦工具箱.exe");
                _status.Text = "正在创建快捷方式…";
                Application.DoEvents();
                string startMenu = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "A梦工具箱.lnk");
                MakeShortcut(startMenu, exe, dir);
                if (_desktop.Checked)
                {
                    MakeShortcut(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "A梦工具箱.lnk"), exe, dir);
                }

                string uninstall = Path.Combine(dir, "卸载.bat");
                File.WriteAllText(uninstall,
                    "@echo off\r\n"
                    + "del /f /q \"%USERPROFILE%\\Desktop\\A梦工具箱.lnk\" 2>nul\r\n"
                    + "del /f /q \"%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\A梦工具箱.lnk\" 2>nul\r\n"
                    + "reg delete \"HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\A梦工具箱\" /f >nul 2>&1\r\n"
                    + "start \"\" cmd /c \"timeout /t 2 >nul & rmdir /s /q \\\"%~dp0\\\"\"\r\n",
                    Encoding.Default);

                using (RegistryKey key = Registry.LocalMachine.CreateSubKey(@"Software\Microsoft\Windows\CurrentVersion\Uninstall\A梦工具箱"))
                {
                    key.SetValue("DisplayName", "A梦工具箱");
                    key.SetValue("DisplayVersion", Version);
                    key.SetValue("Publisher", "A梦工具箱");
                    key.SetValue("InstallLocation", dir);
                    key.SetValue("DisplayIcon", exe);
                    key.SetValue("UninstallString", "\"" + uninstall + "\"");
                    key.SetValue("NoModify", 1, RegistryValueKind.DWord);
                    key.SetValue("NoRepair", 1, RegistryValueKind.DWord);
                }

                _bar.Value = 100;
                _status.Text = "安装完成";
                if (_run.Checked)
                {
                    Process.Start(new ProcessStartInfo(exe) { WorkingDirectory = dir, UseShellExecute = true });
                }
                MessageBox.Show("安装完成。\n\n安装目录：" + dir, "A梦工具箱");
                Close();
            }
            catch (Exception ex)
            {
                _install.Enabled = true;
                _status.Text = "安装失败";
                MessageBox.Show("安装失败：" + ex.Message, "A梦工具箱", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        static void MakeShortcut(string path, string target, string workDir)
        {
            object shell = Activator.CreateInstance(Type.GetTypeFromProgID("WScript.Shell"));
            object lnk = shell.GetType().InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] { path });
            Type t = lnk.GetType();
            t.InvokeMember("TargetPath", BindingFlags.SetProperty, null, lnk, new object[] { target });
            t.InvokeMember("WorkingDirectory", BindingFlags.SetProperty, null, lnk, new object[] { workDir });
            t.InvokeMember("IconLocation", BindingFlags.SetProperty, null, lnk, new object[] { target + ",0" });
            t.InvokeMember("Save", BindingFlags.InvokeMethod, null, lnk, null);
        }
    }
}
