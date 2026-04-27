import { ChevronLeft, ChevronRight } from "lucide-react";
import { useRef, useState, useEffect, type ReactNode } from "react";
import { cn } from "@/lib/utils";

interface Props {
  children: ReactNode;
  className?: string;
}

export function HorizontalScroll({ children, className }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [canLeft, setCanLeft] = useState(false);
  const [canRight, setCanRight] = useState(false);

  const update = () => {
    const el = ref.current;
    if (!el) return;
    setCanLeft(el.scrollLeft > 8);
    setCanRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 8);
  };

  useEffect(() => {
    update();
    const el = ref.current;
    if (!el) return;
    el.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    return () => {
      el.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
    };
  }, []);

  const scrollBy = (dir: 1 | -1) => {
    const el = ref.current;
    if (!el) return;
    el.scrollBy({ left: dir * (el.clientWidth * 0.8), behavior: "smooth" });
  };

  return (
    <div className={cn("relative group/scroll", className)}>
      <div
        ref={ref}
        className="no-scrollbar flex gap-4 overflow-x-auto scroll-smooth pb-2 -mx-4 px-4 md:mx-0 md:px-0"
      >
        {children}
      </div>

      {canLeft && (
        <button
          aria-label="Défiler à gauche"
          onClick={() => scrollBy(-1)}
          className="hidden md:flex absolute left-0 top-1/2 -translate-y-1/2 -translate-x-2 w-10 h-10 rounded-full bg-surface/95 backdrop-blur border border-border items-center justify-center text-foreground opacity-0 group-hover/scroll:opacity-100 transition-opacity hover:bg-surface-2 z-10"
        >
          <ChevronLeft className="w-5 h-5" />
        </button>
      )}
      {canRight && (
        <button
          aria-label="Défiler à droite"
          onClick={() => scrollBy(1)}
          className="hidden md:flex absolute right-0 top-1/2 -translate-y-1/2 translate-x-2 w-10 h-10 rounded-full bg-surface/95 backdrop-blur border border-border items-center justify-center text-foreground opacity-0 group-hover/scroll:opacity-100 transition-opacity hover:bg-surface-2 z-10"
        >
          <ChevronRight className="w-5 h-5" />
        </button>
      )}
    </div>
  );
}