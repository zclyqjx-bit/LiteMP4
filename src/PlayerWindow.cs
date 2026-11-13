using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Input;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Shell;
using System.Windows.Threading;
using Microsoft.Win32;

[assembly: AssemblyTitle("轻播 Lite")]
[assembly: AssemblyDescription("精简的 Windows 多格式视频播放器")]
[assembly: AssemblyProduct("轻播 Lite")]
[assembly: AssemblyVersion("1.7.0.0")]
[assembly: AssemblyFileVersion("1.7.0.0")]

namespace LiteMp4
{
    internal static class Program
    {
        [STAThread]
        public static void Main(string[] args)
        {
            Application app = new Application();
            app.ShutdownMode = ShutdownMode.OnMainWindowClose;
            PlayerWindow window = new PlayerWindow();
            window.SyncLogPath = Environment.GetEnvironmentVariable("LITEMP4_SYNC_LOG");
            if (args.Length > 0)
                window.Loaded += delegate
                {
                    if (args.Length == 1)
                        window.OpenPath(args[0]);
                    else
                        window.OpenFiles(args);
                };
            app.Run(window);
        }
    }

    public sealed class PlayerWindow : Window
    {
        public string SyncLogPath { get; set; }

        private static readonly Brush WindowBrush = MakeBrush("#FF0D1117");
        private static readonly Brush PanelBrush = MakeBrush("#FF151B23");
        private static readonly Brush TextBrush = MakeBrush("#FFF2F5F7");
        private static readonly Brush MutedBrush = MakeBrush("#FF8B96A3");
        private static readonly Brush AccentBrush = MakeBrush("#FF45D69E");
        private static readonly Brush AccentHoverBrush = MakeBrush("#FF69E5B6");
        private static readonly Brush ButtonBrush = MakeBrush("#00151B23");
        private static readonly Brush ButtonHoverBrush = MakeBrush("#FF29333E");
        private static readonly Brush ButtonPressedBrush = MakeBrush("#FF35424F");
        private static readonly Brush CloseHoverBrush = MakeBrush("#FFE81123");
        private static readonly double[] Rates = { 0.5, 0.75, 1.0, 1.25, 1.5, 2.0 };
        private static readonly HashSet<string> SupportedExtensions = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            ".mp4", ".m4v", ".mkv", ".mov", ".avi", ".wmv", ".flv", ".webm",
            ".ts", ".m2ts", ".mts", ".mpg", ".mpeg", ".mpe", ".mpv", ".m2v",
            ".vob", ".3gp", ".3g2", ".rm", ".rmvb", ".asf", ".divx", ".f4v", ".ogv"
        };
        private const string VideoFileFilter =
            "常见视频 (*.mp4;*.m4v;*.mkv;*.mov;*.avi;*.wmv;*.flv;*.webm;*.ts;*.m2ts;*.mts;*.mpg;*.mpeg;*.mpe;*.mpv;*.m2v;*.vob;*.3gp;*.3g2;*.rm;*.rmvb;*.asf;*.divx;*.f4v;*.ogv)|*.mp4;*.m4v;*.mkv;*.mov;*.avi;*.wmv;*.flv;*.webm;*.ts;*.m2ts;*.mts;*.mpg;*.mpeg;*.mpe;*.mpv;*.m2v;*.vob;*.3gp;*.3g2;*.rm;*.rmvb;*.asf;*.divx;*.f4v;*.ogv|所有文件 (*.*)|*.*";

        private MediaElement media;
        private readonly DispatcherTimer uiTimer;
        private readonly DispatcherTimer nextTrackTimer;
        private readonly DispatcherTimer openTimer;
        private readonly RangeBar seekBar;
        private readonly RangeBar volumeBar;
        private readonly TextBlock fileText;
        private readonly TextBlock timeText;
        private readonly TextBlock stateGlyph;
        private readonly TextBlock stateTitle;
        private readonly TextBlock stateDetail;
        private readonly Button stateOpenButton;
        private readonly Button playButton;
        private readonly TextBlock playGlyph;
        private readonly Button stopButton;
        private readonly Button previousButton;
        private readonly Button nextButton;
        private readonly Button speedButton;
        private readonly Button muteButton;
        private readonly Button repeatButton;
        private readonly Grid statePanel;
        private readonly Grid videoArea;
        private readonly Grid titleBar;
        private readonly Border controlsPanel;
        private readonly Border bufferingBadge;
        private readonly RowDefinition titleRow;
        private readonly TextBlock maximizeGlyph;
        private readonly WindowChrome chrome;
        private Button topmostButton;
        private Button playlistToggleButton;
        private bool userTopmost;
        private bool repeatTrack;
        private ColumnDefinition playlistColumn;
        private Border playlistPanel;
        private ListBox playlistListBox;
        private TextBlock playlistTitleText;
        private MenuItem playSelectedMenuItem;
        private MenuItem deleteSelectedMenuItem;
        private MenuItem clearPlaylistMenuItem;
        private bool playlistVisible;
        private bool playlistVisibleBeforeFullscreen;
        private const int TrayMessage = 0x8064;
        private IntPtr trayIconHandle;
        private bool ownsTrayIcon;
        private bool trayIconAdded;
        private bool minimizedToTray;
        private WindowState stateBeforeTray = WindowState.Normal;

        private string currentPath;
        private readonly List<string> playlist = new List<string>();
        private int currentIndex = -1;
        private TimeSpan duration;
        private double rate = 1.0;
        private double lastVolume = 0.7;
        private bool hasMedia;
        private bool isPlaying;
        private bool isOpening;
        private bool ended;
        private bool isFullscreen;
        private bool isClosing;
        private bool muted;
        private bool useMpv;
        private bool qualityReduced;
        private bool qualityOutputConfirmed;
        private bool skipSoftwareScale;
        private int syncSampleCounter;
        private ProcessPriorityClass originalPriority;
        private bool playbackPriorityRaised;
        private MpvPlayer mpv;
        private MpvHost mpvHost;
        private WindowState stateBeforeFullscreen = WindowState.Normal;

        public PlayerWindow()
        {
            Title = "轻播 Lite";
            originalPriority = Process.GetCurrentProcess().PriorityClass;
            Width = 960;
            Height = 600;
            MinWidth = 560;
            MinHeight = 360;
            WindowStartupLocation = WindowStartupLocation.CenterScreen;
            WindowStyle = WindowStyle.None;
            AllowsTransparency = false;
            Background = WindowBrush;
            Foreground = TextBrush;
            FontFamily = new FontFamily("Microsoft YaHei UI");
            UseLayoutRounding = true;
            SnapsToDevicePixels = true;
            AllowDrop = true;

            chrome = new WindowChrome
            {
                CaptionHeight = 44,
                ResizeBorderThickness = new Thickness(6),
                GlassFrameThickness = new Thickness(0),
                CornerRadius = new CornerRadius(0),
                UseAeroCaptionButtons = false
            };
            WindowChrome.SetWindowChrome(this, chrome);
            SourceInitialized += OnSourceInitialized;

            Grid root = new Grid();
            root.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            playlistColumn = new ColumnDefinition { Width = new GridLength(0) };
            root.ColumnDefinitions.Add(playlistColumn);
            titleRow = new RowDefinition { Height = new GridLength(44) };
            root.RowDefinitions.Add(titleRow);
            root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
            root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            Content = root;

            titleBar = BuildTitleBar(out fileText, out maximizeGlyph);
            Grid.SetColumnSpan(titleBar, 2);
            root.Children.Add(titleBar);

            videoArea = new Grid { Background = Brushes.Black, ClipToBounds = true };
            Grid.SetRow(videoArea, 1);
            root.Children.Add(videoArea);

            media = CreateNativeMedia();
            videoArea.Children.Add(media);

            BuildStatePanel(videoArea, out statePanel, out stateGlyph, out stateTitle,
                out stateDetail, out stateOpenButton);

            bufferingBadge = new Border
            {
                Background = MakeBrush("#CC151B23"),
                CornerRadius = new CornerRadius(5),
                Padding = new Thickness(12, 6, 12, 6),
                HorizontalAlignment = HorizontalAlignment.Center,
                VerticalAlignment = VerticalAlignment.Top,
                Margin = new Thickness(0, 18, 0, 0),
                Visibility = Visibility.Collapsed,
                IsHitTestVisible = false,
                Child = MakeText("缓冲中…", 12, TextBrush)
            };
            videoArea.Children.Add(bufferingBadge);

            BuildControls(root, out controlsPanel, out seekBar, out volumeBar, out timeText,
                out playButton, out playGlyph, out stopButton, out previousButton, out nextButton,
                out speedButton, out repeatButton, out muteButton);
            Grid.SetColumnSpan(controlsPanel, 2);
            BuildPlaylistPanel(root);
            UpdatePlaylistLayout();

            uiTimer = new DispatcherTimer(DispatcherPriority.Background);
            uiTimer.Interval = TimeSpan.FromMilliseconds(250);
            uiTimer.Tick += delegate { UpdateTimeline(); };
            nextTrackTimer = new DispatcherTimer(DispatcherPriority.Normal);
            nextTrackTimer.Interval = TimeSpan.FromMilliseconds(700);
            nextTrackTimer.Tick += OnAutoNextTick;
            openTimer = new DispatcherTimer(DispatcherPriority.Normal);
            openTimer.Interval = TimeSpan.FromSeconds(4);
            openTimer.Tick += OnOpenTimeout;

            seekBar.ValueChangedByUser += SeekToRatio;
            volumeBar.ValueChangedByUser += delegate(double value) { SetVolume(value, true); };
            stateOpenButton.Click += delegate { ShowOpenDialog(); };
            playButton.Click += delegate { TogglePlay(); };
            stopButton.Click += delegate { StopPlayback(); };
            previousButton.Click += delegate { PlayPrevious(); };
            nextButton.Click += delegate { PlayNext(); };
            speedButton.Click += delegate { ChangeRate(1); };
            muteButton.Click += delegate { ToggleMute(); };

            videoArea.MouseLeftButtonDown += OnVideoMouseDown;
            PreviewKeyDown += OnPreviewKeyDown;
            DragEnter += OnDragEnter;
            DragOver += OnDragEnter;
            Drop += OnDrop;
            Closing += OnWindowClosing;
            StateChanged += OnWindowStateChanged;
            Loaded += delegate { Keyboard.Focus(this); };

            UpdateTopmostButton();
            UpdateRepeatButton();
            ResetTransport();
            SetVolume(lastVolume, true);
            ShowWelcome();
        }

