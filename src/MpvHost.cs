using System;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;

namespace LiteMp4
{
    internal sealed class MpvHost : HwndHost
    {
        private const int WsChild = 0x40000000;
        private const int WsVisible = 0x10000000;
        private const int WsClipSiblings = 0x04000000;
        private const int WsClipChildren = 0x02000000;
        private const int SsBlackRect = 0x00000004;
        private const int WmLeftButtonDown = 0x0201;
        private int lastClickTick;

        public MpvHost()
        {
            Focusable = false;
        }

        public event Action Activated;
        public event Action DoubleClicked;

        protected override HandleRef BuildWindowCore(HandleRef hwndParent)
        {
            IntPtr child = CreateWindowEx(
                0, "static", String.Empty,
                WsChild | WsVisible | WsClipSiblings | WsClipChildren | SsBlackRect,
                0, 0, 64, 64, hwndParent.Handle, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero);
            if (child == IntPtr.Zero)
                throw new InvalidOperationException("无法创建兼容视频窗口。");
            return new HandleRef(this, child);
        }

        protected override void DestroyWindowCore(HandleRef hwnd)
        {
            if (hwnd.Handle != IntPtr.Zero)
                DestroyWindow(hwnd.Handle);
        }

        protected override IntPtr WndProc(IntPtr hwnd, int message, IntPtr wParam,
            IntPtr lParam, ref bool handled)
        {
            if (message == WmLeftButtonDown)
            {
                int now = Environment.TickCount;
                bool isDouble = (uint)(now - lastClickTick) <= GetDoubleClickTime();
                lastClickTick = isDouble ? 0 : now;
                Post(Activated);
                if (isDouble)
                    Post(DoubleClicked);
            }
            return base.WndProc(hwnd, message, wParam, lParam, ref handled);
        }

        private void Post(Action handler)
        {
            if (handler == null)
                return;
            Dispatcher.BeginInvoke(new Action(delegate
            {
                if (IsVisible)
                    handler();
            }));
        }

        [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr CreateWindowEx(int exStyle, string className,
            string windowName, int style, int x, int y, int width, int height,
            IntPtr parent, IntPtr menu, IntPtr instance, IntPtr parameter);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool DestroyWindow(IntPtr hwnd);

        [DllImport("user32.dll")]
        private static extern uint GetDoubleClickTime();
    }
}
