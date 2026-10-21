/**
 * Thin compatibility layer exposing the small navigation API the app's pages use,
 * implemented on top of TanStack Router. Keeps page logic untouched.
 */
import {
  Link as TLink,
  Outlet as TOutlet,
  useNavigate as useTNavigate,
  useRouterState,
  useParams as useTParams,
} from "@tanstack/react-router";
import { forwardRef, useCallback, useEffect, useMemo, type AnchorHTMLAttributes, type ReactNode } from "react";

type To = string;
type NavOpts = { replace?: boolean; state?: unknown };

const STATE_KEY = "__compat_state";

function splitTo(to: To) {
  const [pathAndSearch, hash] = to.split("#");
  const [path, search] = pathAndSearch.split("?");
  return { path: path || "/", search: search ? Object.fromEntries(new URLSearchParams(search)) : undefined, hash };
}

export function useNavigate() {
  const nav = useTNavigate();
  return useCallback(
    (to: To | number, opts?: NavOpts) => {
      if (typeof to === "number") {
        window.history.go(to);
        return;
      }
      const { path, search, hash } = splitTo(to);
      if (opts?.state !== undefined) (window as unknown as Record<string, unknown>)[STATE_KEY] = opts.state;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      nav({ to: path as any, search: (search ?? {}) as any, hash, replace: opts?.replace });
    },
    [nav],
  );
}

export function useLocation() {
  const loc = useRouterState({ select: (s) => s.location });
  const state = typeof window !== "undefined" ? (window as unknown as Record<string, unknown>)[STATE_KEY] : undefined;
  return { pathname: loc.pathname, search: loc.searchStr, hash: loc.hash, state: state ?? null };
}

export function useParams<T extends Record<string, string | undefined> = Record<string, string | undefined>>(): T {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (useTParams as any)({ strict: false }) as T;
}

export function useSearchParams(): [URLSearchParams, (next: Record<string, string> | URLSearchParams, opts?: NavOpts) => void] {
  const searchStr = useRouterState({ select: (s) => s.location.searchStr });
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const nav = useTNavigate();
  const params = useMemo(() => new URLSearchParams(searchStr), [searchStr]);
  const set = useCallback(
    (next: Record<string, string> | URLSearchParams, opts?: NavOpts) => {
      const obj = next instanceof URLSearchParams ? Object.fromEntries(next) : next;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      nav({ to: pathname as any, search: obj as any, replace: opts?.replace });
    },
    [nav, pathname],
  );
  return [params, set];
}

type LinkProps = Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> & {
  to: To;
  replace?: boolean;
  state?: unknown;
  children?: ReactNode;
};

export const Link = forwardRef<HTMLAnchorElement, LinkProps>(({ to, replace, state, onClick, ...rest }, ref) => {
  const { path, search, hash } = splitTo(to);
  return (
    <TLink
      ref={ref}
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      to={path as any}
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      search={(search ?? {}) as any}
      hash={hash}
      replace={replace}
      onClick={(e) => {
        if (state !== undefined) (window as unknown as Record<string, unknown>)[STATE_KEY] = state;
        onClick?.(e);
      }}
      {...rest}
    />
  );
});
Link.displayName = "Link";

type NavLinkProps = Omit<LinkProps, "className"> & {
  end?: boolean;
  className?: string | ((s: { isActive: boolean; isPending: boolean }) => string);
};

export const NavLink = forwardRef<HTMLAnchorElement, NavLinkProps>(({ to, end, className, ...rest }, ref) => {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const target = splitTo(to).path;
  const isActive = end || target === "/" ? pathname === target : pathname === target || pathname.startsWith(target + "/");
  const cls = typeof className === "function" ? className({ isActive, isPending: false }) : className;
  return <Link ref={ref} to={to} className={cls} aria-current={isActive ? "page" : undefined} {...rest} />;
});
NavLink.displayName = "NavLink";

export function Navigate({ to, replace, state }: { to: To; replace?: boolean; state?: unknown }) {
  const navigate = useNavigate();
  useEffect(() => {
    navigate(to, { replace, state });
  }, [to, replace, state, navigate]);
  return null;
}

export const Outlet = TOutlet;