        private Grid BuildTitleBar(out TextBlock nameText, out TextBlock maxGlyph)
        {
            Grid bar = new Grid { Background = PanelBrush };
            bar.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            bar.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            bar.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

            StackPanel brand = new StackPanel
            {
                Orientation = Orientation.Horizontal,
                Margin = new Thickness(14, 0, 8, 0),
                VerticalAlignment = VerticalAlignment.Center
            };
            Border logo = new Border
            {
                Width = 24,
                Height = 24,
                CornerRadius = new CornerRadius(6),
                Background = AccentBrush,
                Child = new TextBlock
                {
                    Text = "▶", FontSize = 10, Foreground = MakeBrush("#FF092018"),
                    HorizontalAlignment = HorizontalAlignment.Center,
                    VerticalAlignment = VerticalAlignment.Center,
                    Margin = new Thickness(2, 0, 0, 0)
                }
            };
            brand.Children.Add(logo);
            TextBlock brandText = MakeText("轻播", 14, TextBrush);
            brandText.FontWeight = FontWeights.SemiBold;
            brandText.Margin = new Thickness(8, 0, 14, 0);
            brandText.VerticalAlignment = VerticalAlignment.Center;
            brand.Children.Add(brandText);
            Button open = CreateButton("打开 ▾", "打开文件或文件夹", "打开视频",
                ButtonBrush, ButtonHoverBrush, ButtonPressedBrush);
            open.Height = 28;
            open.Padding = new Thickness(11, 0, 11, 0);
            ContextMenu openMenu = CreateOpenMenu(open);
            open.ContextMenu = openMenu;
            open.Click += delegate { openMenu.IsOpen = true; };
            brand.Children.Add(open);

            topmostButton = CreateButton("置顶", "窗口置顶 / 取消置顶 (T)", "置顶切换",
                ButtonBrush, ButtonHoverBrush, ButtonPressedBrush);
            topmostButton.Height = 28;
            topmostButton.Width = 68;
            topmostButton.Margin = new Thickness(6, 0, 0, 0);
            topmostButton.Click += delegate { ToggleTopmost(); };
            brand.Children.Add(topmostButton);

            playlistToggleButton = CreateButton("列表", "显示 / 隐藏播放列表 (L)", "播放列表切换",
                ButtonBrush, ButtonHoverBrush, ButtonPressedBrush);
            playlistToggleButton.Height = 28;
            playlistToggleButton.Width = 64;
            playlistToggleButton.Margin = new Thickness(6, 0, 0, 0);
            playlistToggleButton.Click += delegate { TogglePlaylist(); };
            brand.Children.Add(playlistToggleButton);
            bar.Children.Add(brand);

            nameText = MakeText("原生播放 · 轻量无广告", 12, MutedBrush);
            nameText.HorizontalAlignment = HorizontalAlignment.Center;
            nameText.VerticalAlignment = VerticalAlignment.Center;
            nameText.TextTrimming = TextTrimming.CharacterEllipsis;
            nameText.Margin = new Thickness(12, 0, 12, 0);
            Grid.SetColumn(nameText, 1);
            bar.Children.Add(nameText);

            StackPanel windowButtons = new StackPanel { Orientation = Orientation.Horizontal };
            Grid.SetColumn(windowButtons, 2);
            Button minimize = CreateWindowButton("", "最小化", ButtonHoverBrush);
            minimize.Click += delegate { WindowState = WindowState.Minimized; };
            maxGlyph = new TextBlock
            {
                Text = "", FontFamily = new FontFamily("Segoe MDL2 Assets"), FontSize = 10,
                HorizontalAlignment = HorizontalAlignment.Center,
                VerticalAlignment = VerticalAlignment.Center
            };
            Button maximize = CreateWindowButton("", "最大化 / 还原", ButtonHoverBrush);
            maximize.Content = maxGlyph;
            maximize.Click += delegate { ToggleMaximize(); };
            Button close = CreateWindowButton("", "关闭", CloseHoverBrush);
            close.Click += delegate { Close(); };
            windowButtons.Children.Add(minimize);
            windowButtons.Children.Add(maximize);
            windowButtons.Children.Add(close);
            bar.Children.Add(windowButtons);

            bar.MouseLeftButtonDown += delegate(object sender, MouseButtonEventArgs e)
            {
                if (e.ClickCount == 2)
                    ToggleMaximize();
                else if (e.LeftButton == MouseButtonState.Pressed)
                    DragMove();
            };
            return bar;
        }

        private void BuildStatePanel(Grid parent, out Grid panel, out TextBlock glyph,
            out TextBlock title, out TextBlock detail, out Button openButton)
        {
            panel = new Grid { Background = WindowBrush };
            StackPanel content = new StackPanel
            {
                HorizontalAlignment = HorizontalAlignment.Center,
                VerticalAlignment = VerticalAlignment.Center,
                MaxWidth = 620
            };
            Border icon = new Border
            {
                Width = 68, Height = 68, CornerRadius = new CornerRadius(20),
                Background = MakeBrush("#FF183D32"),
                HorizontalAlignment = HorizontalAlignment.Center,
                Child = new TextBlock
                {
                    FontSize = 27, Foreground = AccentBrush,
                    HorizontalAlignment = HorizontalAlignment.Center,
                    VerticalAlignment = VerticalAlignment.Center
                }
            };
            glyph = (TextBlock)icon.Child;
            content.Children.Add(icon);
            title = MakeText("", 24, TextBrush);
            title.FontWeight = FontWeights.SemiBold;
            title.HorizontalAlignment = HorizontalAlignment.Center;
            title.Margin = new Thickness(0, 22, 0, 0);
            content.Children.Add(title);
            detail = MakeText("", 12, MutedBrush);
            detail.TextWrapping = TextWrapping.Wrap;
            detail.TextAlignment = TextAlignment.Center;
            detail.LineHeight = 21;
            detail.Margin = new Thickness(24, 12, 24, 0);
            content.Children.Add(detail);
            openButton = CreateButton("选择视频文件", "选择本地视频", "打开视频",
                AccentBrush, AccentHoverBrush, AccentBrush);
            openButton.Foreground = MakeBrush("#FF092018");
            openButton.FontWeight = FontWeights.SemiBold;
            openButton.Padding = new Thickness(22, 0, 22, 0);
            openButton.Height = 38;
            openButton.Margin = new Thickness(0, 24, 0, 0);
            openButton.HorizontalAlignment = HorizontalAlignment.Center;
            content.Children.Add(openButton);
            panel.Children.Add(content);

            TextBlock codecHint = MakeText("多文件连续播放 · 高分辨率同步优先 · 降低帧率与输出质量", 11, MutedBrush);
            codecHint.HorizontalAlignment = HorizontalAlignment.Center;
            codecHint.VerticalAlignment = VerticalAlignment.Bottom;
            codecHint.Margin = new Thickness(16, 0, 16, 22);
            panel.Children.Add(codecHint);
            parent.Children.Add(panel);
        }

        private void BuildPlaylistPanel(Grid root)
        {
            playlistPanel = new Border
            {
                Width = 270,
                Background = PanelBrush,
                BorderBrush = MakeBrush("#FF2B3540"),
                BorderThickness = new Thickness(1, 0, 0, 0),
                Visibility = Visibility.Collapsed,
                ClipToBounds = true
            };
            Grid.SetRow(playlistPanel, 1);
            Grid.SetColumn(playlistPanel, 1);
            Grid layout = new Grid();
            layout.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            layout.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
            layout.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            playlistPanel.Child = layout;

            Grid header = new Grid { Margin = new Thickness(12, 8, 8, 8) };
            header.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            header.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            playlistTitleText = MakeText("播放列表 (0)", 13, TextBrush);
            playlistTitleText.FontWeight = FontWeights.SemiBold;
            playlistTitleText.VerticalAlignment = VerticalAlignment.Center;
            header.Children.Add(playlistTitleText);
            Button hide = CreateButton("隐藏", "隐藏播放列表 (L)", "隐藏播放列表",
                ButtonBrush, ButtonHoverBrush, ButtonPressedBrush);
            hide.Height = 28;
            hide.Width = 46;
            Grid.SetColumn(hide, 1);
            hide.Click += delegate { TogglePlaylist(); };
            header.Children.Add(hide);
            layout.Children.Add(header);

            playlistListBox = new ListBox
            {
                Background = PanelBrush,
                Foreground = TextBrush,
                BorderThickness = new Thickness(0),
                SelectionMode = SelectionMode.Extended,
                HorizontalContentAlignment = HorizontalAlignment.Stretch,
                ItemContainerStyle = CreatePlaylistItemStyle()
            };
            ScrollViewer.SetVerticalScrollBarVisibility(playlistListBox, ScrollBarVisibility.Auto);
            AutomationProperties.SetName(playlistListBox, "视频播放列表");
            playlistListBox.MouseDoubleClick += OnPlaylistDoubleClick;
            playlistListBox.PreviewMouseRightButtonDown += OnPlaylistRightButtonDown;
            playlistListBox.SelectionChanged += OnPlaylistSelectionChanged;
            Grid.SetRow(playlistListBox, 1);
            layout.Children.Add(playlistListBox);

            TextBlock hint = MakeText("Shift/Ctrl 多选 · 双击播放 · L 隐藏", 11, MutedBrush);
            hint.Margin = new Thickness(12, 5, 12, 10);
            hint.HorizontalAlignment = HorizontalAlignment.Center;
            Grid.SetRow(hint, 2);
            layout.Children.Add(hint);
            root.Children.Add(playlistPanel);
            ContextMenu playlistMenu = CreatePlaylistContextMenu();
            playlistPanel.ContextMenu = playlistMenu;
            playlistListBox.ContextMenu = playlistMenu;
        }

        private static Style CreatePlaylistItemStyle()
        {
            Style style = new Style(typeof(ListBoxItem));
            style.Setters.Add(new Setter(ListBoxItem.BackgroundProperty, Brushes.Transparent));
            style.Setters.Add(new Setter(ListBoxItem.ForegroundProperty, TextBrush));
            style.Setters.Add(new Setter(ListBoxItem.PaddingProperty, new Thickness(11, 7, 11, 7)));
            style.Setters.Add(new Setter(ListBoxItem.FontSizeProperty, 12.0));
            style.Setters.Add(new Setter(ListBoxItem.CursorProperty, Cursors.Hand));
            style.Setters.Add(new Setter(ListBoxItem.HorizontalContentAlignmentProperty, HorizontalAlignment.Stretch));

            ControlTemplate template = new ControlTemplate(typeof(ListBoxItem));
            FrameworkElementFactory border = new FrameworkElementFactory(typeof(Border), "ItemBorder");
            border.SetValue(Border.BackgroundProperty, new TemplateBindingExtension(ListBoxItem.BackgroundProperty));
            border.SetValue(Border.PaddingProperty, new TemplateBindingExtension(ListBoxItem.PaddingProperty));
            FrameworkElementFactory content = new FrameworkElementFactory(typeof(ContentPresenter));
            content.SetValue(ContentPresenter.HorizontalAlignmentProperty, HorizontalAlignment.Left);
            content.SetValue(ContentPresenter.VerticalAlignmentProperty, VerticalAlignment.Center);
            border.AppendChild(content);
            template.VisualTree = border;
            Trigger hover = new Trigger { Property = ListBoxItem.IsMouseOverProperty, Value = true };
            hover.Setters.Add(new Setter(Border.BackgroundProperty, MakeBrush("#FF29333E"), "ItemBorder"));
            template.Triggers.Add(hover);
            Trigger selected = new Trigger { Property = ListBoxItem.IsSelectedProperty, Value = true };
            selected.Setters.Add(new Setter(Border.BackgroundProperty, MakeBrush("#FF285245"), "ItemBorder"));
            template.Triggers.Add(selected);
            style.Setters.Add(new Setter(ListBoxItem.TemplateProperty, template));
            return style;
        }

        private ContextMenu CreateOpenMenu(Button owner)
        {
            ContextMenu menu = new ContextMenu
            {
                PlacementTarget = owner,
                Placement = PlacementMode.Bottom,
                Background = PanelBrush,
                BorderBrush = MakeBrush("#FF2B3540"),
                BorderThickness = new Thickness(1),
                Padding = new Thickness(4),
                MinWidth = 120,
                HasDropShadow = false
            };
            Style itemStyle = CreatePlaylistMenuItemStyle();
            menu.Items.Add(CreateMenuItem("文件", itemStyle, ShowOpenDialog));
            menu.Items.Add(CreateMenuItem("文件夹", itemStyle, ShowOpenFolderDialog));
            return menu;
        }

