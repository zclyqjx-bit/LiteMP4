using System;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Threading;

namespace LiteMp4
{
    internal sealed class MpvPlayer : IDisposable
    {
        private const string LibraryName = "libmpv-2.dll";
        private const int EventShutdown = 1;
        private const int EventLogMessage = 2;
        private const int EventEndFile = 7;
        private const int EventFileLoaded = 8;
        private const int EventPropertyChange = 22;
        private const int FormatFlag = 3;
        private const int FormatDouble = 5;

        private readonly Dispatcher dispatcher;
        private IntPtr handle;
        private Thread eventThread;
        private volatile bool disposed;
        private bool endedReported;

        public MpvPlayer(IntPtr videoWindow)
        {
            if (videoWindow == IntPtr.Zero)
                throw new ArgumentException("视频窗口尚未准备完成。", "videoWindow");
            dispatcher = Dispatcher.CurrentDispatcher;
            string library = Path.Combine(AppDomain.CurrentDomain.BaseDirectory,
                Path.Combine("runtime", LibraryName));
            if (!File.Exists(library))
                throw new FileNotFoundException("缺少 AV1/HEVC 兼容解码组件。", library);
            if (LoadLibraryEx(library, IntPtr.Zero, 8) == IntPtr.Zero)
                throw new InvalidOperationException("兼容解码组件加载失败，错误码：" +
                    Marshal.GetLastWin32Error().ToString(CultureInfo.InvariantCulture));

            handle = mpv_create();
            if (handle == IntPtr.Zero)
                throw new InvalidOperationException("无法创建兼容播放器。 ");
            try
            {
                Configure(videoWindow);
                Check(mpv_initialize(handle), "初始化兼容播放器");
                Observe(1, "duration", FormatDouble);
                Observe(2, "pause", FormatFlag);
                Observe(3, "eof-reached", FormatFlag);
                Observe(4, "paused-for-cache", FormatFlag);
                mpv_request_log_messages(handle, Utf8("warn"));
                eventThread = new Thread(EventLoop);
                eventThread.IsBackground = true;
                eventThread.Name = "libmpv events";
                eventThread.Start();
            }
            catch
            {
                disposed = true;
                if (handle != IntPtr.Zero)
                    mpv_terminate_destroy(handle);
                handle = IntPtr.Zero;
                throw;
            }
        }

        public event Action Loaded;
        public event Action Ended;
        public event Action<string> Failed;
        public event Action<bool> PauseChanged;
        public event Action<bool> BufferingChanged;
        public event Action<double> DurationChanged;
        public string LastLog { get; private set; }

        private void Configure(IntPtr videoWindow)
        {
            SetOption("config", "no");
            SetOption("idle", "yes");
            SetOption("wid", videoWindow.ToInt64().ToString(CultureInfo.InvariantCulture));
            SetOption("vo", "gpu");
            SetOption("gpu-api", "d3d11");
            SetOption("hwdec", "auto-safe");
            SetOption("video-sync", "audio");
            SetOption("framedrop", "decoder+vo");
            SetOption("vd-lavc-threads", "4");
            SetOption("vd-lavc-fast", "yes");
            SetOption("vd-lavc-skiploopfilter", "all");
            SetOption("vd-lavc-o", "skip_frame=nonref:filmgrain=0");
            SetOption("vd-queue-max-secs", "1");
            SetOption("vd-queue-max-samples", "6");
            SetOption("vd-queue-max-bytes", "128MiB");
            SetOption("ad-queue-max-secs", "3");
            SetOption("cache", "yes");
            SetOption("cache-secs", "15");
            SetOption("cache-pause-initial", "yes");
            SetOption("demuxer-max-bytes", "32MiB");
            SetOption("demuxer-max-back-bytes", "16MiB");
            SetOption("keep-open", "yes");
            SetOption("osc", "no");
            SetOption("osd-level", "0");
            SetOption("load-scripts", "no");
            SetOption("ytdl", "no");
            SetOption("input-default-bindings", "no");
            SetOption("input-vo-keyboard", "no");
            SetOption("input-cursor", "no");
            SetOption("scale", "bilinear");
            SetOption("cscale", "bilinear");
            SetOption("dscale", "bilinear");
            SetOption("interpolation", "no");
            SetOption("vf", "fps=12");
            SetOption("audio-buffer", "1.5");
            SetOption("hr-seek", "yes");
            SetOption("volume-max", "100");
        }

