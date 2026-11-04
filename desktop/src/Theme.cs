using System;
using System.Collections.Generic;
using System.Globalization;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Effects;

namespace Iris
{
    /// <summary>统一的颜色、字体与小控件工厂。界面全部用 WPF 原生绘制，不是网页。</summary>
    static class T
    {
        public static readonly FontFamily Font = new FontFamily("Microsoft YaHei UI");
        public static readonly FontFamily Icons = new FontFamily("Segoe Fluent Icons, Segoe MDL2 Assets");

        public static readonly Color Ink = C("#1B1B1F");
        public static readonly Color Ink2 = C("#3B3F46");
        public static readonly Color Muted = C("#5F6874");
        public static readonly Color Dim = C("#98A1AC");
        public static readonly Color Accent = C("#0F6CBD");
        public static readonly Color AccentHover = C("#115EA3");
        public static readonly Color Danger = C("#C4314B");
        public static readonly Color Ok = C("#0F7B45");
        public static readonly Color Line = C("#1A000000");
        public static readonly Color LineSoft = C("#12000000");

        public static Color C(string hex)
        {
            return (Color)ColorConverter.ConvertFromString(hex);
        }

        public static SolidColorBrush B(string hex)
        {
            var b = new SolidColorBrush(C(hex));
            b.Freeze();
            return b;
        }

        public static TextBlock Text(string text, double size, Color color, FontWeight weight)
        {
            var t = new TextBlock
            {
                Text = text,
                FontFamily = Font,
                FontSize = size,
                Foreground = new SolidColorBrush(color),
                FontWeight = weight,
                TextTrimming = TextTrimming.CharacterEllipsis,
                VerticalAlignment = VerticalAlignment.Center,
            };
            TextOptions.SetTextFormattingMode(t, TextFormattingMode.Ideal);
            TextOptions.SetTextRenderingMode(t, TextRenderingMode.ClearType);
            return t;
        }

        public static TextBlock Text(string text, double size, Color color)
        {
            return Text(text, size, color, FontWeights.Normal);
        }

        public static TextBlock Icon(string glyph, double size, Color color)
        {
            var t = new TextBlock
            {
                Text = glyph,
                FontFamily = Icons,
                FontSize = size,
                Foreground = new SolidColorBrush(color),
                VerticalAlignment = VerticalAlignment.Center,
                HorizontalAlignment = HorizontalAlignment.Center,
            };
            return t;
        }

        public static Border Card(string bg)
        {
            var b = new Border
            {
                CornerRadius = new CornerRadius(14),
                Background = B(bg),
                BorderBrush = new SolidColorBrush(Color.FromArgb(120, 255, 255, 255)),
                BorderThickness = new Thickness(1),
            };
            return b;
        }

        public static Border Card(string bg, double radius)
        {
            var b = Card(bg);
            b.CornerRadius = new CornerRadius(radius);
            return b;
        }

        /// <summary>主按钮：蓝底白字，鼠标悬停变深。</summary>
        public static Border Button(string text, bool primary, RoutedEventHandler onClick)
        {
            var b = new Border
            {
                CornerRadius = new CornerRadius(7),
                Height = 38,
                Background = primary ? new SolidColorBrush(Accent) : B("#FFFFFF"),
                BorderBrush = primary ? new SolidColorBrush(Accent) : B("#D5DAE1"),
                BorderThickness = new Thickness(1),
                Cursor = Cursors.Hand,
                Padding = new Thickness(14, 0, 14, 0),
            };
            var t = Text(text, 13, primary ? Colors.White : Ink2, FontWeights.SemiBold);
            t.HorizontalAlignment = HorizontalAlignment.Center;
            t.VerticalAlignment = VerticalAlignment.Center;
            t.IsHitTestVisible = false;
            b.Child = t;

            b.MouseEnter += delegate
            {
                b.Background = primary ? new SolidColorBrush(AccentHover) : B("#F3F6FA");
            };
            b.MouseLeave += delegate
            {
                b.Background = primary ? new SolidColorBrush(Accent) : B("#FFFFFF");
            };
            b.MouseLeftButtonUp += delegate { onClick(b, new RoutedEventArgs()); };
            return b;
        }