        private ContextMenu CreatePlaylistContextMenu()
        {
            ContextMenu menu = new ContextMenu
            {
                Background = PanelBrush,
                BorderBrush = MakeBrush("#FF2B3540"),
                BorderThickness = new Thickness(1),
                Padding = new Thickness(4),
                MinWidth = 160,
                HasDropShadow = false
            };
            Style itemStyle = CreatePlaylistMenuItemStyle();
            MenuItem addFiles = CreateMenuItem("添加播放文件", itemStyle, ShowAddFilesDialog);
            MenuItem addFolder = CreateMenuItem("添加播放文件夹", itemStyle, ShowAddFolderDialog);
            playSelectedMenuItem = CreateMenuItem("播放选定文件", itemStyle, PlaySelectedItems);
            deleteSelectedMenuItem = CreateMenuItem("删除选定的文件", itemStyle, DeleteSelectedPlaylistItem);
            clearPlaylistMenuItem = CreateMenuItem("清空播放列表", itemStyle, ClearPlaylist);
            menu.Items.Add(addFiles);
            menu.Items.Add(addFolder);
            menu.Items.Add(playSelectedMenuItem);
            menu.Items.Add(deleteSelectedMenuItem);
            menu.Items.Add(clearPlaylistMenuItem);
            menu.Opened += delegate
            {
                playSelectedMenuItem.IsEnabled = playlistListBox.SelectedItems.Count > 0;
                deleteSelectedMenuItem.IsEnabled = playlistListBox.SelectedItems.Count > 0;
                clearPlaylistMenuItem.IsEnabled = playlist.Count > 0;
            };
            return menu;
        }

        private static MenuItem CreateMenuItem(string header, Style style, Action action)
        {
            MenuItem item = new MenuItem { Header = header, Style = style };
            item.Click += delegate { action(); };
            return item;
        }

        private static Style CreatePlaylistMenuItemStyle()
        {
            Style style = new Style(typeof(MenuItem));
            style.Setters.Add(new Setter(MenuItem.ForegroundProperty, TextBrush));
            style.Setters.Add(new Setter(MenuItem.BackgroundProperty, PanelBrush));
            style.Setters.Add(new Setter(MenuItem.PaddingProperty, new Thickness(12, 6, 12, 6)));
            style.Setters.Add(new Setter(MenuItem.FontSizeProperty, 12.0));
            style.Setters.Add(new Setter(MenuItem.CursorProperty, Cursors.Hand));
            ControlTemplate template = new ControlTemplate(typeof(MenuItem));
            FrameworkElementFactory border = new FrameworkElementFactory(typeof(Border), "MenuBorder");
            border.SetValue(Border.BackgroundProperty, new TemplateBindingExtension(MenuItem.BackgroundProperty));
            border.SetValue(Border.PaddingProperty, new TemplateBindingExtension(MenuItem.PaddingProperty));
            FrameworkElementFactory content = new FrameworkElementFactory(typeof(ContentPresenter));
            content.SetValue(ContentPresenter.ContentProperty, new TemplateBindingExtension(MenuItem.HeaderProperty));
            content.SetValue(ContentPresenter.ContentTemplateProperty, new TemplateBindingExtension(MenuItem.HeaderTemplateProperty));
            content.SetValue(ContentPresenter.HorizontalAlignmentProperty, HorizontalAlignment.Left);
            content.SetValue(ContentPresenter.VerticalAlignmentProperty, VerticalAlignment.Center);
            border.AppendChild(content);
            template.VisualTree = border;
            Trigger hover = new Trigger { Property = MenuItem.IsHighlightedProperty, Value = true };
            hover.Setters.Add(new Setter(Border.BackgroundProperty, ButtonHoverBrush, "MenuBorder"));
            template.Triggers.Add(hover);
            Trigger disabled = new Trigger { Property = MenuItem.IsEnabledProperty, Value = false };
            disabled.Setters.Add(new Setter(Border.OpacityProperty, 0.35, "MenuBorder"));
            template.Triggers.Add(disabled);
            style.Setters.Add(new Setter(MenuItem.TemplateProperty, template));
            return style;
        }

        private void BuildControls(Grid root, out Border panel, out RangeBar seek,
            out RangeBar volume, out TextBlock clock, out Button play, out TextBlock playIcon,
            out Button stop, out Button previous, out Button next, out Button speed, out Button repeat, out Button mute)
        {
            panel = new Border { Background = PanelBrush, Padding = new Thickness(16, 7, 16, 11) };
            Grid.SetRow(panel, 2);
            Grid layout = new Grid();
            layout.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            layout.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            layout.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            panel.Child = layout;
            root.Children.Add(panel);

            seek = new RangeBar(false) { Height = 24, Cursor = Cursors.Hand };
            seek.ToolTip = "点击或拖动跳转（松开时执行）";
            AutomationProperties.SetName(seek, "播放进度");
            layout.Children.Add(seek);

            Grid transport = new Grid { Margin = new Thickness(0, 3, 0, 0) };
            transport.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            transport.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            transport.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            Grid.SetRow(transport, 1);
            layout.Children.Add(transport);

            TextBlock credit = MakeText("By 沂州小帅   Email:zclyqjx@163.com", 9, MutedBrush);
            credit.HorizontalAlignment = HorizontalAlignment.Right;
            credit.Margin = new Thickness(0, 3, 0, 0);
            credit.IsHitTestVisible = false;
            AutomationProperties.SetName(credit, "作者信息");
            Grid.SetRow(credit, 2);
            layout.Children.Add(credit);

            StackPanel left = new StackPanel { Orientation = Orientation.Horizontal };
            play = CreateButton("▶", "播放 / 暂停 (空格)", "播放或暂停",
                AccentBrush, AccentHoverBrush, AccentBrush);
            play.Width = 44;
            play.Foreground = MakeBrush("#FF092018");
            playIcon = new TextBlock
            {
                Text = "▶", FontSize = 16, FontFamily = new FontFamily("Segoe UI Symbol"),
                HorizontalAlignment = HorizontalAlignment.Center,
                VerticalAlignment = VerticalAlignment.Center
            };
            play.Content = playIcon;
            left.Children.Add(play);

            stop = CreateButton("■", "停止并回到片头", "停止",
                ButtonBrush, ButtonHoverBrush, ButtonPressedBrush);
            stop.Margin = new Thickness(5, 0, 0, 0);
            stop.FontFamily = new FontFamily("Segoe UI Symbol");
            left.Children.Add(stop);
            previous = CreateButton("上一", "上一个视频 (PageUp)", "上一个视频",
                ButtonBrush, ButtonHoverBrush, ButtonPressedBrush);
            previous.Width = 42;
            previous.FontSize = 11;
            previous.Margin = new Thickness(5, 0, 0, 0);
            left.Children.Add(previous);
            next = CreateButton("下一", "下一个视频 (PageDown)", "下一个视频",
                ButtonBrush, ButtonHoverBrush, ButtonPressedBrush);
            next.Width = 42;
            next.FontSize = 11;
            next.Margin = new Thickness(5, 0, 0, 0);
            left.Children.Add(next);
            clock = MakeText("00:00 / 00:00", 12, MutedBrush);
            clock.FontFamily = new FontFamily("Consolas");
            clock.VerticalAlignment = VerticalAlignment.Center;
            clock.Margin = new Thickness(14, 0, 0, 0);
            left.Children.Add(clock);
            transport.Children.Add(left);

            TextBlock shortcuts = MakeText("空格  播放 / 暂停     ← →  快退 / 快进", 10, MutedBrush);
            shortcuts.HorizontalAlignment = HorizontalAlignment.Center;
            shortcuts.VerticalAlignment = VerticalAlignment.Center;
            Grid.SetColumn(shortcuts, 1);
            transport.Children.Add(shortcuts);

            StackPanel right = new StackPanel { Orientation = Orientation.Horizontal };
            Grid.SetColumn(right, 2);
            speed = CreateButton("1×", "切换倍速 [ 和 ]", "播放倍速",
                ButtonBrush, ButtonHoverBrush, ButtonPressedBrush);
            speed.Width = 48;
            right.Children.Add(speed);
            repeat = CreateButton("单曲", "单曲循环 (R)", "单曲循环",
                ButtonBrush, ButtonHoverBrush, ButtonPressedBrush);
            repeat.Width = 52;
            repeat.FontSize = 11;
            repeat.Click += delegate { ToggleRepeat(); };
            right.Children.Add(repeat);
            mute = CreateButton("音量", "静音 / 恢复 (M)", "静音",
                ButtonBrush, ButtonHoverBrush, ButtonPressedBrush);
            mute.Width = 46;
            mute.FontSize = 11;
            right.Children.Add(mute);
            volume = new RangeBar(true)
            {
                Width = 76, Height = 34, Ratio = lastVolume,
                Cursor = Cursors.Hand, Margin = new Thickness(2, 0, 5, 0)
            };
            volume.ToolTip = "音量（↑ / ↓）";
            AutomationProperties.SetName(volume, "音量");
            right.Children.Add(volume);
            Button fullscreen = CreateButton("⛶", "全屏 (F / F11，Esc 退出)", "全屏",
                ButtonBrush, ButtonHoverBrush, ButtonPressedBrush);
            fullscreen.Width = 38;
            fullscreen.FontFamily = new FontFamily("Segoe UI Symbol");
            fullscreen.FontSize = 18;
            fullscreen.Click += delegate { ToggleFullscreen(); };
            right.Children.Add(fullscreen);
            transport.Children.Add(right);
        }

        private MediaElement CreateNativeMedia()
        {
            MediaElement element = new MediaElement
            {
                LoadedBehavior = MediaState.Manual,
                UnloadedBehavior = MediaState.Manual,
                ScrubbingEnabled = true,
                Stretch = Stretch.Uniform,
                Volume = lastVolume,
                Focusable = false
            };
            element.MediaOpened += OnMediaOpened;
            element.MediaEnded += OnMediaEnded;
            element.MediaFailed += OnMediaFailed;
            element.BufferingStarted += OnNativeBufferingStarted;
            element.BufferingEnded += OnNativeBufferingEnded;
            return element;
        }

        private void ReplaceNativeMedia()
        {
            MediaElement oldMedia = media;
            if (oldMedia != null)
            {
                oldMedia.MediaOpened -= OnMediaOpened;
                oldMedia.MediaEnded -= OnMediaEnded;
                oldMedia.MediaFailed -= OnMediaFailed;
                oldMedia.BufferingStarted -= OnNativeBufferingStarted;
                oldMedia.BufferingEnded -= OnNativeBufferingEnded;
                videoArea.Children.Remove(oldMedia);
            }
            media = CreateNativeMedia();
            media.IsMuted = muted;
            videoArea.Children.Insert(0, media);
        }

        private void OnNativeBufferingStarted(object sender, RoutedEventArgs e)
        {
            if (ReferenceEquals(sender, media) && !useMpv)
                bufferingBadge.Visibility = Visibility.Visible;
        }

        private void OnNativeBufferingEnded(object sender, RoutedEventArgs e)
        {
            if (ReferenceEquals(sender, media) && !useMpv)
                bufferingBadge.Visibility = Visibility.Collapsed;
        }

        private void ShowOpenDialog()
        {
            OpenFileDialog dialog = new OpenFileDialog
            {
                Title = "选择视频文件（可多选）",
                Filter = VideoFileFilter,
                CheckFileExists = true,
                Multiselect = true,
                RestoreDirectory = true
            };
            if (dialog.ShowDialog(this) == true)
                OpenFiles(dialog.FileNames);
        }

        private void ShowOpenFolderDialog()
        {
            string folder = ChooseFolder();
            if (String.IsNullOrEmpty(folder))
                return;
            try
            {
                string[] files = Directory.GetFiles(folder, "*", SearchOption.AllDirectories);
                Array.Sort(files, new NaturalFileComparer());
                OpenFiles(files);
            }
            catch (Exception error)
            {
                MessageBox.Show(this, "无法打开所选文件夹：\n" + error.Message, "轻播 Lite",
                    MessageBoxButton.OK, MessageBoxImage.Information);
            }
        }

        private void ShowAddFilesDialog()
        {
            OpenFileDialog dialog = new OpenFileDialog
            {
                Title = "添加视频到当前播放列表",
                Filter = VideoFileFilter,
                CheckFileExists = true,
                Multiselect = true,
                RestoreDirectory = true
            };
            if (dialog.ShowDialog(this) == true)
                AddFiles(dialog.FileNames);
        }

