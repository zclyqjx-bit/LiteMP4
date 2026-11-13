using System;
using System.Collections.Generic;
using System.Reflection;
using System.Windows;
using System.Windows.Controls;
using LiteMp4;

namespace MultiSelectionTests
{
    internal static class Program
    {
        private static readonly string Root = AppDomain.CurrentDomain.BaseDirectory;

        private static List<string> GetPlaylist(PlayerWindow window)
        {
            return (List<string>)typeof(PlayerWindow).GetField("playlist",
                BindingFlags.NonPublic | BindingFlags.Instance).GetValue(window);
        }

        private static ListBox GetListBox(PlayerWindow window)
        {
            return (ListBox)typeof(PlayerWindow).GetField("playlistListBox",
                BindingFlags.NonPublic | BindingFlags.Instance).GetValue(window);
        }

        private static void SetCurrentIndex(PlayerWindow window, int value)
        {
            typeof(PlayerWindow).GetField("currentIndex",
                BindingFlags.NonPublic | BindingFlags.Instance).SetValue(window, value);
        }

        private static void SelectTwo(PlayerWindow window)
        {
            ListBox box = GetListBox(window);
            box.SelectedItems.Clear();
            box.SelectedItems.Add(box.Items[0]);
            box.SelectedItems.Add(box.Items[2]);
        }

        [STAThread]
        private static int Main()
        {
            if (Application.Current == null)
                new Application();
            string a = System.IO.Path.Combine(Root, "multi-a.mp4");
            string b = System.IO.Path.Combine(Root, "multi-b.mp4");
            string c = System.IO.Path.Combine(Root, "multi-c.mp4");
            if (!System.IO.File.Exists(a) || !System.IO.File.Exists(b) || !System.IO.File.Exists(c))
                throw new Exception("Test media are missing: " + Root);

            PlayerWindow window = new PlayerWindow();
            try
            {
                List<string> playlist = GetPlaylist(window);
                playlist.Add(a);
                playlist.Add(b);
                playlist.Add(c);
                typeof(PlayerWindow).GetMethod("UpdatePlaylistView",
                    BindingFlags.NonPublic | BindingFlags.Instance).Invoke(window, null);
                SelectTwo(window);
                MethodInfo indicesMethod = typeof(PlayerWindow).GetMethod("GetSelectedIndices",
                    BindingFlags.NonPublic | BindingFlags.Instance);
                List<int> indices = (List<int>)indicesMethod.Invoke(window, null);
                if (indices.Count != 2 || indices[0] != 0 || indices[1] != 2)
                    throw new Exception("Non-contiguous indices were not preserved");

                List<string> selectedPaths = (List<string>)typeof(PlayerWindow).GetMethod(
                    "BuildSelectedPaths", BindingFlags.NonPublic | BindingFlags.Static)
                    .Invoke(null, new object[] { playlist, indices });
                if (selectedPaths.Count != 2 || selectedPaths[0] != a || selectedPaths[1] != c)
                    throw new Exception("PlaySelectedItems did not create the selected subset");

                playlist.Clear();
                playlist.Add(a);
                playlist.Add(b);
                playlist.Add(c);
                SetCurrentIndex(window, -1);
                typeof(PlayerWindow).GetMethod("UpdatePlaylistView",
                    BindingFlags.NonPublic | BindingFlags.Instance).Invoke(window, null);
                SelectTwo(window);
                typeof(PlayerWindow).GetMethod("DeleteSelectedPlaylistItem",
                    BindingFlags.NonPublic | BindingFlags.Instance).Invoke(window, null);
                if (playlist.Count != 1 || playlist[0] != b)
                    throw new Exception("DeleteSelectedPlaylistItem did not remove all selected items");
                Console.WriteLine("PASS: non-contiguous selection subset and multi-delete are correct");
                return 0;
            }
            finally
            {
                window.Close();
            }
        }
    }
}
