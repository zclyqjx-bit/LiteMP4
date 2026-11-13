using System;
using System.Collections.Generic;
using System.IO;

namespace LiteMp4
{
    internal sealed class NaturalFileComparer : IComparer<string>
    {
        public int Compare(string x, string y)
        {
            if (x == null)
                return y == null ? 0 : -1;
            if (y == null)
                return 1;

            string left = Path.GetFileNameWithoutExtension(x);
            string right = Path.GetFileNameWithoutExtension(y);
            int i = 0;
            int j = 0;
            while (i < left.Length && j < right.Length)
            {
                bool leftIsDigit = Char.IsDigit(left[i]);
                bool rightIsDigit = Char.IsDigit(right[j]);
                if (leftIsDigit && rightIsDigit)
                {
                    int leftEnd = i;
                    int rightEnd = j;
                    while (leftEnd < left.Length && Char.IsDigit(left[leftEnd]))
                        leftEnd++;
                    while (rightEnd < right.Length && Char.IsDigit(right[rightEnd]))
                        rightEnd++;
                    int numberResult = CompareNumberChunks(
                        left.Substring(i, leftEnd - i), right.Substring(j, rightEnd - j));
                    if (numberResult != 0)
                        return numberResult;
                    i = leftEnd;
                    j = rightEnd;
                    continue;
                }

                char leftChar = Char.ToLowerInvariant(left[i]);
                char rightChar = Char.ToLowerInvariant(right[j]);
                int result = leftChar.CompareTo(rightChar);
                if (result != 0)
                    return result;
                i++;
                j++;
            }

            if (i < left.Length)
                return 1;
            if (j < right.Length)
                return -1;
            return StringComparer.OrdinalIgnoreCase.Compare(x, y);
        }

        private static int CompareNumberChunks(string left, string right)
        {
            string leftNumber = left.TrimStart('0');
            string rightNumber = right.TrimStart('0');
            if (leftNumber.Length == 0)
                leftNumber = "0";
            if (rightNumber.Length == 0)
                rightNumber = "0";
            if (leftNumber.Length != rightNumber.Length)
                return leftNumber.Length.CompareTo(rightNumber.Length);
            return String.CompareOrdinal(leftNumber, rightNumber);
        }
    }
}