        private void ShowAddFolderDialog()
        {
            string folder = ChooseFolder();
            if (String.IsNullOrEmpty(folder))
                return;
            try
            {
                string[] files = Directory.GetFiles(folder, "*", SearchOption.AllDirectories);
                Array.Sort(files, new NaturalFileComparer());
                AddFiles(files);
            }
            catch (Exception error)
            {
                MessageBox.Show(this, "无法读取所选文件夹：\n" + error.Message, "轻播 Lite",
                    MessageBoxButton.OK, MessageBoxImage.Information);
            }
        }

        private void AddFiles(IEnumerable<string> paths)
        {
            if (isClosing || paths == null)
                return;
            int rejected;
            List<string> validFiles = GetValidFiles(paths, out rejected);
            if (validFiles.Count == 0)
            {
                MessageBox.Show(this, "没有找到可添加的视频文件。", "轻播 Lite",
                    MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            bool startPlayback = playlist.Count == 0 || currentIndex < 0;
            playlist.AddRange(validFiles);
            playlistVisible = true;
            if (startPlayback)
                currentIndex = 0;
            UpdatePlaylistView();
            if (startPlayback)
                OpenCurrentTrack();
            if (rejected > 0)
                fileText.ToolTip = currentPath + "\n已忽略 " + rejected.ToString(CultureInfo.InvariantCulture) + " 个无效文件";
        }

        private void ClearPlaylist()
        {
            ReleaseMedia();
            ReplaceNativeMedia();
            playlist.Clear();
            currentIndex = -1;
            currentPath = null;
            fileText.Text = "原生播放 · 轻量无广告";
            Title = "轻播 Lite";
            ResetTransport();
            UpdatePlaylistView();
            ShowWelcome();
        }

        private void PlaySelectedItems()
        {
            List<int> selectedIndices = GetSelectedIndices();
            if (selectedIndices.Count == 0)
                return;
            List<string> selectedPaths = BuildSelectedPaths(playlist, selectedIndices);

            nextTrackTimer.Stop();
            playlist.Clear();
            playlist.AddRange(selectedPaths);
            currentIndex = 0;
            UpdatePlaylistView();
            OpenCurrentTrack();
        }

        private static List<string> BuildSelectedPaths(List<string> source, List<int> indices)
        {
            List<string> selectedPaths = new List<string>();
            for (int i = 0; i < indices.Count; i++)
                selectedPaths.Add(source[indices[i]]);
            return selectedPaths;
        }

        private List<int> GetSelectedIndices()
        {
            List<int> indices = new List<int>();
            foreach (ListBoxItem item in playlistListBox.SelectedItems)
            {
                if (item.Tag is int)
                    indices.Add((int)item.Tag);
            }
            indices.Sort();
            return indices;
        }

        private static int CountRemovedBefore(List<int> removed, int originalIndex)
        {
            int count = 0;
            for (int i = 0; i < removed.Count; i++)
            {
                if (removed[i] < originalIndex)
                    count++;
            }
            return count;
        }

        private void DeleteSelectedPlaylistItem()
        {
            List<int> removed = GetSelectedIndices();
            if (removed.Count == 0)
                return;
            int oldCurrent = currentIndex;
            bool removedCurrent = removed.Contains(oldCurrent);
            int nextOriginal = -1;
            if (removedCurrent)
            {
                for (int i = oldCurrent + 1; i < playlist.Count; i++)
                {
                    if (!removed.Contains(i))
                    {
                        nextOriginal = i;
                        break;
                    }
                }
                if (nextOriginal < 0)
                {
                    for (int i = oldCurrent - 1; i >= 0; i--)
                    {
                        if (!removed.Contains(i))
                        {
                            nextOriginal = i;
                            break;
                        }
                    }
                }
            }

            for (int i = removed.Count - 1; i >= 0; i--)
                playlist.RemoveAt(removed[i]);
            if (playlist.Count == 0)
            {
                ClearPlaylist();
                return;
            }

            if (removedCurrent)
            {
                if (nextOriginal < 0)
                {
                    ClearPlaylist();
                    return;
                }
                currentIndex = nextOriginal - CountRemovedBefore(removed, nextOriginal);
                UpdatePlaylistView();
                OpenCurrentTrack();
            }
            else
            {
                currentIndex = oldCurrent - CountRemovedBefore(removed, oldCurrent);
                UpdatePlaylistView();
                UpdatePlaylistSelection();
            }
        }

        public void OpenPath(string path)
        {
            if (isClosing || String.IsNullOrWhiteSpace(path))
                return;
            string fullPath;
            try
            {
                fullPath = Path.GetFullPath(path);
            }
            catch (Exception ex)
            {
                MessageBox.Show(this, "文件路径无效：\n" + ex.Message, "轻播 Lite",
                    MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }
            if (!File.Exists(fullPath))
            {
                MessageBox.Show(this, "找不到视频文件：\n" + fullPath, "轻播 Lite",
                    MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }
            if (!IsSupportedFile(fullPath))
            {
                MessageBox.Show(this, "请选择支持的视频文件（MP4、MKV、MOV、AVI、WebM 等）。", "轻播 Lite",
                    MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            OpenFiles(new string[] { fullPath });
        }

        public void OpenFiles(IEnumerable<string> paths)
        {
            if (isClosing || paths == null)
                return;
            int rejected;
            List<string> validFiles = GetValidFiles(paths, out rejected);
            if (validFiles.Count == 0)
            {
                MessageBox.Show(this, "找不到视频文件，或所选文件格式不受支持。", "轻播 Lite",
                    MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            nextTrackTimer.Stop();
            playlist.Clear();
            playlist.AddRange(validFiles);
            currentIndex = 0;
            UpdatePlaylistView();
            OpenCurrentTrack();
            if (rejected > 0)
                fileText.ToolTip = currentPath + "\n已忽略 " + rejected.ToString(CultureInfo.InvariantCulture) + " 个无效文件";
        }

        private void TogglePlaylist()
        {
            playlistVisible = !playlistVisible;
            if (isFullscreen)
                playlistVisibleBeforeFullscreen = playlistVisible;
            UpdatePlaylistLayout();
            if (playlistVisible)
                UpdatePlaylistSelection();
        }

        private void UpdatePlaylistLayout()
        {
            if (playlistColumn == null || playlistPanel == null || playlistToggleButton == null)
                return;
            playlistColumn.Width = new GridLength(playlistVisible ? 270 : 0);
            playlistPanel.Visibility = playlistVisible ? Visibility.Visible : Visibility.Collapsed;
            playlistToggleButton.Content = playlistVisible ? "隐藏列表" : "列表";
            playlistToggleButton.Foreground = playlistVisible ? AccentBrush : TextBrush;
            playlistToggleButton.ToolTip = playlistVisible ? "隐藏播放列表 (L)" : "显示播放列表 (L)";
        }

        private void UpdatePlaylistView()
        {
            if (playlistListBox == null)
                return;
            playlistListBox.Items.Clear();
            for (int i = 0; i < playlist.Count; i++)
            {
                string display = (i + 1).ToString("00", CultureInfo.InvariantCulture) + "  " +
                    Path.GetFileName(playlist[i]);
                TextBlock text = MakeText(display, 12, TextBrush);
                text.TextTrimming = TextTrimming.CharacterEllipsis;
                ListBoxItem item = new ListBoxItem
                {
                    Content = text,
                    Tag = i,
                    ToolTip = playlist[i]
                };
                AutomationProperties.SetName(item, display);
                playlistListBox.Items.Add(item);
            }
            if (playlist.Count > 1)
                playlistVisible = true;
            UpdatePlaylistLayout();
            UpdatePlaylistSelection();
        }

        private void OnPlaylistSelectionChanged(object sender, SelectionChangedEventArgs e)
        {
            UpdatePlaylistHeader();
        }

        private void UpdatePlaylistHeader()
        {
            if (playlistTitleText == null)
                return;
            playlistTitleText.Text = "播放列表 (" + playlist.Count.ToString(CultureInfo.InvariantCulture) + ")";
            if (playlistListBox.SelectedItems.Count > 1)
            {
                playlistTitleText.Text += " · 已选 " +
                    playlistListBox.SelectedItems.Count.ToString(CultureInfo.InvariantCulture) + " 项";
            }
        }

        private void UpdatePlaylistSelection()
        {
            if (playlistListBox == null || playlistTitleText == null)
                return;
            int selected = currentIndex >= 0 && currentIndex < playlistListBox.Items.Count ? currentIndex : -1;
            playlistListBox.SelectedIndex = selected;
            if (selected >= 0)
                playlistListBox.ScrollIntoView(playlistListBox.SelectedItem);
            UpdatePlaylistHeader();
        }

        private void OnPlaylistRightButtonDown(object sender, MouseButtonEventArgs e)
        {
            ListBoxItem item = FindAncestor<ListBoxItem>(e.OriginalSource as DependencyObject);
            if (item != null && !playlistListBox.SelectedItems.Contains(item))
                playlistListBox.SelectedItem = item;
        }

        private static T FindAncestor<T>(DependencyObject current) where T : DependencyObject
        {
            while (current != null)
            {
                if (current is T)
                    return (T)current;
                current = VisualTreeHelper.GetParent(current);
            }
            return null;
        }

        private void OnPlaylistDoubleClick(object sender, MouseButtonEventArgs e)
        {
            ListBoxItem item = playlistListBox.SelectedItem as ListBoxItem;
            if (item != null && item.Tag is int)
            {
                int index = (int)item.Tag;
                if (index >= 0 && index < playlist.Count)
                {
                    currentIndex = index;
                    OpenCurrentTrack();
                }
            }
            Keyboard.Focus(this);
            e.Handled = true;
        }

        private string GetFileDisplayName()
        {
            string name = Path.GetFileName(currentPath);
            if (playlist.Count <= 1)
                return name;
            return "[" + (currentIndex + 1).ToString(CultureInfo.InvariantCulture) + "/" +
                playlist.Count.ToString(CultureInfo.InvariantCulture) + "] " + name;
        }

        private void OpenCurrentTrack()
        {
            if (currentIndex < 0 || currentIndex >= playlist.Count)
                return;
            nextTrackTimer.Stop();
            string fullPath = playlist[currentIndex];
            ReleaseMedia();
            ReplaceNativeMedia();
            currentPath = fullPath;
            fileText.Text = GetFileDisplayName();
            fileText.ToolTip = fullPath;
            Title = Path.GetFileName(fullPath) + " - 轻播 Lite";
            isOpening = true;
            openTimer.Start();
            UpdatePlaylistButtons();
            UpdatePlaylistSelection();
            ShowState("···", "正在打开视频", Path.GetFileName(fullPath), false);
            try
            {
                media.Source = new Uri(fullPath, UriKind.Absolute);
                media.Play();
            }
            catch (Exception ex)
            {
                ShowMediaError(ex);
            }
        }

        private void OnAutoNextTick(object sender, EventArgs e)
        {
            nextTrackTimer.Stop();
            if (currentIndex + 1 < playlist.Count)
            {
                currentIndex++;
                OpenCurrentTrack();
            }
        }

        private void PlayNext()
        {
            nextTrackTimer.Stop();
            if (currentIndex + 1 < playlist.Count)
            {
                currentIndex++;
                OpenCurrentTrack();
            }
        }

        private void PlayPrevious()
        {
            nextTrackTimer.Stop();
            if (currentIndex > 0)
            {
                currentIndex--;
                OpenCurrentTrack();
            }
            else if (hasMedia)
            {
                SeekToRatio(0.0);
            }
        }

        private void UpdatePlaylistButtons()
        {
            if (previousButton == null || nextButton == null)
                return;
            previousButton.IsEnabled = currentIndex > 0;
            nextButton.IsEnabled = currentIndex >= 0 && currentIndex + 1 < playlist.Count;
        }

        private static bool IsMpvRuntimeAvailable()
        {
            string runtime = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "runtime");
            return File.Exists(Path.Combine(runtime, "libmpv-2.dll")) &&
                File.Exists(Path.Combine(runtime, "vulkan-1.dll"));
        }

        private static List<string> GetValidFiles(IEnumerable<string> paths, out int rejected)
        {
            List<string> validFiles = new List<string>();
            rejected = 0;
            foreach (string path in paths)
            {
                try
                {
                    if (String.IsNullOrWhiteSpace(path))
                    {
                        rejected++;
                        continue;
                    }
                    string fullPath = Path.GetFullPath(path);
                    if (File.Exists(fullPath) && IsSupportedFile(fullPath))
                        validFiles.Add(fullPath);
                    else
                        rejected++;
                }
                catch (Exception)
                {
                    rejected++;
                }
            }
            return validFiles;
        }

        private static bool IsSupportedFile(string path)
        {
            return SupportedExtensions.Contains(Path.GetExtension(path));
        }

        private void ReleaseMedia()
        {
            openTimer.Stop();
            nextTrackTimer.Stop();
            uiTimer.Stop();
            RestorePlaybackPriority();
            ReleaseMpv();
            media.Visibility = Visibility.Visible;
            isPlaying = false;
            isOpening = false;
            hasMedia = false;
            ended = false;
            duration = TimeSpan.Zero;
            bufferingBadge.Visibility = Visibility.Collapsed;
            qualityReduced = false;
            qualityOutputConfirmed = false;
            skipSoftwareScale = false;
            syncSampleCounter = 0;
            AutomationProperties.SetHelpText(fileText, String.Empty);
            try
            {
                if (media.Source != null)
                {
                    media.Stop();
                    media.Close();
                    media.Source = null;
                }
            }
            catch (InvalidOperationException) { }
            ResetTransport();
        }

        private void OnMediaOpened(object sender, RoutedEventArgs e)
        {
            if (isClosing || !isOpening || useMpv || !ReferenceEquals(sender, media))
                return;
            openTimer.Stop();
            try
            {
                if ((media.NaturalVideoWidth > 1920 || media.NaturalVideoHeight > 1080) && IsMpvRuntimeAvailable())
                {
                    string qualityBackendError;
                    if (TryStartMpv(out qualityBackendError))
                        return;
                    ShowMediaError(new InvalidOperationException("高分辨率流畅模式启动失败：" + qualityBackendError));
                    return;
                }
                duration = media.NaturalDuration.HasTimeSpan
                    ? media.NaturalDuration.TimeSpan : TimeSpan.Zero;
                hasMedia = true;
                isOpening = false;
                ended = false;
                stopButton.IsEnabled = true;
                statePanel.Visibility = Visibility.Collapsed;
                media.SpeedRatio = rate;
                SetVolume(volumeBar.Ratio, false);
                media.Play();
                isPlaying = true;
                playGlyph.Text = "❚❚";
                playButton.ToolTip = "暂停 (空格)";
                UpdateTimeline();
                uiTimer.Start();
            }
            catch (Exception ex)
            {
                ShowMediaError(ex);
            }
        }

        private void OnMediaEnded(object sender, RoutedEventArgs e)
        {
            if (ReferenceEquals(sender, media) && !useMpv)
                FinishPlayback();
        }

        private void OnOpenTimeout(object sender, EventArgs e)
        {
            openTimer.Stop();
            if (isClosing || !isOpening || useMpv)
                return;
            string fallbackError;
            if (TryStartMpv(out fallbackError))
                return;
            ShowMediaError(new InvalidOperationException("系统播放后端打开超时。\n" + fallbackError));
        }

        private void OnMediaFailed(object sender, ExceptionRoutedEventArgs e)
        {
            if (!ReferenceEquals(sender, media))
                return;
            if (useMpv || isClosing)
                return;
            string fallbackError;
            if (TryStartMpv(out fallbackError))
                return;
            string nativeError = e.ErrorException == null ? "系统解码失败" : e.ErrorException.Message;
            ShowMediaError(new InvalidOperationException(nativeError + "\n" + fallbackError));
        }

        private bool TryStartMpv(out string fallbackError)
        {
            fallbackError = null;
            openTimer.Stop();
            try
            {
                useMpv = true;
                media.Stop();
                media.Close();
                media.Source = null;
                media.Visibility = Visibility.Collapsed;
                mpvHost = new MpvHost();
                mpvHost.Activated += delegate { Keyboard.Focus(this); };
                mpvHost.DoubleClicked += delegate { if (hasMedia) ToggleFullscreen(); };
                videoArea.Children.Insert(1, mpvHost);
                videoArea.UpdateLayout();
                if (mpvHost.Handle == IntPtr.Zero)
                    throw new InvalidOperationException("视频嵌入窗口尚未创建完成。");

                mpv = new MpvPlayer(mpvHost.Handle);
                mpv.Loaded += OnMpvLoaded;
                mpv.Ended += OnMpvEnded;
                mpv.Failed += OnMpvFailed;
                mpv.PauseChanged += OnMpvPauseChanged;
                mpv.BufferingChanged += OnMpvBufferingChanged;
                mpv.DurationChanged += OnMpvDurationChanged;
                mpv.SetRate(rate);
                mpv.SetVolume(volumeBar.Ratio);
                mpv.SetMuted(muted);
                ShowState("···", "正在以兼容模式打开",
                    "高分辨率同步优先 · 降低帧率与输出质量 · 音频缓冲 1.5 秒", false);
                mpv.Load(currentPath);
                return true;
            }
            catch (Exception error)
            {
                fallbackError = error.Message;
                ReleaseMpv();
                media.Visibility = Visibility.Visible;
                return false;
            }
        }

        private void RaisePlaybackPriority()
        {
            if (playbackPriorityRaised)
                return;
            try
            {
                Process.GetCurrentProcess().PriorityClass = ProcessPriorityClass.AboveNormal;
                playbackPriorityRaised = true;
            }
            catch (System.ComponentModel.Win32Exception) { }
            catch (InvalidOperationException) { }
        }

        private void RestorePlaybackPriority()
        {
            if (!playbackPriorityRaised)
                return;
            playbackPriorityRaised = false;
            try
            {
                Process.GetCurrentProcess().PriorityClass = originalPriority;
            }
            catch (System.ComponentModel.Win32Exception) { }
            catch (InvalidOperationException) { }
        }

        private void ReleaseMpv()
        {
            useMpv = false;
            MpvPlayer oldPlayer = mpv;
            mpv = null;
            if (oldPlayer != null)
                oldPlayer.Dispose();
            if (mpvHost != null)
            {
                videoArea.Children.Remove(mpvHost);
                mpvHost.Dispose();
                mpvHost = null;
            }
        }

        private void OnMpvLoaded()
        {
            if (!useMpv || mpv == null || isClosing || !isOpening)
                return;
            openTimer.Stop();
            try
            {
                duration = TimeSpan.FromSeconds(Math.Max(0.0, mpv.Duration));
                string qualityHint = "兼容模式：libmpv · 音频优先同步 · 慢速硬件自动丢帧";
                double sourceWidth = mpv.VideoWidth;
                double sourceHeight = mpv.VideoHeight;
                if (sourceWidth > 0.0 && (sourceWidth > 1920.0 || sourceHeight > 1080.0))
                {
                    RaisePlaybackPriority();
                    string codec = mpv.VideoCodec;
                    skipSoftwareScale = String.Equals(codec, "hevc", StringComparison.OrdinalIgnoreCase) ||
                        String.Equals(codec, "h265", StringComparison.OrdinalIgnoreCase);
                    mpv.EnableReducedQuality(codec);
                    qualityReduced = true;
                    qualityOutputConfirmed = false;
                    syncSampleCounter = 0;
                    fileText.Text = GetFileDisplayName() + (skipSoftwareScale ? " · 同步优先" : " · 正在降画质");
                    qualityHint = skipSoftwareScale
                        ? "HEVC 同步优先：跳过量产非参考帧 · 限制 12 fps · 音频缓冲 1.5 秒"
                        : "高分辨率流畅模式：15 fps · 960 宽 / 8-bit · 音频缓冲 1.5 秒";
                }
                else
                {
                    qualityReduced = false;
                    skipSoftwareScale = false;
                }
                hasMedia = true;
                isOpening = false;
                ended = false;
                isPlaying = true;
                stopButton.IsEnabled = true;
                statePanel.Visibility = Visibility.Collapsed;
                Keyboard.Focus(this);
                fileText.ToolTip = currentPath + "\n" + qualityHint;
                mpv.SetRate(rate);
                mpv.SetVolume(volumeBar.Ratio);
                mpv.SetMuted(muted);
                mpv.SetPaused(false);
                playGlyph.Text = "❚❚";
                playButton.ToolTip = "暂停 (空格)";
                UpdateTimeline();
                uiTimer.Start();
            }
            catch (Exception error)
            {
                ShowMediaError(error);
            }
        }

        private void UpdateQualityDisplay()
        {
            if (!useMpv || mpv == null || !qualityReduced || qualityOutputConfirmed)
                return;
            double width = mpv.OutputVideoWidth;
            double height = mpv.OutputVideoHeight;
            if (skipSoftwareScale)
            {
                double frameRate = mpv.EstimatedVideoFrameRate;
                if (width <= 0.0 || height <= 0.0 || frameRate <= 0.0 || frameRate > 15.5)
                    return;
                qualityOutputConfirmed = true;
                fileText.Text = GetFileDisplayName() + " · 同步优先 " +
                    frameRate.ToString("0.0", CultureInfo.InvariantCulture) + " fps";
                fileText.ToolTip = currentPath + "\nHEVC 同步优先：跳过量产非参考帧 · 实际 " +
                    frameRate.ToString("0.0", CultureInfo.InvariantCulture) +
                    " fps · GPU 缩放至窗口 · 音频缓冲 1.5 秒";
                return;
            }
            if (width <= 0.0 || width > 960.5 || height <= 0.0)
                return;
            int actualWidth = (int)Math.Round(width);
            int actualHeight = (int)Math.Round(height);
            qualityOutputConfirmed = true;
            fileText.Text = GetFileDisplayName() + " · 流畅 " +
                actualWidth.ToString(CultureInfo.InvariantCulture) + "×" +
                actualHeight.ToString(CultureInfo.InvariantCulture) + " / 8-bit";
            fileText.ToolTip = currentPath + "\n高分辨率流畅模式：实际输出 " +
                actualWidth.ToString(CultureInfo.InvariantCulture) + "×" +
                actualHeight.ToString(CultureInfo.InvariantCulture) + " / 8-bit · 15 fps · 音频缓冲 1.5 秒";
        }

        private void OnMpvFailed(string error)
        {
            if (useMpv && !isClosing)
                ShowMediaError(new InvalidOperationException(error));
        }

        private void OnMpvEnded()
        {
            if (useMpv)
                FinishPlayback();
        }

        private void FinishPlayback()
        {
            if (!hasMedia || ended)
                return;
            if (repeatTrack)
            {
                ReplayCurrentTrack();
                return;
            }
            isPlaying = false;
            ended = true;
            uiTimer.Stop();
            bufferingBadge.Visibility = Visibility.Collapsed;
            seekBar.Ratio = 1.0;
            timeText.Text = FormatTime(duration) + " / " + FormatTime(duration);
            playGlyph.Text = "↻";
            bool hasNext = currentIndex >= 0 && currentIndex + 1 < playlist.Count;
            playButton.ToolTip = hasNext ? "即将播放下一个；空格可重播当前" : "重新播放 (空格)";
            if (hasNext)
                nextTrackTimer.Start();
        }

        private void ReplayCurrentTrack()
        {
            nextTrackTimer.Stop();
            ended = false;
            try
            {
                if (useMpv && mpv != null)
                {
                    mpv.Seek(0.0);
                    mpv.SetPaused(false);
                }
                else
                {
                    media.Position = TimeSpan.Zero;
                    media.Play();
                }
                isPlaying = true;
                playGlyph.Text = "❚❚";
                playButton.ToolTip = "暂停 (空格)";
                seekBar.Ratio = 0.0;
                UpdateTimeline();
                uiTimer.Start();
            }
            catch (Exception error)
            {
                ShowMediaError(error);
            }
        }

        private void OnMpvPauseChanged(bool paused)
        {
            if (!useMpv || !hasMedia || ended)
                return;
            isPlaying = !paused;
            playGlyph.Text = isPlaying ? "❚❚" : "▶";
            playButton.ToolTip = isPlaying ? "暂停 (空格)" : "播放 (空格)";
            if (isPlaying)
                uiTimer.Start();
            else
                uiTimer.Stop();
        }

        private void OnMpvBufferingChanged(bool buffering)
        {
            if (useMpv && hasMedia)
                bufferingBadge.Visibility = buffering ? Visibility.Visible : Visibility.Collapsed;
        }

        private void OnMpvDurationChanged(double seconds)
        {
            if (!useMpv || seconds <= 0.0 || Double.IsNaN(seconds) || Double.IsInfinity(seconds))
                return;
            duration = TimeSpan.FromSeconds(seconds);
            UpdateTimeline();
        }

        private void ShowMediaError(Exception error)
        {
            openTimer.Stop();
            nextTrackTimer.Stop();
            uiTimer.Stop();
            RestorePlaybackPriority();
            ReleaseMpv();
            media.Visibility = Visibility.Visible;
            qualityReduced = false;
            qualityOutputConfirmed = false;
            skipSoftwareScale = false;
            syncSampleCounter = 0;
            AutomationProperties.SetHelpText(fileText, String.Empty);
            isPlaying = false;
            isOpening = false;
            hasMedia = false;
            ended = false;
            duration = TimeSpan.Zero;
            ResetTransport();
            string name = String.IsNullOrEmpty(currentPath) ? "" : Path.GetFileName(currentPath);
            fileText.Text = GetFileDisplayName();
            ShowState("!", "无法播放此视频",
                name + "\n系统与兼容后端均无法解码。请保持 runtime 文件夹完整，并检查文件是否损坏。", true);
            stateDetail.ToolTip = error == null ? "未知解码错误" : error.Message;
        }

        private void ShowWelcome()
        {
            ShowState("▶", "轻一点，专注播放",
                "多格式视频 · 高分辨率同步优先 · 音频缓冲 1.5 秒\n可多选或批量拖入视频连续播放，Ctrl + O 打开", true);
        }

        private void ShowState(string glyph, string title, string detail, bool showOpen)
        {
            stateGlyph.Text = glyph;
            stateTitle.Text = title;
            stateDetail.Text = detail;
            stateDetail.ToolTip = null;
            stateOpenButton.Visibility = showOpen ? Visibility.Visible : Visibility.Collapsed;
            statePanel.Visibility = Visibility.Visible;
            bufferingBadge.Visibility = Visibility.Collapsed;
        }

        private void TogglePlay()
        {
            nextTrackTimer.Stop();
            if (!hasMedia)
            {
                if (!isOpening)
                    ShowOpenDialog();
                return;
            }
            try
            {
                if (isPlaying)
                {
                    if (useMpv && mpv != null)
                        mpv.SetPaused(true);
                    else
                        media.Pause();
                    isPlaying = false;
                    uiTimer.Stop();
                    playGlyph.Text = "▶";
                    playButton.ToolTip = "播放 (空格)";
                }
                else
                {
                    if (ended)
                    {
                        if (useMpv && mpv != null)
                            mpv.Seek(0.0);
                        else
                            media.Position = TimeSpan.Zero;
                        ended = false;
                    }
                    if (useMpv && mpv != null)
                        mpv.SetPaused(false);
                    else
                        media.Play();
                    isPlaying = true;
                    playGlyph.Text = "❚❚";
                    playButton.ToolTip = "暂停 (空格)";
                    uiTimer.Start();
                }
                UpdateTimeline();
            }
            catch (Exception ex)
            {
                ShowMediaError(ex);
            }
        }

        private void StopPlayback()
        {
            nextTrackTimer.Stop();
            if (!hasMedia)
                return;
            try
            {
                if (useMpv && mpv != null)
                {
                    mpv.SetPaused(true);
                    mpv.Seek(0.0);
                }
                else
                {
                    media.Stop();
                    media.Position = TimeSpan.Zero;
                }
            }
            catch (InvalidOperationException) { }
            isPlaying = false;
            ended = false;
            uiTimer.Stop();
            ResetTransport();
        }

        private void SeekToRatio(double ratio)
        {
            nextTrackTimer.Stop();
            if (!hasMedia || duration <= TimeSpan.Zero)
                return;
            ratio = Math.Max(0.0, Math.Min(1.0, ratio));
            try
            {
                TimeSpan target = TimeSpan.FromTicks((long)(duration.Ticks * ratio));
                if (useMpv && mpv != null)
                    mpv.Seek(target.TotalSeconds);
                else
                    media.Position = target;
                if (ended && ratio < 1.0)
                    ended = false;
                seekBar.Ratio = ratio;
                if (!isPlaying)
                {
                    playGlyph.Text = "▶";
                    playButton.ToolTip = "播放 (空格)";
                }
                UpdateTimeline();
            }
            catch (InvalidOperationException) { }
        }

        private void SeekRelative(double seconds)
        {
            if (!hasMedia || duration <= TimeSpan.Zero)
                return;
            double baseSeconds = ended ? duration.TotalSeconds :
                (useMpv && mpv != null ? mpv.Position : media.Position.TotalSeconds);
            double target = Math.Max(0.0, Math.Min(duration.TotalSeconds, baseSeconds + seconds));
            SeekToRatio(target / duration.TotalSeconds);
        }

        private void ChangeRate(int direction)
        {
            int index = Array.IndexOf(Rates, rate);
            if (index < 0)
                index = 2;
            index = (index + direction + Rates.Length) % Rates.Length;
            double previous = rate;
            rate = Rates[index];
            try
            {
                if (hasMedia)
                {
                    if (useMpv && mpv != null)
                        mpv.SetRate(rate);
                    else
                        media.SpeedRatio = rate;
                }
                speedButton.Content = rate.ToString("0.##", CultureInfo.InvariantCulture) + "×";
            }
            catch (InvalidOperationException)
            {
                rate = previous;
            }
        }

        private void SetVolume(double value, bool unmute)
        {
            value = Math.Max(0.0, Math.Min(1.0, value));
            if (value > 0.0)
                lastVolume = value;
            volumeBar.Ratio = value;
            if (unmute && value > 0.0)
                muted = false;
            ApplyAudioState();
            UpdateMuteButton();
        }

        private void ApplyAudioState()
        {
            try
            {
                if (useMpv && mpv != null)
                {
                    mpv.SetVolume(volumeBar.Ratio);
                    mpv.SetMuted(muted);
                }
                else
                {
                    media.Volume = volumeBar.Ratio;
                    media.IsMuted = muted;
                }
            }
            catch (InvalidOperationException) { }
        }

        private void ToggleMute()
        {
            if (muted || volumeBar.Ratio <= 0.0)
            {
                if (volumeBar.Ratio <= 0.0)
                    SetVolume(lastVolume, false);
                muted = false;
            }
            else
            {
                muted = true;
            }
            ApplyAudioState();
            UpdateMuteButton();
        }

        private void UpdateMuteButton()
        {
            bool silent = muted || volumeBar.Ratio <= 0.0;
            muteButton.Content = silent ? "静音" : "音量";
            muteButton.Foreground = silent ? AccentBrush : TextBrush;
            volumeBar.Opacity = silent ? 0.45 : 1.0;
        }

        private void UpdateTimeline()
        {
            if (!hasMedia || duration <= TimeSpan.Zero || seekBar.IsDragging)
                return;
            if (useMpv && qualityReduced && !qualityOutputConfirmed)
                UpdateQualityDisplay();
            if (useMpv && mpv != null && (syncSampleCounter++ % 4) == 0)
            {
                double syncMilliseconds = Math.Abs(mpv.AudioVideoSync * 1000.0);
                double frameRate = mpv.EstimatedVideoFrameRate;
                string tooltip = fileText.ToolTip as string;
                AutomationProperties.SetHelpText(fileText,
                    (String.IsNullOrEmpty(tooltip) ? currentPath : tooltip) +
                    "\nA/V偏差 " + syncMilliseconds.ToString("0", CultureInfo.InvariantCulture) +
                    " ms · 输出 " + frameRate.ToString("0.0", CultureInfo.InvariantCulture) + " fps");
                WriteSyncLog(syncMilliseconds, frameRate);
            }
            try
            {
                TimeSpan position = ended ? duration :
                    (useMpv && mpv != null ? TimeSpan.FromSeconds(Math.Max(0.0, mpv.Position)) : media.Position);
                if (position < TimeSpan.Zero)
                    position = TimeSpan.Zero;
                if (position > duration)
                    position = duration;
                seekBar.Ratio = position.TotalSeconds / duration.TotalSeconds;
                timeText.Text = FormatTime(position) + " / " + FormatTime(duration);
            }
            catch (InvalidOperationException) { }
        }

        private void WriteSyncLog(double syncMilliseconds, double frameRate)
        {
            if (String.IsNullOrEmpty(SyncLogPath))
                return;
            try
            {
                string title = (fileText.Text ?? String.Empty).Replace("|", "/");
                string contents = mpv.Position.ToString("0.###", CultureInfo.InvariantCulture) + "|" +
                    syncMilliseconds.ToString("0", CultureInfo.InvariantCulture) + "|" +
                    frameRate.ToString("0.0", CultureInfo.InvariantCulture) + "|" + title;
                File.WriteAllText(SyncLogPath, contents, Encoding.UTF8);
            }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }

        private void ResetTransport()
        {
            seekBar.Ratio = 0.0;
            timeText.Text = "00:00 / 00:00";
            playGlyph.Text = "▶";
            playButton.ToolTip = hasMedia ? "播放 (空格)" : "打开视频 (空格)";
            stopButton.IsEnabled = hasMedia;
            UpdatePlaylistButtons();
        }

        private static string FormatTime(TimeSpan value)
        {
            int seconds = Math.Max(0, (int)value.TotalSeconds);
            int hours = seconds / 3600;
            int minutes = (seconds / 60) % 60;
            seconds %= 60;
            return hours > 0
                ? String.Format(CultureInfo.InvariantCulture, "{0:00}:{1:00}:{2:00}", hours, minutes, seconds)
                : String.Format(CultureInfo.InvariantCulture, "{0:00}:{1:00}", minutes, seconds);
        }

        private void OnPreviewKeyDown(object sender, KeyEventArgs e)
        {
            if (playlistListBox != null && playlistListBox.IsKeyboardFocusWithin &&
                (e.Key == Key.Left || e.Key == Key.Right || e.Key == Key.Up ||
                 e.Key == Key.Down || e.Key == Key.Space || e.Key == Key.Home || e.Key == Key.End))
                return;
            if ((Keyboard.Modifiers & ModifierKeys.Control) != 0 && e.Key == Key.O)
            {
                if (!e.IsRepeat)
                    ShowOpenDialog();
                e.Handled = true;
                return;
            }

            switch (e.Key)
            {
                case Key.Space:
                case Key.MediaPlayPause:
                    if (!e.IsRepeat)
                        TogglePlay();
                    break;
                case Key.MediaStop:
                    StopPlayback();
                    break;
                case Key.Left:
                    SeekRelative((Keyboard.Modifiers & ModifierKeys.Shift) != 0 ? -30 : -5);
                    break;
                case Key.Right:
                    SeekRelative((Keyboard.Modifiers & ModifierKeys.Shift) != 0 ? 30 : 5);
                    break;
                case Key.Up:
                    SetVolume(volumeBar.Ratio + 0.05, true);
                    break;
                case Key.Down:
                    SetVolume(volumeBar.Ratio - 0.05, true);
                    break;
                case Key.M:
                    if (!e.IsRepeat)
                        ToggleMute();
                    break;
                case Key.T:
                    if (!e.IsRepeat)
                        ToggleTopmost();
                    break;
                case Key.L:
                    if (!e.IsRepeat)
                        TogglePlaylist();
                    break;
                case Key.R:
                    if (!e.IsRepeat)
                        ToggleRepeat();
                    break;
                case Key.F:
                case Key.F11:
                    if (!e.IsRepeat && hasMedia)
                        ToggleFullscreen();
                    break;
                case Key.Escape:
                    if (isFullscreen)
                        ToggleFullscreen();
                    break;
                case Key.OemOpenBrackets:
                    if (!e.IsRepeat)
                        ChangeRate(-1);
                    break;
                case Key.OemCloseBrackets:
                    if (!e.IsRepeat)
                        ChangeRate(1);
                    break;
                case Key.PageUp:
                    PlayPrevious();
                    break;
                case Key.PageDown:
                    PlayNext();
                    break;
                case Key.Home:
                    SeekToRatio(0.0);
                    break;
                default:
                    return;
            }
            e.Handled = true;
        }

        private void ToggleRepeat()
        {
            repeatTrack = !repeatTrack;
            UpdateRepeatButton();
        }

        private void UpdateRepeatButton()
        {
            if (repeatButton == null)
                return;
            repeatButton.Content = repeatTrack ? "循环中" : "单曲";
            repeatButton.Foreground = repeatTrack ? AccentBrush : TextBrush;
            repeatButton.ToolTip = repeatTrack ? "取消单曲循环 (R)" : "开启单曲循环 (R)";
        }

        private void ToggleTopmost()
        {
            userTopmost = !userTopmost;
            if (!isFullscreen)
                Topmost = userTopmost;
            UpdateTopmostButton();
        }

        private void UpdateTopmostButton()
        {
            if (topmostButton == null)
                return;
            topmostButton.Content = userTopmost ? "取消置顶" : "置顶";
            topmostButton.Foreground = userTopmost ? AccentBrush : TextBrush;
            topmostButton.ToolTip = userTopmost ? "取消置顶 (T)" : "窗口置顶 (T)";
        }

        private void ToggleMaximize()
        {
            if (isFullscreen)
            {
                ToggleFullscreen();
                return;
            }
            WindowState = WindowState == WindowState.Maximized
                ? WindowState.Normal : WindowState.Maximized;
        }

        private void ToggleFullscreen()
        {
            isFullscreen = !isFullscreen;
            if (isFullscreen)
            {
                stateBeforeFullscreen = WindowState;
                playlistVisibleBeforeFullscreen = playlistVisible;
                playlistVisible = false;
                UpdatePlaylistLayout();
                titleBar.Visibility = Visibility.Collapsed;
                controlsPanel.Visibility = Visibility.Collapsed;
                titleRow.Height = new GridLength(0);
                chrome.CaptionHeight = 0;
                chrome.ResizeBorderThickness = new Thickness(0);
                ResizeMode = ResizeMode.NoResize;
                WindowChrome.SetWindowChrome(this, null);
                Topmost = true;
                WindowState = WindowState.Maximized;
            }
            else
            {
                Topmost = userTopmost;
                WindowState = stateBeforeFullscreen == WindowState.Maximized
                    ? WindowState.Maximized : WindowState.Normal;
                ResizeMode = ResizeMode.CanResize;
                WindowChrome.SetWindowChrome(this, chrome);
                chrome.CaptionHeight = 44;
                chrome.ResizeBorderThickness = new Thickness(6);
                titleRow.Height = new GridLength(44);
                titleBar.Visibility = Visibility.Visible;
                controlsPanel.Visibility = Visibility.Visible;
                playlistVisible = playlistVisibleBeforeFullscreen;
                UpdatePlaylistLayout();
            }
        }

        private void OnVideoMouseDown(object sender, MouseButtonEventArgs e)
        {
            if (e.ClickCount == 2 && hasMedia)
            {
                ToggleFullscreen();
                e.Handled = true;
            }
        }

        private void OnDragEnter(object sender, DragEventArgs e)
        {
            e.Effects = GetDroppedVideos(e.Data).Count == 0 ? DragDropEffects.None : DragDropEffects.Copy;
            e.Handled = true;
        }

        private void OnDrop(object sender, DragEventArgs e)
        {
            List<string> files = GetDroppedVideos(e.Data);
            if (files.Count > 0)
                OpenFiles(files);
            e.Handled = true;
        }

        private static List<string> GetDroppedVideos(IDataObject data)
        {
            List<string> result = new List<string>();
            if (!data.GetDataPresent(DataFormats.FileDrop))
                return result;
            string[] files = data.GetData(DataFormats.FileDrop) as string[];
            if (files == null)
                return result;
            for (int i = 0; i < files.Length; i++)
            {
                if (IsSupportedFile(files[i]))
                    result.Add(files[i]);
            }
            return result;
        }

        private string ChooseFolder()
        {
            IntPtr pidl = IntPtr.Zero;
            IntPtr display = Marshal.AllocHGlobal(520);
            IntPtr title = Marshal.StringToHGlobalUni("选择要添加到播放列表的文件夹");
            try
            {
                Marshal.WriteByte(display, 0);
                BROWSEINFO info = new BROWSEINFO();
                info.hwndOwner = new WindowInteropHelper(this).Handle;
                info.pidlRoot = IntPtr.Zero;
                info.pszDisplayName = display;
                info.lpszTitle = title;
                info.ulFlags = 0x51;
                info.lpfn = IntPtr.Zero;
                info.lParam = IntPtr.Zero;
                info.iImage = 0;
                pidl = SHBrowseForFolder(ref info);
                if (pidl == IntPtr.Zero)
                    return null;
                StringBuilder path = new StringBuilder(260);
                return SHGetPathFromIDList(pidl, path) ? path.ToString() : null;
            }
            finally
            {
                if (pidl != IntPtr.Zero)
                    CoTaskMemFree(pidl);
                Marshal.FreeHGlobal(display);
                Marshal.FreeHGlobal(title);
            }
        }

        [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
        private static extern IntPtr SHBrowseForFolder(ref BROWSEINFO info);

        [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
        private static extern bool SHGetPathFromIDList(IntPtr pidl, StringBuilder path);

        [DllImport("ole32.dll")]
        private static extern void CoTaskMemFree(IntPtr pointer);

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private struct BROWSEINFO
        {
            public IntPtr hwndOwner;
            public IntPtr pidlRoot;
            public IntPtr pszDisplayName;
            public IntPtr lpszTitle;
            public uint ulFlags;
            public IntPtr lpfn;
            public IntPtr lParam;
            public int iImage;
        }

        private void OnSourceInitialized(object sender, EventArgs e)
        {
            HwndSource source = PresentationSource.FromVisual(this) as HwndSource;
            if (source != null)
                source.AddHook(WindowMessageHook);
        }

        private IntPtr WindowMessageHook(IntPtr hwnd, int message, IntPtr wParam,
            IntPtr lParam, ref bool handled)
        {
            if (message == TrayMessage)
            {
                int trayEvent = lParam.ToInt32();
                if (trayEvent == 0x0202 || trayEvent == 0x0203)
                    RestoreFromTray();
                else if (trayEvent == 0x0205)
                    ShowTrayMenu();
                handled = true;
                return IntPtr.Zero;
            }
            const int WmGetMinMaxInfo = 0x0024;
            if (message != WmGetMinMaxInfo || !isFullscreen)
                return IntPtr.Zero;

            MINMAXINFO limits = (MINMAXINFO)Marshal.PtrToStructure(lParam, typeof(MINMAXINFO));
            IntPtr monitor = MonitorFromWindow(hwnd, 2);
            if (monitor != IntPtr.Zero)
            {
                MONITORINFO info = new MONITORINFO();
                info.Size = Marshal.SizeOf(typeof(MONITORINFO));
                if (GetMonitorInfo(monitor, ref info))
                {
                    RECT work = info.WorkArea;
                    RECT screen = info.MonitorArea;
                    limits.MaxPosition.X = Math.Abs(work.Left - screen.Left);
                    limits.MaxPosition.Y = Math.Abs(work.Top - screen.Top);
                    limits.MaxSize.X = Math.Abs(screen.Right - screen.Left);
                    limits.MaxSize.Y = Math.Abs(screen.Bottom - screen.Top);
                    limits.MaxTrackPosition = limits.MaxPosition;
                    limits.MaxTrackSize = limits.MaxSize;
                    Marshal.StructureToPtr(limits, lParam, false);
                }
            }
            handled = true;
            return IntPtr.Zero;
        }

        [DllImport("user32.dll")]
        private static extern IntPtr MonitorFromWindow(IntPtr hwnd, uint flags);

        [DllImport("user32.dll", CharSet = CharSet.Auto)]
        private static extern bool GetMonitorInfo(IntPtr monitor, ref MONITORINFO info);

        [StructLayout(LayoutKind.Sequential)]
        private struct POINT
        {
            public int X;
            public int Y;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct RECT
        {
            public int Left;
            public int Top;
            public int Right;
            public int Bottom;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct MINMAXINFO
        {
            public POINT Reserved;
            public POINT MaxSize;
            public POINT MaxPosition;
            public POINT MinTrackSize;
            public POINT MaxTrackSize;
            public POINT MaxTrackPosition;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct MONITORINFO
        {
            public int Size;
            public RECT MonitorArea;
            public RECT WorkArea;
            public uint Flags;
        }

        private void OnWindowStateChanged(object sender, EventArgs e)
        {
            maximizeGlyph.Text = WindowState == WindowState.Maximized ? "" : "";
            if (WindowState == WindowState.Minimized)
            {
                HideToTray();
            }
            else
            {
                stateBeforeTray = WindowState;
                if (minimizedToTray)
                    RestoreFromTray();
                else
                    RemoveTrayIcon();
            }
        }

        private void HideToTray()
        {
            if (minimizedToTray)
                return;
            minimizedToTray = true;
            if (!AddTrayIcon())
            {
                minimizedToTray = false;
                return;
            }
            Hide();
        }

        private bool AddTrayIcon()
        {
            if (trayIconAdded)
                return true;
            if (trayIconHandle == IntPtr.Zero)
            {
                IntPtr largeIcon;
                IntPtr smallIcon;
                string executable = Process.GetCurrentProcess().MainModule.FileName;
                if (ExtractIconEx(executable, 0, out largeIcon, out smallIcon, 1) > 0)
                {
                    trayIconHandle = smallIcon;
                    ownsTrayIcon = true;
                    if (largeIcon != IntPtr.Zero)
                        DestroyIcon(largeIcon);
                }
                else
                {
                    trayIconHandle = LoadIcon(IntPtr.Zero, new IntPtr(32512));
                    ownsTrayIcon = false;
                }
            }
            NOTIFYICONDATA data = CreateTrayData();
            trayIconAdded = Shell_NotifyIcon(0, ref data);
            return trayIconAdded;
        }

        private NOTIFYICONDATA CreateTrayData()
        {
            NOTIFYICONDATA data = new NOTIFYICONDATA();
            data.cbSize = (uint)Marshal.SizeOf(typeof(NOTIFYICONDATA));
            data.hWnd = new WindowInteropHelper(this).Handle;
            data.uID = 1;
            data.uFlags = 7;
            data.uCallbackMessage = TrayMessage;
            data.hIcon = trayIconHandle;
            data.szTip = "轻播 Lite - 左键恢复，右键菜单";
            data.dwState = 0;
            data.dwStateMask = 0;
            data.szInfo = String.Empty;
            data.uTimeout = 0;
            data.szInfoTitle = String.Empty;
            data.dwInfoFlags = 0;
            data.guidItem = Guid.Empty;
            data.hBalloonIcon = IntPtr.Zero;
            return data;
        }

        private void RemoveTrayIcon()
        {
            if (!trayIconAdded)
                return;
            NOTIFYICONDATA data = CreateTrayData();
            Shell_NotifyIcon(2, ref data);
            trayIconAdded = false;
        }

        private void DestroyTrayIcon()
        {
            RemoveTrayIcon();
            if (ownsTrayIcon && trayIconHandle != IntPtr.Zero)
                DestroyIcon(trayIconHandle);
            trayIconHandle = IntPtr.Zero;
            ownsTrayIcon = false;
        }

        private void RestoreFromTray()
        {
            if (!minimizedToTray)
            {
                RemoveTrayIcon();
                return;
            }
            minimizedToTray = false;
            RemoveTrayIcon();
            Show();
            WindowState = stateBeforeTray == WindowState.Maximized
                ? WindowState.Maximized : WindowState.Normal;
            Topmost = userTopmost;
            Activate();
            Keyboard.Focus(this);
        }

        private void ShowTrayMenu()
        {
            IntPtr menu = CreatePopupMenu();
            if (menu == IntPtr.Zero)
                return;
            try
            {
                AppendMenu(menu, 0, 1001, "恢复窗口");
                AppendMenu(menu, 0, 1002, "退出");
                POINT point;
                GetCursorPos(out point);
                IntPtr hwnd = new WindowInteropHelper(this).Handle;
                SetForegroundWindow(hwnd);
                int command = TrackPopupMenuEx(menu, 0x120, point.X, point.Y, hwnd, IntPtr.Zero);
                if (command == 1001)
                    RestoreFromTray();
                else if (command == 1002)
                    Close();
            }
            finally
            {
                DestroyMenu(menu);
            }
        }

        [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
        private static extern bool Shell_NotifyIcon(uint message, ref NOTIFYICONDATA data);

        [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
        private static extern uint ExtractIconEx(string file, int index,
            out IntPtr largeIcon, out IntPtr smallIcon, uint iconCount);

        [DllImport("user32.dll")]
        private static extern IntPtr LoadIcon(IntPtr instance, IntPtr iconName);

        [DllImport("user32.dll")]
        private static extern bool DestroyIcon(IntPtr icon);

        [DllImport("user32.dll")]
        private static extern IntPtr CreatePopupMenu();

        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        private static extern bool AppendMenu(IntPtr menu, uint flags, uint id, string text);

        [DllImport("user32.dll")]
        private static extern int TrackPopupMenuEx(IntPtr menu, uint flags, int x, int y,
            IntPtr hwnd, IntPtr parameters);

        [DllImport("user32.dll")]
        private static extern bool DestroyMenu(IntPtr menu);

        [DllImport("user32.dll")]
        private static extern bool GetCursorPos(out POINT point);

        [DllImport("user32.dll")]
        private static extern bool SetForegroundWindow(IntPtr hwnd);

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private struct NOTIFYICONDATA
        {
            public uint cbSize;
            public IntPtr hWnd;
            public uint uID;
            public uint uFlags;
            public uint uCallbackMessage;
            public IntPtr hIcon;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)]
            public string szTip;
            public uint dwState;
            public uint dwStateMask;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 256)]
            public string szInfo;
            public uint uTimeout;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 64)]
            public string szInfoTitle;
            public uint dwInfoFlags;
            public Guid guidItem;
            public IntPtr hBalloonIcon;
        }

        private void OnWindowClosing(object sender, System.ComponentModel.CancelEventArgs e)
        {
            isClosing = true;
            DestroyTrayIcon();
            ReleaseMedia();
        }

        private static TextBlock MakeText(string text, double size, Brush foreground)
        {
            return new TextBlock
            {
                Text = text,
                FontSize = size,
                Foreground = foreground,
                TextTrimming = TextTrimming.CharacterEllipsis
            };
        }

        private static Button CreateWindowButton(string glyph, string tooltip, Brush hover)
        {
            Button button = CreateButton(glyph, tooltip, tooltip,
                ButtonBrush, hover, ButtonPressedBrush);
            button.Width = 46;
            button.Height = 44;
            button.Padding = new Thickness(0);
            button.FontFamily = new FontFamily("Segoe MDL2 Assets");
            button.FontSize = 10;
            return button;
        }

        private static Button CreateButton(string content, string tooltip, string automationName,
            Brush normal, Brush hover, Brush pressed)
        {
            Button button = new Button
            {
                Content = content,
                ToolTip = tooltip,
                Height = 34,
                MinWidth = 34,
                Padding = new Thickness(9, 0, 9, 0),
                FontSize = 12,
                Foreground = TextBrush,
                Cursor = Cursors.Hand,
                Focusable = false,
                Style = CreateButtonStyle(normal, hover, pressed)
            };
            AutomationProperties.SetName(button, automationName);
            WindowChrome.SetIsHitTestVisibleInChrome(button, true);
            return button;
        }

        private static Style CreateButtonStyle(Brush normal, Brush hover, Brush pressed)
        {
            Style style = new Style(typeof(Button));
            style.Setters.Add(new Setter(Button.BackgroundProperty, normal));
            style.Setters.Add(new Setter(Button.BorderThicknessProperty, new Thickness(0)));

            ControlTemplate template = new ControlTemplate(typeof(Button));
            FrameworkElementFactory border = new FrameworkElementFactory(typeof(Border), "Chrome");
            border.SetValue(Border.BackgroundProperty,
                new TemplateBindingExtension(Button.BackgroundProperty));
            border.SetValue(Border.CornerRadiusProperty, new CornerRadius(5));
            border.SetValue(Border.SnapsToDevicePixelsProperty, true);
            FrameworkElementFactory content = new FrameworkElementFactory(typeof(ContentPresenter));
            content.SetValue(ContentPresenter.ContentProperty,
                new TemplateBindingExtension(ContentControl.ContentProperty));
            content.SetValue(ContentPresenter.ContentTemplateProperty,
                new TemplateBindingExtension(ContentControl.ContentTemplateProperty));
            content.SetValue(ContentPresenter.HorizontalAlignmentProperty, HorizontalAlignment.Center);
            content.SetValue(ContentPresenter.VerticalAlignmentProperty, VerticalAlignment.Center);
            border.AppendChild(content);
            template.VisualTree = border;

            Trigger over = new Trigger { Property = Button.IsMouseOverProperty, Value = true };
            over.Setters.Add(new Setter(Border.BackgroundProperty, hover, "Chrome"));
            template.Triggers.Add(over);
            Trigger down = new Trigger { Property = Button.IsPressedProperty, Value = true };
            down.Setters.Add(new Setter(Border.BackgroundProperty, pressed, "Chrome"));
            template.Triggers.Add(down);
            Trigger disabled = new Trigger { Property = Button.IsEnabledProperty, Value = false };
            disabled.Setters.Add(new Setter(Border.OpacityProperty, 0.3, "Chrome"));
            template.Triggers.Add(disabled);
            style.Setters.Add(new Setter(Button.TemplateProperty, template));
            return style;
        }

        private static SolidColorBrush MakeBrush(string color)
        {
            SolidColorBrush brush = new SolidColorBrush((Color)ColorConverter.ConvertFromString(color));
            brush.Freeze();
            return brush;
        }

    }

    internal sealed class RangeBar : FrameworkElement
    {
        private static readonly Brush TrackBrush = CreateBrush("#FF35404C");
        private static readonly Brush FillBrush = CreateBrush("#FF45D69E");
        private static readonly Brush ThumbBrush = CreateBrush("#FFE3FFF4");
        private readonly bool continuous;
        private double ratio;
        private double dragRatio;
        private bool pointerOver;

        public RangeBar(bool continuousChanges)
        {
            continuous = continuousChanges;
            Focusable = false;
            SnapsToDevicePixels = true;
            MinWidth = 24;
        }

        public event Action<double> ValueChangedByUser;
        public bool IsDragging { get; private set; }

        public double Ratio
        {
            get { return ratio; }
            set
            {
                if (IsDragging)
                    return;
                ratio = Math.Max(0.0, Math.Min(1.0, value));
                InvalidateVisual();
            }
        }

        protected override void OnRender(DrawingContext drawingContext)
        {
            base.OnRender(drawingContext);
            double width = ActualWidth;
            double height = ActualHeight;
            if (width <= 0 || height <= 0)
                return;
            drawingContext.DrawRectangle(Brushes.Transparent, null, new Rect(0, 0, width, height));
            double middle = height / 2.0;
            double value = IsDragging ? dragRatio : ratio;
            double thumbX = 6.0 + value * Math.Max(0.0, width - 12.0);
            drawingContext.DrawRoundedRectangle(TrackBrush, null,
                new Rect(0, middle - 2.0, width, 4.0), 2.0, 2.0);
            if (thumbX > 0.5)
            {
                drawingContext.DrawRoundedRectangle(FillBrush, null,
                    new Rect(0, middle - 2.0, thumbX, 4.0), 2.0, 2.0);
            }
            double radius = IsDragging ? 6.0 : (pointerOver ? 5.5 : 4.5);
            drawingContext.DrawEllipse(ThumbBrush, null, new Point(thumbX, middle), radius, radius);
        }

        protected override void OnMouseLeftButtonDown(MouseButtonEventArgs e)
        {
            base.OnMouseLeftButtonDown(e);
            IsDragging = true;
            dragRatio = ratio;
            CaptureMouse();
            UpdateDrag(e.GetPosition(this));
            e.Handled = true;
        }

        protected override void OnMouseMove(MouseEventArgs e)
        {
            base.OnMouseMove(e);
            if (IsDragging)
            {
                if (e.LeftButton == MouseButtonState.Pressed)
                    UpdateDrag(e.GetPosition(this));
                else
                    CancelDrag();
            }
        }

        protected override void OnMouseLeftButtonUp(MouseButtonEventArgs e)
        {
            base.OnMouseLeftButtonUp(e);
            if (!IsDragging)
                return;
            UpdateDrag(e.GetPosition(this));
            IsDragging = false;
            ratio = dragRatio;
            ReleaseMouseCapture();
            InvalidateVisual();
            RaiseChanged();
            e.Handled = true;
        }

        protected override void OnLostMouseCapture(MouseEventArgs e)
        {
            base.OnLostMouseCapture(e);
            CancelDrag();
        }

        protected override void OnMouseEnter(MouseEventArgs e)
        {
            base.OnMouseEnter(e);
            pointerOver = true;
            InvalidateVisual();
        }

        protected override void OnMouseLeave(MouseEventArgs e)
        {
            base.OnMouseLeave(e);
            pointerOver = false;
            InvalidateVisual();
        }

        private void UpdateDrag(Point point)
        {
            double usableWidth = Math.Max(1.0, ActualWidth - 12.0);
            dragRatio = Math.Max(0.0, Math.Min(1.0, (point.X - 6.0) / usableWidth));
            InvalidateVisual();
            if (continuous)
                RaiseChanged();
        }

        private void RaiseChanged()
        {
            Action<double> handler = ValueChangedByUser;
            if (handler != null)
                handler(dragRatio);
        }

        private void CancelDrag()
        {
            if (!IsDragging)
                return;
            IsDragging = false;
            InvalidateVisual();
        }

        private static SolidColorBrush CreateBrush(string color)
        {
            SolidColorBrush brush = new SolidColorBrush((Color)ColorConverter.ConvertFromString(color));
            brush.Freeze();
            return brush;
        }
    }
}
