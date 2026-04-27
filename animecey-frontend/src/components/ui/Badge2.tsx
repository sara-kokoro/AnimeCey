import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

type Variant = "vf" | "vostfr" | "genre" | "serie" | "film" | "ongoing" | "completed" | "upcoming";

interface Props {
  variant?: Variant;
  children: ReactNode;
  className?: string;
}

const styles: Record<Variant, string> = {
  vf: "bg-primary/15 text-primary border border-primary/30",
  vostfr: "bg-primary/15 text-primary border border-primary/30",
  genre: "bg-surface-2 text-muted-foreground border border-border",
  serie: "bg-info/15 text-info border border-info/30",
  film: "bg-[hsl(262_83%_58%/0.15)] text-[hsl(262_83%_70%)] border border-[hsl(262_83%_58%/0.3)]",
  ongoing: "bg-success/15 text-success border border-success/30",
  completed: "bg-muted-foreground/15 text-muted-foreground border border-border",
  upcoming: "bg-warning/15 text-warning border border-warning/30",
};

export function Badge2({ variant = "genre", children, className }: Props) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-1 rounded-md text-[11px] font-semibold tracking-wide font-body",
        styles[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}