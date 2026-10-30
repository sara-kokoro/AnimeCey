/** « 228 Mo », « 1,4 Go » : taille lisible. */
export function fmtSize(bytes: number): string {
  if (bytes >= 1_000_000_000) return `${(bytes / 1_000_000_000).toFixed(1).replace(".", ",")} Go`;
  if (bytes >= 1_000_000) return `${Math.round(bytes / 1_000_000)} Mo`;
  return `${Math.max(1, Math.round(bytes / 1024))} Ko`;
}