        public static Border IconButton(string glyph, string tooltip, RoutedEventHandler onClick)
        {
            var b = new Border
            {
                Width = 34,
                Height = 30,
                CornerRadius = new CornerRadius(6),
                Background = Brushes.Transparent,
                Cursor = Cursors.Hand,
            };
            b.Child = Icon(glyph, 14, Ink2);
            ((FrameworkElement)b.Child).IsHitTestVisible = false;
            if (tooltip != null)
            {
                b.ToolTip = tooltip;
            }
            b.MouseEnter += delegate { b.Background = B("#14000000"); };
            b.MouseLeave += delegate { b.Background = Brushes.Transparent; };
            b.MouseLeftButtonUp += delegate { onClick(b, new RoutedEventArgs()); };
            return b;
        }
    }

    /// <summary>圆形进度环，中心显示百分比。</summary>
    class Ring : FrameworkElement
    {
        double _value;
        string _centerText;
        Color _accentColor;
        string _caption;

        public double Value
        {
            get { return _value; }
            set { _value = value; InvalidateVisual(); }
        }

        public string CenterText
        {
            get { return _centerText; }
            set { _centerText = value; InvalidateVisual(); }
        }

        public Color AccentColor
        {
            get { return _accentColor; }
            set { _accentColor = value; InvalidateVisual(); }
        }

        public string Caption
        {
            get { return _caption; }
            set { _caption = value; InvalidateVisual(); }
        }

        public Ring()
        {
            _accentColor = T.Accent;
            _centerText = "0%";
        }

        protected override void OnRender(DrawingContext dc)
        {
            double size = Math.Min(ActualWidth, ActualHeight);
            if (size <= 0)
            {
                return;
            }
            var center = new Point(ActualWidth / 2, ActualHeight / 2);
            double thickness = Math.Max(8, size * 0.075);
            double r = size / 2 - thickness / 2 - 2;

            var track = new Pen(new SolidColorBrush(Color.FromArgb(255, 228, 232, 238)), thickness);
            dc.DrawEllipse(null, track, center, r, r);

            if (Value > 0)
            {
                double angle = Math.Min(100, Math.Max(0, Value)) / 100.0 * 360.0;
                var geo = new StreamGeometry();
                using (var ctx = geo.Open())
                {
                    Point start = PointOn(center, r, -90);
                    ctx.BeginFigure(start, false, false);
                    ctx.ArcTo(PointOn(center, r, -90 + angle), new Size(r, r), 0,
                        angle > 180, SweepDirection.Clockwise, true, false);
                }
                geo.Freeze();
                var pen = new Pen(new SolidColorBrush(AccentColor), thickness);
                pen.StartLineCap = PenLineCap.Round;
                pen.EndLineCap = PenLineCap.Round;
                dc.DrawGeometry(null, pen, geo);
            }

            if (!string.IsNullOrEmpty(CenterText))
            {
                var ft = new FormattedText(CenterText, CultureInfo.CurrentCulture, FlowDirection.LeftToRight,
                    new Typeface(T.Font, FontStyles.Normal, FontWeights.SemiBold, FontStretches.Normal),
                    size * 0.22, new SolidColorBrush(T.Ink), 1.0);
                dc.DrawText(ft, new Point(center.X - ft.Width / 2, center.Y - ft.Height / 2));
            }

            if (!string.IsNullOrEmpty(Caption))
            {
                var ft = new FormattedText(Caption, CultureInfo.CurrentCulture, FlowDirection.LeftToRight,
                    new Typeface(T.Font, FontStyles.Normal, FontWeights.Normal, FontStretches.Normal),
                    12.5, new SolidColorBrush(T.Muted), 1.0);
                dc.DrawText(ft, new Point(center.X - ft.Width / 2, center.Y + size * 0.20));
            }
        }

        static Point PointOn(Point center, double r, double deg)
        {
            double rad = deg * Math.PI / 180.0;
            return new Point(center.X + r * Math.Cos(rad), center.Y + r * Math.Sin(rad));
        }
    }

    /// <summary>自绘下拉框：圆角、白底、右侧 chevron，点开是菜单。</summary>
    class SelectBox : Grid
    {
        readonly TextBlock _text;
        readonly Border _frame;
        readonly List<string> _items = new List<string>();
        int _index;
        Popup _openPopup;