        public double Position
        {
            get { return GetDouble("time-pos"); }
        }

        public double Duration
        {
            get { return GetDouble("duration"); }
        }

        public double VideoWidth
        {
            get { return GetDouble("video-params/w"); }
        }

        public double VideoHeight
        {
            get { return GetDouble("video-params/h"); }
        }

        public double OutputVideoWidth
        {
            get { return GetDouble("video-out-params/w"); }
        }

        public double OutputVideoHeight
        {
            get { return GetDouble("video-out-params/h"); }
        }

        public string VideoCodec
        {
            get
            {
                string format = GetString("video-format");
                return String.IsNullOrEmpty(format) ? GetString("video-codec") : format;
            }
        }

        public double AudioVideoSync
        {
            get { return GetDouble("avsync"); }
        }

        public double EstimatedVideoFrameRate
        {
            get { return GetDouble("estimated-vf-fps"); }
        }

        public void EnableReducedQuality(string codec)
        {
            if (!String.Equals(codec, "hevc", StringComparison.OrdinalIgnoreCase) &&
                !String.Equals(codec, "h265", StringComparison.OrdinalIgnoreCase))
            {
                SetProperty("vf", "fps=15,scale=960:-2:flags=fast_bilinear,format=yuv420p");
            }
        }

        public void Load(string path)
        {
            endedReported = false;
            Command("loadfile", path, "replace");
            SetPaused(false);
        }

        public void SetPaused(bool paused)
        {
            SetProperty("pause", paused ? "yes" : "no");
        }

        public void SetVolume(double ratio)
        {
            SetProperty("volume", (Math.Max(0.0, Math.Min(1.0, ratio)) * 100.0)
                .ToString("0.##", CultureInfo.InvariantCulture));
        }

        public void SetMuted(bool muted)
        {
            SetProperty("mute", muted ? "yes" : "no");
        }

        public void SetRate(double value)
        {
            SetProperty("speed", value.ToString("0.##", CultureInfo.InvariantCulture));
        }

        public void Seek(double seconds)
        {
            endedReported = false;
            SetProperty("time-pos", Math.Max(0.0, seconds)
                .ToString("0.###", CultureInfo.InvariantCulture));
        }

        private void EventLoop()
        {
            try
            {
                while (handle != IntPtr.Zero)
                {
                    IntPtr pointer = mpv_wait_event(handle, -1.0);
                    if (pointer == IntPtr.Zero)
                        break;
                    MpvEvent mediaEvent = (MpvEvent)Marshal.PtrToStructure(pointer, typeof(MpvEvent));
                    if (mediaEvent.Id == EventShutdown)
                        break;
                    switch (mediaEvent.Id)
                    {
                        case EventFileLoaded:
                            endedReported = false;
                            Post(Loaded);
                            break;
                        case EventEndFile:
                            HandleEndFile(mediaEvent.Data);
                            break;
                        case EventPropertyChange:
                            HandleProperty(mediaEvent.ReplyUserData, mediaEvent.Data);
                            break;
                        case EventLogMessage:
                            HandleLog(mediaEvent.Data);
                            break;
                    }
                }
            }
            catch (Exception error)
            {
                if (!disposed)
                    Post(Failed, "兼容播放事件处理失败：" + error.Message);
            }
            finally
            {
                IntPtr oldHandle = handle;
                handle = IntPtr.Zero;
                if (oldHandle != IntPtr.Zero)
                    mpv_terminate_destroy(oldHandle);
            }
        }

