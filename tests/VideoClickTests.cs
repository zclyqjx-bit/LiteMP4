using System;
using System.Reflection;
using System.Windows;
using System.Windows.Threading;
using LiteMp4;

namespace VideoClickTests
{
    internal static class Program
    {
        private static void SetField(PlayerWindow window, string name, object value)
        {
            typeof(PlayerWindow).GetField(name, BindingFlags.NonPublic | BindingFlags.Instance)
                .SetValue(window, value);
        }

        private static T GetField<T>(PlayerWindow window, string name)
        {
            return (T)typeof(PlayerWindow).GetField(name, BindingFlags.NonPublic | BindingFlags.Instance)
                .GetValue(window);
        }

        [STAThread]
        private static int Main()
        {
            if (Application.Current == null)
                new Application();
            PlayerWindow window = new PlayerWindow();
            try
            {
                SetField(window, "hasMedia", true);
                SetField(window, "isPlaying", true);
                typeof(PlayerWindow).GetMethod("ScheduleVideoClick",
                    BindingFlags.NonPublic | BindingFlags.Instance).Invoke(window, null);
                DispatcherTimer clickTimer = GetField<DispatcherTimer>(window, "videoClickTimer");
                if (!clickTimer.IsEnabled)
                    throw new Exception("Test setup did not arm the video click timer");

                typeof(PlayerWindow).GetMethod("StopPlayback",
                    BindingFlags.NonPublic | BindingFlags.Instance).Invoke(window, null);
                if (clickTimer.IsEnabled)
                    throw new Exception("StopPlayback left the pending video click timer running");

                DispatcherFrame frame = new DispatcherFrame();
                DispatcherTimer wait = new DispatcherTimer(DispatcherPriority.Normal);
                wait.Interval = TimeSpan.FromMilliseconds(1200);
                wait.Tick += delegate
                {
                    wait.Stop();
                    frame.Continue = false;
                };
                wait.Start();
                Dispatcher.PushFrame(frame);
                if (GetField<bool>(window, "isPlaying"))
                    throw new Exception("A stale video click restarted playback after Stop");
                Console.WriteLine("PASS: Stop cancels a pending video click and remains stopped");
                return 0;
            }
            finally
            {
                window.Close();
            }
        }
    }
}