        public event EventHandler Changed;

        public SelectBox(double height)
        {
            Height = height;
            _frame = new Border
            {
                CornerRadius = new CornerRadius(7),
                Background = T.B("#FFFFFF"),
                BorderBrush = T.B("#D5DAE1"),
                BorderThickness = new Thickness(1),
            };
            Children.Add(_frame);
            _frame.IsHitTestVisible = false;

            var g = new Grid();
            g.IsHitTestVisible = false;
            g.ColumnDefinitions.Add(new ColumnDefinition());
            g.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(34) });
            _text = T.Text("", 13, T.Ink2);
            _text.Margin = new Thickness(12, 0, 4, 0);
            _text.VerticalAlignment = VerticalAlignment.Center;
            g.Children.Add(_text);
            var chev = T.Icon("\uE70D", 10, T.Muted);
            Grid.SetColumn(chev, 1);
            g.Children.Add(chev);
            Children.Add(g);

            Cursor = Cursors.Hand;
            Background = Brushes.Transparent;
            MouseLeftButtonUp += delegate { Open(); };
            MouseEnter += delegate { _frame.BorderBrush = new SolidColorBrush(T.Accent); };
            MouseLeave += delegate { _frame.BorderBrush = T.B("#D5DAE1"); };
        }

        public void SetItems(IEnumerable<string> items, int selected)
        {
            _items.Clear();
            _items.AddRange(items);
            _index = Math.Max(0, Math.Min(selected, _items.Count - 1));
            _text.Text = _items.Count > 0 ? _items[_index] : "";
        }

        public int SelectedIndex { get { return _index; } }

        public string SelectedItem
        {
            get { return _items.Count > 0 ? _items[_index] : ""; }
        }

        void Open()
        {
            if (_openPopup != null)
            {
                _openPopup.IsOpen = false;
            }
            var popup = new Popup
            {
                PlacementTarget = this,
                Placement = PlacementMode.Bottom,
                VerticalOffset = 4,
                StaysOpen = false,
                AllowsTransparency = true,
            };

            var panel = new StackPanel();
            for (int i = 0; i < _items.Count; i++)
            {
                int idx = i;
                bool selected = i == _index;
                var row = new Grid();
                row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(4) });
                row.ColumnDefinitions.Add(new ColumnDefinition());
                var bar = new Border
                {
                    Width = 3,
                    Height = 16,
                    CornerRadius = new CornerRadius(2),
                    Background = new SolidColorBrush(T.Accent),
                    HorizontalAlignment = HorizontalAlignment.Left,
                    VerticalAlignment = VerticalAlignment.Center,
                    Visibility = selected ? Visibility.Visible : Visibility.Collapsed,
                };
                row.Children.Add(bar);
                var label = T.Text(_items[i], 13, selected ? T.Accent : T.Ink2, selected ? FontWeights.SemiBold : FontWeights.Normal);
                label.Margin = new Thickness(10, 0, 10, 0);
                Grid.SetColumn(label, 1);
                row.Children.Add(label);

                var item = new Border
                {
                    CornerRadius = new CornerRadius(6),
                    Padding = new Thickness(4, 7, 4, 7),
                    Background = selected ? T.B("#1A0F6CBD") : Brushes.Transparent,
                    Cursor = Cursors.Hand,
                    Child = row,
                };
                item.MouseEnter += delegate
                {
                    if (!selected) { item.Background = T.B("#F2F5FA"); }
                };
                item.MouseLeave += delegate
                {
                    if (!selected) { item.Background = Brushes.Transparent; }
                };
                item.MouseLeftButtonUp += delegate
                {
                    _index = idx;
                    _text.Text = _items[idx];
                    popup.IsOpen = false;
                    if (Changed != null)
                    {
                        Changed(this, EventArgs.Empty);
                    }
                };
                panel.Children.Add(item);
            }

            var scroll = new ScrollViewer
            {
                MaxHeight = 320,
                VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
                HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled,
                Content = panel,
            };
            var frame = new Border
            {
                Background = T.B("#FFFFFF"),
                CornerRadius = new CornerRadius(9),
                BorderBrush = T.B("#E1E5EB"),
                BorderThickness = new Thickness(1),
                Padding = new Thickness(5),
                MinWidth = Math.Max(ActualWidth, 160),
                Effect = new System.Windows.Media.Effects.DropShadowEffect
                {
                    BlurRadius = 20,
                    ShadowDepth = 4,
                    Direction = 270,
                    Opacity = 0.18,
                    Color = T.C("#1B2A3A"),
                },
                Child = scroll,
            };
            popup.Child = frame;
            _openPopup = popup;
            popup.IsOpen = true;
        }
    }

    /// <summary>左侧导航项：图标 + 文字；收起时只留图标。</summary>
    class NavItem : Border
    {
        readonly TextBlock _label;
        readonly TextBlock _icon;
        public readonly string PageId;
        readonly Border _bar;
        bool _active;

        public event EventHandler Activated;

        public NavItem(string glyph, string label, string pageId)
        {
            PageId = pageId;
            Height = 42;
            CornerRadius = new CornerRadius(8);
            Background = Brushes.Transparent;
            Cursor = Cursors.Hand;
            Margin = new Thickness(8, 2, 8, 2);

            var g = new Grid();
            g.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(40) });
            g.ColumnDefinitions.Add(new ColumnDefinition());
            _icon = T.Icon(glyph, 17, T.Muted);
            _icon.HorizontalAlignment = HorizontalAlignment.Center;
            g.Children.Add(_icon);
            _label = T.Text(label, 13, T.Ink2);
            _label.Margin = new Thickness(2, 0, 10, 0);
            Grid.SetColumn(_label, 1);
            g.Children.Add(_label);

            _bar = new Border
            {
                Width = 3,
                Height = 18,
                CornerRadius = new CornerRadius(2),
                Background = new SolidColorBrush(T.Accent),
                HorizontalAlignment = HorizontalAlignment.Left,
                VerticalAlignment = VerticalAlignment.Center,
                Visibility = Visibility.Collapsed,
            };
            // 用 Grid 叠一层，保证竖条覆盖在左侧
            var overlay = new Grid();
            g.IsHitTestVisible = false;
            _bar.IsHitTestVisible = false;
            overlay.Children.Add(g);
            overlay.Children.Add(_bar);
            Child = overlay;

            MouseEnter += delegate { if (!_active) Background = T.B("#12000000"); };
            MouseLeave += delegate { if (!_active) Background = Brushes.Transparent; };
            MouseLeftButtonUp += delegate
            {
                if (Activated != null)
                {
                    Activated(this, EventArgs.Empty);
                }
            };
        }

        public void SetActive(bool active)
        {
            _active = active;
            Background = active ? T.B("#1A0F6CBD") : Brushes.Transparent;
            _icon.Foreground = new SolidColorBrush(active ? T.Accent : T.Muted);
            _label.Foreground = new SolidColorBrush(active ? T.Ink : T.Ink2);
            _label.FontWeight = active ? FontWeights.SemiBold : FontWeights.Normal;
            _bar.Visibility = active ? Visibility.Visible : Visibility.Collapsed;
        }

        public void SetCollapsed(bool collapsed)
        {
            _label.Visibility = collapsed ? Visibility.Collapsed : Visibility.Visible;
            ToolTip = collapsed ? _label.Text : null;
        }
    }

    static class Layout
    {
        public static Grid Columns(params double[] widths)
        {
            var g = new Grid();
            foreach (double w in widths)
            {
                if (w <= 0)
                {
                    g.ColumnDefinitions.Add(new ColumnDefinition());
                }
                else
                {
                    g.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(w) });
                }
            }
            return g;
        }

        public static Grid Rows(params double[] heights)
        {
            var g = new Grid();
            foreach (double h in heights)
            {
                if (h <= 0)
                {
                    g.RowDefinitions.Add(new RowDefinition());
                }
                else
                {
                    g.RowDefinitions.Add(new RowDefinition { Height = new GridLength(h) });
                }
            }
            return g;
        }

        public static StackPanel VStack(double gap)
        {
            return new StackPanel { Orientation = Orientation.Vertical, Margin = new Thickness(0) };
        }

        public static StackPanel HStack(double gap)
        {
            return new StackPanel { Orientation = Orientation.Horizontal };
        }
    }
}