        private void HandleEndFile(IntPtr data)
        {
            if (data == IntPtr.Zero)
                return;
            MpvEndFile end = (MpvEndFile)Marshal.PtrToStructure(data, typeof(MpvEndFile));
            if (end.Reason == 0)
                ReportEnded();
            else if (end.Reason == 4)
            {
                string detail = ErrorString(end.Error);
                if (!String.IsNullOrEmpty(LastLog))
                    detail += "\n" + LastLog;
                Post(Failed, detail);
            }
        }

        private void HandleProperty(ulong id, IntPtr data)
        {
            if (data == IntPtr.Zero)
                return;
            MpvEventProperty property = (MpvEventProperty)Marshal.PtrToStructure(
                data, typeof(MpvEventProperty));
            if (property.Data == IntPtr.Zero)
                return;
            if (id == 1 && property.Format == FormatDouble)
            {
                Post(DurationChanged, ReadDouble(property.Data));
            }
            else if (id == 2 && property.Format == FormatFlag)
            {
                Post(PauseChanged, Marshal.ReadInt32(property.Data) != 0);
            }
            else if (id == 3 && property.Format == FormatFlag)
            {
                if (Marshal.ReadInt32(property.Data) != 0)
                    ReportEnded();
            }
            else if (id == 4 && property.Format == FormatFlag)
            {
                Post(BufferingChanged, Marshal.ReadInt32(property.Data) != 0);
            }
        }

        private void HandleLog(IntPtr data)
        {
            if (data == IntPtr.Zero)
                return;
            MpvLogMessage message = (MpvLogMessage)Marshal.PtrToStructure(data, typeof(MpvLogMessage));
            string text = PtrToStringUtf8(message.Text).Trim();
            if (text.Length > 0)
                LastLog = PtrToStringUtf8(message.Prefix) + ": " + text;
        }

        private void ReportEnded()
        {
            if (endedReported)
                return;
            endedReported = true;
            Post(Ended);
        }

        private void SetOption(string name, string value)
        {
            Check(mpv_set_option_string(handle, Utf8(name), Utf8(value)), "设置 " + name);
        }

        private void Observe(ulong id, string name, int format)
        {
            Check(mpv_observe_property(handle, id, Utf8(name), format), "监视 " + name);
        }

        private void SetProperty(string name, string value)
        {
            Check(mpv_set_property_string(handle, Utf8(name), Utf8(value)), "设置 " + name);
        }

        private double GetDouble(string name)
        {
            if (disposed || handle == IntPtr.Zero)
                return 0.0;
            double value;
            return mpv_get_property_double(handle, Utf8(name), FormatDouble, out value) >= 0 &&
                !Double.IsNaN(value) && !Double.IsInfinity(value) ? value : 0.0;
        }

        private string GetString(string name)
        {
            if (disposed || handle == IntPtr.Zero)
                return String.Empty;
            IntPtr pointer = mpv_get_property_string(handle, Utf8(name));
            if (pointer == IntPtr.Zero)
                return String.Empty;
            string value = PtrToStringUtf8(pointer);
            mpv_free(pointer);
            return value;
        }

        private void Command(params string[] arguments)
        {
            ExecuteCommand(false, arguments);
        }

        private void CommandAsync(params string[] arguments)
        {
            ExecuteCommand(true, arguments);
        }

        private void ExecuteCommand(bool asynchronous, string[] arguments)
        {
            IntPtr[] pointers = new IntPtr[arguments.Length + 1];
            try
            {
                for (int i = 0; i < arguments.Length; i++)
                    pointers[i] = AllocateUtf8(arguments[i]);
                pointers[arguments.Length] = IntPtr.Zero;
                int result = asynchronous
                    ? mpv_command_async(handle, 0, pointers)
                    : mpv_command(handle, pointers);
                Check(result, "执行兼容播放命令");
            }
            finally
            {
                for (int i = 0; i < pointers.Length; i++)
                {
                    if (pointers[i] != IntPtr.Zero)
                        Marshal.FreeHGlobal(pointers[i]);
                }
            }
        }

        private void Post(Action action)
        {
            if (action == null || dispatcher.HasShutdownStarted)
                return;
            dispatcher.BeginInvoke(new Action(delegate
            {
                if (!disposed)
                    action();
            }));
        }

