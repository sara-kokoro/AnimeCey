function colorFromName(name: string) {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) % 360;
  return `hsl(${h}, 50%, 35%)`;
}

export function Avatar({ name, size = 36 }: { name: string; size?: number }) {
  const initials = name.slice(0, 2).toUpperCase();
  return (
    <div
      className="rounded-full flex items-center justify-center font-display font-bold text-foreground shrink-0"
      style={{ width: size, height: size, background: colorFromName(name), fontSize: size * 0.4 }}
    >
      {initials}
    </div>
  );
}