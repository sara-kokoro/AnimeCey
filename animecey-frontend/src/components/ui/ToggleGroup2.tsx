import { cn } from "@/lib/utils";

type Val = string | number;

interface Props<T extends Val> {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
  size?: "sm" | "md";
  className?: string;
}

export function ToggleGroup2<T extends Val>({
  options,
  value,
  onChange,
  size = "md",
  className,
}: Props<T>) {
  return (
    <div className={cn("no-scrollbar flex gap-2 overflow-x-auto max-w-full min-w-0", className)}>
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={String(opt.value)}
            onClick={() => onChange(opt.value)}
            className={cn(
              "shrink-0 rounded-lg font-body font-semibold transition-all duration-200 border",
              size === "sm" ? "px-3.5 py-1.5 text-xs" : "px-4 py-2 text-sm",
              active
                ? "bg-primary text-primary-foreground border-primary"
                : "bg-surface text-muted-foreground border-border hover:text-foreground hover:border-border-subtle",
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}