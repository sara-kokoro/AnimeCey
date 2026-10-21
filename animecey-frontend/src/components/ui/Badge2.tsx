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
  genre: "bg-foreground/10 text-foreground border border-foreground/15 backdrop-blur",
  serie: "bg-info/15 text-info border border-info/30",
  film: "bg-highlight/15 text-highlight border border-highlight/30",
  ongoing: "bg-success/15 text-success border border-success/30",
  completed: "bg-muted-foreground/15 text-muted-foreground border border-border",
  upcoming: "bg-warning/15 text-warning border border-warning/30",
};

export function Badge2({ variant = "genre", children, className }: Props) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-semibold tracking-wide font-body",
        styles[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}