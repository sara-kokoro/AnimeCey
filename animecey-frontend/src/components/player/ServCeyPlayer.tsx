import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  FastForward,
  Loader2,
  Maximize,
  Minimize,
  Pause,
  PictureInPicture2,
  Play,
  RotateCcw,
  RotateCw,
  SkipForward,
  Volume1,
  Volume2,
  VolumeX,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  src: string;
  title?: string;
  subtitle?: string;
  /** Clé pour retenir la position de lecture (ex. l'id de l'épisode). */
  storageKey?: string;
  /** Appelé quand la vidéo est prête à être lue (pour masquer le chargement de la page). */
  onReady?: () => void;
  /** Passe à l'épisode suivant (bouton + lecture automatique à la fin). */
  onNext?: () => void;
  hasNext?: boolean;
  /** Durée du saut d'intro, en secondes (0 pour masquer le bouton). */
  skipIntroSeconds?: number;
}

const SPEEDS = [0.5, 0.75, 1, 1.25, 1.5, 2];
const HIDE_AFTER_MS = 2800;
const AUTONEXT_SECONDS = 6;

function fmt(t: number): string {
  if (!isFinite(t) || t < 0) t = 0;
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = Math.floor(t % 60);
  const mm = h > 0 ? String(m).padStart(2, "0") : String(m);
  return `${h > 0 ? `${h}:` : ""}${mm}:${String(s).padStart(2, "0")}`;
}

function readNumber(key: string, fallback: number): number {
  try {
    const v = parseFloat(localStorage.getItem(key) ?? "");
    return isFinite(v) ? v : fallback;
  } catch {
    return fallback;
  }
}

function writeValue(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* stockage indisponible : on ignore */
  }
}

