/**
 * Truncates a path in the middle so both start and end remain visible in one line.
 * e.g. "C:\\Users\\dev\\projects\\my-app\\src\\components\\VeryLongFileName.tsx"
 *  -> "C:\Users\dev\projects\…\VeryLongFileName.tsx"
 *
 * @param path - Full path string
 * @param maxLength - Max length (default 56). If path is shorter, returned as-is.
 * @returns path or "start…end" with head+tail+3 ≈ maxLength
 */
export function truncatePathMiddle(path: string, maxLength = 56): string {
  if (path.length <= maxLength) return path;
  const ellipsis = "…";
  const take = maxLength - ellipsis.length;
  const head = Math.ceil(take / 2);
  const tail = take - head;
  return path.slice(0, head) + ellipsis + path.slice(-tail);
}