        private void Post<T>(Action<T> action, T value)
        {
            if (action == null || dispatcher.HasShutdownStarted)
                return;
            dispatcher.BeginInvoke(new Action(delegate
            {
                if (!disposed)
                    action(value);
            }));
        }

        public void Dispose()
        {
            if (disposed)
                return;
            disposed = true;
            try
            {
                if (handle != IntPtr.Zero)
                    CommandAsync("quit");
            }
            catch (InvalidOperationException) { }
            if (eventThread != null && Thread.CurrentThread != eventThread)
                eventThread.Join(6000);
            Loaded = null;
            Ended = null;
            Failed = null;
            PauseChanged = null;
            BufferingChanged = null;
            DurationChanged = null;
        }

        private static double ReadDouble(IntPtr pointer)
        {
            return BitConverter.Int64BitsToDouble(Marshal.ReadInt64(pointer));
        }

        private static void Check(int result, string operation)
        {
            if (result < 0)
                throw new InvalidOperationException(operation + "失败：" + ErrorString(result));
        }

        private static string ErrorString(int error)
        {
            return PtrToStringUtf8(mpv_error_string(error));
        }

        private static byte[] Utf8(string value)
        {
            return Encoding.UTF8.GetBytes((value ?? String.Empty) + "\0");
        }

        private static IntPtr AllocateUtf8(string value)
        {
            byte[] bytes = Utf8(value);
            IntPtr pointer = Marshal.AllocHGlobal(bytes.Length);
            Marshal.Copy(bytes, 0, pointer, bytes.Length);
            return pointer;
        }

        private static string PtrToStringUtf8(IntPtr pointer)
        {
            if (pointer == IntPtr.Zero)
                return String.Empty;
            int length = 0;
            while (Marshal.ReadByte(pointer, length) != 0)
                length++;
            byte[] bytes = new byte[length];
            Marshal.Copy(pointer, bytes, 0, length);
            return Encoding.UTF8.GetString(bytes);
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct MpvEvent
        {
            public int Id;
            public int Error;
            public ulong ReplyUserData;
            public IntPtr Data;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct MpvEventProperty
        {
            public IntPtr Name;
            public int Format;
            public IntPtr Data;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct MpvEndFile
        {
            public int Reason;
            public int Error;
            public long PlaylistEntryId;
            public long PlaylistInsertId;
            public int PlaylistInsertNumEntries;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct MpvLogMessage
        {
            public IntPtr Prefix;
            public IntPtr Level;
            public IntPtr Text;
            public int LogLevel;
        }

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr LoadLibraryEx(string path, IntPtr file, uint flags);

        [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
        private static extern IntPtr mpv_create();

        [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
        private static extern int mpv_initialize(IntPtr context);

        [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
        private static extern void mpv_terminate_destroy(IntPtr context);

        [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
        private static extern int mpv_set_option_string(IntPtr context, byte[] name, byte[] value);

        [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
        private static extern int mpv_set_property_string(IntPtr context, byte[] name, byte[] value);

        [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
        private static extern int mpv_command(IntPtr context, IntPtr[] arguments);

        [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
        private static extern int mpv_command_async(IntPtr context, ulong userData, IntPtr[] arguments);

        [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
        private static extern IntPtr mpv_wait_event(IntPtr context, double timeout);

        [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
        private static extern int mpv_observe_property(IntPtr context, ulong userData,
            byte[] name, int format);

        [DllImport(LibraryName, EntryPoint = "mpv_get_property",
            CallingConvention = CallingConvention.Cdecl)]
        private static extern int mpv_get_property_double(IntPtr context, byte[] name,
            int format, out double value);

        [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
        private static extern IntPtr mpv_get_property_string(IntPtr context, byte[] name);

        [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
        private static extern void mpv_free(IntPtr pointer);

        [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
        private static extern int mpv_request_log_messages(IntPtr context, byte[] level);

        [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
        private static extern IntPtr mpv_error_string(int error);
    }
}
