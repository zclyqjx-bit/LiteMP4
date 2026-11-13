using System;
using System.Collections.Generic;
using LiteMp4;

internal static class NaturalSortTests
{
    private static void Check(string[] input, string[] expected)
    {
        List<string> actual = new List<string>(input);
        actual.Sort(new NaturalFileComparer());
        for (int i = 0; i < expected.Length; i++)
        {
            if (!String.Equals(actual[i], expected[i], StringComparison.OrdinalIgnoreCase))
            {
                throw new Exception("Natural sort mismatch at " + i + ": expected " +
                    expected[i] + ", actual " + actual[i]);
            }
        }
    }

    private static int Main()
    {
        Check(
            new[] { "第10集.mp4", "第2集.mp4", "第1集.mp4", "S01E10.mp4", "S01E02.mp4", "S01E01.mp4", "20.mp4", "3.mp4", "01.mp4" },
            new[] { "01.mp4", "3.mp4", "20.mp4", "S01E01.mp4", "S01E02.mp4", "S01E10.mp4", "第1集.mp4", "第2集.mp4", "第10集.mp4" });
        Check(
            new[] { "file10part2.mp4", "file2part10.mp4", "file2part1.mp4" },
            new[] { "file2part1.mp4", "file2part10.mp4", "file10part2.mp4" });
        Check(
            new[] { "EP10.mp4", "EP3.mp4", "EP1.mp4", "EP02.mp4" },
            new[] { "EP1.mp4", "EP02.mp4", "EP3.mp4", "EP10.mp4" });
        Console.WriteLine("PASS: episode numbers and numeric chunks sort in ascending natural order");
        return 0;
    }
}