export function ServCeyPlayer({
  src,
  title,
  subtitle,
  storageKey,
  onReady,
  onNext,
  hasNext = false,
  skipIntroSeconds = 85,
}: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const barRef = useRef<HTMLDivElement>(null);
  const hideTimer = useRef<number | null>(null);
  const lastTap = useRef<{ t: number; x: number }>({ t: 0, x: 0 });
  const tapTimer = useRef<number | null>(null);
  const dragging = useRef(false);
  const lastSave = useRef(0);

  const [playing, setPlaying] = useState(false);
  const [current, setCurrent] = useState(0);
  const [duration, setDuration] = useState(0);
  const [buffered, setBuffered] = useState(0);
  const [volume, setVolume] = useState(() => Math.min(1, Math.max(0, readNumber("servcey:volume", 1))));
  const [muted, setMuted] = useState(false);
  const [speed, setSpeed] = useState(() => readNumber("servcey:speed", 1));
  const [menuOpen, setMenuOpen] = useState(false);
  const [controlsVisible, setControlsVisible] = useState(true);
  const [waiting, setWaiting] = useState(true);
  const [error, setError] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [hoverTime, setHoverTime] = useState<{ x: number; t: number } | null>(null);
  const [flash, setFlash] = useState<{ side: "left" | "right"; id: number } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [countdown, setCountdown] = useState<number | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  const posKey = storageKey ? `servcey:pos:${storageKey}` : null;
  const canPip = typeof document !== "undefined" && "pictureInPictureEnabled" in document;

  /* ── affichage / masquage des contrôles ─────────────────────────────── */
  const revealControls = useCallback(() => {
    setControlsVisible(true);
    if (hideTimer.current) window.clearTimeout(hideTimer.current);
    hideTimer.current = window.setTimeout(() => {
      const v = videoRef.current;
      if (v && !v.paused && !dragging.current) {
        setControlsVisible(false);
        setMenuOpen(false);
      }
    }, HIDE_AFTER_MS);
  }, []);

  useEffect(() => () => {
    if (hideTimer.current) window.clearTimeout(hideTimer.current);
    if (tapTimer.current) window.clearTimeout(tapTimer.current);
  }, []);

  const showNotice = useCallback((text: string) => {
    setNotice(text);
    window.setTimeout(() => setNotice((n) => (n === text ? null : n)), 2200);
  }, []);

  /* ── actions ────────────────────────────────────────────────────────── */
  const togglePlay = useCallback(() => {
    const v = videoRef.current;
    if (!v) return;
    if (v.paused || v.ended) {
      v.play().catch(() => setError(true));
    } else {
      v.pause();
    }
  }, []);

  const seekBy = useCallback((delta: number) => {
    const v = videoRef.current;
    if (!v || !isFinite(v.duration)) return;
    v.currentTime = Math.min(Math.max(0, v.currentTime + delta), v.duration);
  }, []);

  const seekTo = useCallback((t: number) => {
    const v = videoRef.current;
    if (!v || !isFinite(v.duration)) return;
    v.currentTime = Math.min(Math.max(0, t), v.duration);
    setCurrent(v.currentTime);
  }, []);

  const toggleMute = useCallback(() => {
    const v = videoRef.current;
    if (!v) return;
    v.muted = !v.muted;
    setMuted(v.muted);
  }, []);

  const changeVolume = useCallback((val: number) => {
    const v = videoRef.current;
    if (!v) return;
    const clamped = Math.min(1, Math.max(0, val));
    v.volume = clamped;
    v.muted = clamped === 0;
    setVolume(clamped);
    setMuted(v.muted);
    writeValue("servcey:volume", String(clamped));
  }, []);

  const changeSpeed = useCallback((s: number) => {
    const v = videoRef.current;
    if (v) v.playbackRate = s;
    setSpeed(s);
    setMenuOpen(false);
    writeValue("servcey:speed", String(s));
    showNotice(`Vitesse ×${s}`);
  }, [showNotice]);

  const toggleFullscreen = useCallback(() => {
    const el = wrapRef.current;
    const v = videoRef.current as (HTMLVideoElement & { webkitEnterFullscreen?: () => void }) | null;
    if (!el || !v) return;
    if (document.fullscreenElement) {
      document.exitFullscreen().catch(() => undefined);
    } else if (el.requestFullscreen) {
      el.requestFullscreen().catch(() => undefined);
    } else if (v.webkitEnterFullscreen) {
      v.webkitEnterFullscreen(); // iPhone : plein écran natif de la vidéo
    }
  }, []);

  const togglePip = useCallback(async () => {
    const v = videoRef.current;
    if (!v) return;
    try {
      if (document.pictureInPictureElement) await document.exitPictureInPicture();
      else await v.requestPictureInPicture();
    } catch {
      /* non pris en charge */
    }
  }, []);

  const skipIntro = useCallback(() => {
    seekBy(skipIntroSeconds);
    showNotice(`Intro passée (+${skipIntroSeconds} s)`);
  }, [seekBy, skipIntroSeconds, showNotice]);

  /* ── événements de la vidéo ─────────────────────────────────────────── */
  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    v.volume = volume;
    v.playbackRate = speed;

    const onLoaded = () => {
      setDuration(v.duration || 0);
      setWaiting(false);
      onReady?.();
      if (posKey) {
        const saved = readNumber(posKey, 0);
        if (saved > 10 && v.duration && saved < v.duration * 0.95) {
          v.currentTime = saved;
          showNotice(`Reprise à ${fmt(saved)}`);
        }
      }
    };
    const onTime = () => {
      setCurrent(v.currentTime);
      if (v.buffered.length) setBuffered(v.buffered.end(v.buffered.length - 1));
      if (posKey && Date.now() - lastSave.current > 4000) {
        lastSave.current = Date.now();
        writeValue(posKey, String(v.currentTime));
      }
    };
    const onPlay = () => { setPlaying(true); setCountdown(null); revealControls(); };
    const onPause = () => { setPlaying(false); setControlsVisible(true); };
    const onWaiting = () => setWaiting(true);
    const onCanPlay = () => setWaiting(false);
    const onErr = () => { setError(true); setWaiting(false); onReady?.(); };
    const onEnd = () => {
      setPlaying(false);
      setControlsVisible(true);
      if (posKey) writeValue(posKey, "0");
      if (hasNext && onNext) setCountdown(AUTONEXT_SECONDS);
    };
    const onDuration = () => setDuration(v.duration || 0);

    v.addEventListener("loadedmetadata", onLoaded);
    v.addEventListener("durationchange", onDuration);
    v.addEventListener("timeupdate", onTime);
    v.addEventListener("progress", onTime);
    v.addEventListener("play", onPlay);
    v.addEventListener("pause", onPause);
    v.addEventListener("waiting", onWaiting);
    v.addEventListener("canplay", onCanPlay);
    v.addEventListener("playing", onCanPlay);
    v.addEventListener("error", onErr);
    v.addEventListener("ended", onEnd);
    return () => {
      v.removeEventListener("loadedmetadata", onLoaded);
      v.removeEventListener("durationchange", onDuration);
      v.removeEventListener("timeupdate", onTime);
      v.removeEventListener("progress", onTime);
      v.removeEventListener("play", onPlay);
      v.removeEventListener("pause", onPause);
      v.removeEventListener("waiting", onWaiting);
      v.removeEventListener("canplay", onCanPlay);
      v.removeEventListener("playing", onCanPlay);
      v.removeEventListener("error", onErr);
      v.removeEventListener("ended", onEnd);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [src, retryKey, posKey, hasNext]);

  /* ── compte à rebours « épisode suivant » ───────────────────────────── */
  useEffect(() => {
    if (countdown === null) return;
    if (countdown <= 0) {
      setCountdown(null);
      onNext?.();
      return;
    }
    const id = window.setTimeout(() => setCountdown((c) => (c === null ? null : c - 1)), 1000);
    return () => window.clearTimeout(id);
  }, [countdown, onNext]);

  /* ── plein écran ────────────────────────────────────────────────────── */
  useEffect(() => {
    const onFs = () => setFullscreen(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", onFs);
    return () => document.removeEventListener("fullscreenchange", onFs);
  }, []);

  /* ── clavier ────────────────────────────────────────────────────────── */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = wrapRef.current;
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (!el || tag === "INPUT" || tag === "TEXTAREA" || (e.target as HTMLElement | null)?.isContentEditable) return;
      const inside = el.contains(document.activeElement) || el.matches(":hover") || document.fullscreenElement === el;
      if (!inside) return;
      switch (e.key) {
        case " ":
        case "k": e.preventDefault(); togglePlay(); break;
        case "ArrowLeft": e.preventDefault(); seekBy(-5); break;
        case "ArrowRight": e.preventDefault(); seekBy(5); break;
        case "j": seekBy(-10); break;
        case "l": seekBy(10); break;
        case "ArrowUp": e.preventDefault(); changeVolume((videoRef.current?.volume ?? 1) + 0.1); break;
        case "ArrowDown": e.preventDefault(); changeVolume((videoRef.current?.volume ?? 1) - 0.1); break;
        case "m": toggleMute(); break;
        case "f": toggleFullscreen(); break;
        default: return;
      }
      revealControls();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [togglePlay, seekBy, changeVolume, toggleMute, toggleFullscreen, revealControls]);

  /* ── barre de progression (souris + tactile) ────────────────────────── */
  const timeFromPointer = (clientX: number): number => {
    const bar = barRef.current;
    if (!bar || !duration) return 0;
    const rect = bar.getBoundingClientRect();
    return Math.min(1, Math.max(0, (clientX - rect.left) / rect.width)) * duration;
  };

  const onBarDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.stopPropagation();
    dragging.current = true;
    (e.currentTarget as HTMLDivElement).setPointerCapture(e.pointerId);
    seekTo(timeFromPointer(e.clientX));
  };
  const onBarMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const t = timeFromPointer(e.clientX);
    const rect = barRef.current?.getBoundingClientRect();
    if (rect) setHoverTime({ x: e.clientX - rect.left, t });
    if (dragging.current) seekTo(t);
  };
  const onBarUp = (e: React.PointerEvent<HTMLDivElement>) => {
    e.stopPropagation();
    dragging.current = false;
    revealControls();
  };

  /* ── zone vidéo : clic, double-clic / double tape ───────────────────── */
  const onSurfaceClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const now = Date.now();
    const isDouble = now - lastTap.current.t < 300 && Math.abs(x - lastTap.current.x) < 60;
    lastTap.current = { t: now, x };

    if (isDouble) {
      if (tapTimer.current) window.clearTimeout(tapTimer.current);
      const third = rect.width / 3;
      if (x < third) { seekBy(-10); setFlash({ side: "left", id: now }); }
      else if (x > third * 2) { seekBy(10); setFlash({ side: "right", id: now }); }
      else toggleFullscreen();
      revealControls();
      return;
    }
    if (tapTimer.current) window.clearTimeout(tapTimer.current);
    tapTimer.current = window.setTimeout(() => {
      if (menuOpen) { setMenuOpen(false); return; }
      const coarse = window.matchMedia?.("(pointer: coarse)").matches;
      if (coarse && !controlsVisible) revealControls();   // mobile : un tap affiche les contrôles
      else { togglePlay(); revealControls(); }
    }, 220);
  };

  useEffect(() => {
    if (!flash) return;
    const id = window.setTimeout(() => setFlash(null), 600);
    return () => window.clearTimeout(id);
  }, [flash]);

  const pct = duration ? (current / duration) * 100 : 0;
  const bufPct = duration ? (buffered / duration) * 100 : 0;
  const VolIcon = muted || volume === 0 ? VolumeX : volume < 0.5 ? Volume1 : Volume2;
  const showSkipIntro = skipIntroSeconds > 0 && current > 8 && current < 240 && !error;
  const show = controlsVisible || !playing || menuOpen;

  return (
    <div
      ref={wrapRef}
      tabIndex={0}
      onMouseMove={revealControls}
      onTouchStart={() => { /* le tap est géré par la surface */ }}
      className={cn(
        "group/player relative w-full h-full bg-black select-none overflow-hidden outline-none",
        !show && playing && "cursor-none",
      )}
    >
      <video
        key={`${src}-${retryKey}`}
        ref={videoRef}
        src={src}
        autoPlay
        playsInline
        preload="metadata"
        className="absolute inset-0 w-full h-full object-contain bg-black"
      />

      {/* Surface cliquable */}
      <div className="absolute inset-0" onClick={onSurfaceClick} />

      {/* Indicateur de double tape */}
      {flash && (
        <div
          key={flash.id}
          className={cn(
            "pointer-events-none absolute top-0 bottom-0 w-1/3 flex items-center justify-center animate-fade-in",
            flash.side === "left" ? "left-0 rounded-r-[100%]" : "right-0 rounded-l-[100%]",
            "bg-white/10",
          )}
        >
          <div className="flex flex-col items-center text-white font-body text-sm font-semibold gap-1">
            {flash.side === "left" ? <RotateCcw className="w-7 h-7" /> : <RotateCw className="w-7 h-7" />}
            10 s
          </div>
        </div>
      )}

      {/* Chargement */}
      {waiting && !error && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <Loader2 className="w-12 h-12 text-primary animate-spin drop-shadow-lg" />
        </div>
      )}

      {/* Gros bouton lecture */}
      {!playing && !waiting && !error && countdown === null && (
        <button
          onClick={(e) => { e.stopPropagation(); togglePlay(); }}
          aria-label="Lire"
          className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-20 h-20 rounded-full bg-primary text-primary-foreground flex items-center justify-center shadow-2xl shadow-primary/30 hover:scale-105 active:scale-95 transition-transform"
        >
          <Play className="w-9 h-9 ml-1" fill="currentColor" />
        </button>
      )}

      {/* Message court (reprise, vitesse...) */}
      {notice && (
        <div className="pointer-events-none absolute top-14 left-1/2 -translate-x-1/2 rounded-full bg-black/75 backdrop-blur px-4 py-1.5 text-xs font-body font-semibold text-white">
          {notice}
        </div>
      )}

      {/* Erreur */}
      {error && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/85 text-center px-6">
          <AlertTriangle className="w-10 h-10 text-primary" />
          <p className="text-white font-body text-sm max-w-xs">
            Cette vidéo ne peut pas être lue pour le moment. Essaie un autre serveur ou réessaie.
          </p>
          <button
            onClick={() => { setError(false); setWaiting(true); setRetryKey((k) => k + 1); }}
            className="px-5 py-2 rounded-lg bg-primary text-primary-foreground font-body font-semibold text-sm"
          >
            Réessayer
          </button>
        </div>
      )}

      {/* Épisode suivant */}
      {countdown !== null && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-black/80 text-center px-6">
          <p className="text-white/70 font-body text-sm">Épisode suivant dans</p>
          <p className="text-primary font-display font-bold text-6xl leading-none">{countdown}</p>
          <div className="flex gap-3">
            <button
              onClick={() => { setCountdown(null); onNext?.(); }}
              className="px-5 py-2 rounded-lg bg-primary text-primary-foreground font-body font-semibold text-sm"
            >
              Lire maintenant
            </button>
            <button
              onClick={() => setCountdown(null)}
              className="px-5 py-2 rounded-lg bg-white/10 text-white font-body font-semibold text-sm hover:bg-white/20"
            >
              Annuler
            </button>
          </div>
        </div>
      )}

      {/* Bouton « Passer l'intro » */}
      {showSkipIntro && show && (
        <button
          onClick={(e) => { e.stopPropagation(); skipIntro(); }}
          className="absolute right-3 bottom-20 md:bottom-24 inline-flex items-center gap-2 rounded-lg border border-white/30 bg-black/60 backdrop-blur px-3.5 py-2 text-xs md:text-sm font-body font-semibold text-white hover:bg-primary hover:text-primary-foreground hover:border-primary transition-colors"
        >
          <FastForward className="w-4 h-4" />
          Passer l'intro
        </button>
      )}

      {/* Barre du haut */}
      <div
        className={cn(
          "pointer-events-none absolute top-0 inset-x-0 px-3 md:px-5 pt-3 pb-10 bg-gradient-to-b from-black/80 to-transparent transition-opacity duration-300",
          show ? "opacity-100" : "opacity-0",
        )}
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="shrink-0 rounded-md bg-primary text-primary-foreground text-[10px] md:text-xs font-display font-bold px-2 py-0.5 tracking-wide">
            ServCey 1
          </span>
          <div className="min-w-0">
            {title && <p className="truncate text-white font-display font-semibold text-sm md:text-base leading-tight">{title}</p>}
            {subtitle && <p className="truncate text-white/60 font-body text-[11px] md:text-xs">{subtitle}</p>}
          </div>
        </div>
      </div>

      {/* Barre du bas */}
      <div
        onClick={(e) => e.stopPropagation()}
        className={cn(
          "absolute bottom-0 inset-x-0 px-3 md:px-5 pb-2 md:pb-3 pt-12 bg-gradient-to-t from-black/90 via-black/50 to-transparent transition-opacity duration-300",
          show ? "opacity-100" : "opacity-0 pointer-events-none",
        )}
      >
        {/* progression */}
        <div
          ref={barRef}
          onPointerDown={onBarDown}
          onPointerMove={onBarMove}
          onPointerUp={onBarUp}
          onPointerLeave={() => setHoverTime(null)}
          className="group/bar relative h-5 flex items-center cursor-pointer touch-none"
          role="slider"
          aria-label="Position de lecture"
          aria-valuemin={0}
          aria-valuemax={Math.round(duration)}
          aria-valuenow={Math.round(current)}
        >
          <div className="relative w-full h-1 group-hover/bar:h-1.5 rounded-full bg-white/25 transition-all">
            <div className="absolute inset-y-0 left-0 rounded-full bg-white/35" style={{ width: `${bufPct}%` }} />
            <div className="absolute inset-y-0 left-0 rounded-full bg-primary" style={{ width: `${pct}%` }} />
            <div
              className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3.5 h-3.5 rounded-full bg-primary shadow-lg shadow-black/50 scale-0 group-hover/bar:scale-100 transition-transform"
              style={{ left: `${pct}%` }}
            />
          </div>
          {hoverTime && (
            <div
              className="pointer-events-none absolute -top-7 -translate-x-1/2 rounded bg-black/85 px-2 py-0.5 text-[11px] font-body font-semibold text-white"
              style={{ left: hoverTime.x }}
            >
              {fmt(hoverTime.t)}
            </div>
          )}
        </div>

        {/* boutons */}
        <div className="flex items-center gap-1 md:gap-2 text-white">
          <IconBtn label={playing ? "Pause" : "Lire"} onClick={togglePlay}>
            {playing ? <Pause className="w-6 h-6" fill="currentColor" /> : <Play className="w-6 h-6" fill="currentColor" />}
          </IconBtn>
          <IconBtn label="Reculer de 10 secondes" onClick={() => seekBy(-10)} className="hidden sm:inline-flex">
            <RotateCcw className="w-5 h-5" />
          </IconBtn>
          <IconBtn label="Avancer de 10 secondes" onClick={() => seekBy(10)} className="hidden sm:inline-flex">
            <RotateCw className="w-5 h-5" />
          </IconBtn>
          {hasNext && (
            <IconBtn label="Épisode suivant" onClick={() => onNext?.()}>
              <SkipForward className="w-5 h-5" fill="currentColor" />
            </IconBtn>
          )}

          <div className="group/vol hidden md:flex items-center">
            <IconBtn label={muted ? "Activer le son" : "Couper le son"} onClick={toggleMute}>
              <VolIcon className="w-5 h-5" />
            </IconBtn>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={muted ? 0 : volume}
              onChange={(e) => changeVolume(parseFloat(e.target.value))}
              aria-label="Volume"
              className="w-0 group-hover/vol:w-20 focus:w-20 transition-all duration-200 accent-[hsl(var(--primary))] cursor-pointer"
            />
          </div>

          <span className="ml-1 font-body text-xs md:text-sm tabular-nums text-white/90 whitespace-nowrap">
            {fmt(current)} <span className="text-white/50">/ {fmt(duration)}</span>
          </span>

          <div className="flex-1" />

          {/* vitesse */}
          <div className="relative">
            <button
              onClick={() => setMenuOpen((o) => !o)}
              aria-label="Vitesse de lecture"
              className={cn(
                "h-9 min-w-9 px-2 rounded-lg font-body font-bold text-xs md:text-sm transition-colors hover:bg-white/15",
                speed !== 1 && "text-primary",
              )}
            >
              ×{speed}
            </button>
            {menuOpen && (
              <div className="absolute bottom-11 right-0 min-w-[110px] rounded-xl border border-white/15 bg-black/90 backdrop-blur p-1.5 shadow-2xl">
                <p className="px-2.5 pt-1 pb-1.5 text-[10px] uppercase tracking-wider text-white/50 font-body font-semibold">
                  Vitesse
                </p>
                {SPEEDS.map((s) => (
                  <button
                    key={s}
                    onClick={() => changeSpeed(s)}
                    className={cn(
                      "w-full text-left px-2.5 py-1.5 rounded-lg text-sm font-body hover:bg-white/10",
                      s === speed ? "text-primary font-bold" : "text-white",
                    )}
                  >
                    {s === 1 ? "Normale" : `×${s}`}
                  </button>
                ))}
              </div>
            )}
          </div>

          {canPip && (
            <IconBtn label="Image dans l'image" onClick={togglePip} className="hidden md:inline-flex">
              <PictureInPicture2 className="w-5 h-5" />
            </IconBtn>
          )}
          <IconBtn label={fullscreen ? "Quitter le plein écran" : "Plein écran"} onClick={toggleFullscreen}>
            {fullscreen ? <Minimize className="w-5 h-5" /> : <Maximize className="w-5 h-5" />}
          </IconBtn>
        </div>
      </div>
    </div>
  );
}

function IconBtn({
  children,
  label,
  onClick,
  className,
}: {
  children: React.ReactNode;
  label: string;
  onClick: () => void;
  className?: string;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className={cn(
        "h-9 w-9 inline-flex items-center justify-center rounded-lg text-white hover:bg-white/15 hover:text-primary active:scale-95 transition-all",
        className,
      )}
    >
      {children}
    </button>
  );
}
