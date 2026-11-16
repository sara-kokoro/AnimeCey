/** Emoji drapeau d'un code pays ISO (« TG » -> 🇹🇬), calculé : pas de liste à maintenir. */
export function flag(code: string): string {
  const c = code.trim().toUpperCase();
  if (!/^[A-Z]{2}$/.test(c)) return "🌍";
  return String.fromCodePoint(...[...c].map((ch) => 0x1f1e6 + ch.charCodeAt(0) - 65));
}
