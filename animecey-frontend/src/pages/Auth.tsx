import { useMemo, useState } from "react";
import { Link, Navigate, useNavigate, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Mail, Lock, User, Eye, EyeOff } from "lucide-react";
import { Footer } from "@/components/layout/Footer";
import { cn } from "@/lib/utils";
import { login as apiLogin, register as apiRegister } from "@/api/auth";
import { getApiError } from "@/api/axios";
import { useAuthStore, type AuthUser } from "@/stores/auth";
import { toast } from "sonner";

type Mode = "login" | "register";

function getPasswordStrength(pw: string): { score: number; label: string; color: string } {
  if (!pw) return { score: 0, label: "", color: "" };
  let s = 0;
  if (pw.length >= 4) s++;
  if (pw.length >= 8) s++;
  if (/[A-Z]/.test(pw)) s++;
  if (/[0-9]/.test(pw)) s++;
  if (/[^A-Za-z0-9]/.test(pw)) s++;
  if (s <= 1) return { score: 1, label: "Faible", color: "bg-red-500" };
  if (s <= 2) return { score: 2, label: "Insuffisant", color: "bg-orange-500" };
  if (s <= 3) return { score: 3, label: "Moyen", color: "bg-yellow-500" };
  if (s === 4) return { score: 4, label: "Bon", color: "bg-emerald-400" };
  return { score: 5, label: "Excellent", color: "bg-emerald-500" };
}

export default function Auth() {
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string })?.from ?? "/";
  const { isAuthenticated, login: loginStore } = useAuthStore();
  const [mode, setMode] = useState<Mode>("login");
  const [showPwd, setShowPwd] = useState(false);
  const [showPwd2, setShowPwd2] = useState(false);
  const [loading, setLoading] = useState(false);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const strength = useMemo(() => getPasswordStrength(password), [password]);

  if (isAuthenticated) {
    return <Navigate to={from} replace />;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (loading) return;

    if (mode === "register" && password.length < 4) {
      toast.error("Le mot de passe doit contenir au moins 4 caractères");
      return;
    }
    if (mode === "register" && password !== password2) {
      toast.error("Les mots de passe ne correspondent pas");
      return;
    }

    setLoading(true);
    try {
      if (mode === "login") {
        const data = await apiLogin({ email, password });
        loginStore(data.user as unknown as AuthUser, data.access_token);
        toast.success("Connecté !");
      } else {
        const data = await apiRegister({ username, email, password });
        loginStore(data.user as unknown as AuthUser, data.access_token);
        toast.success("Compte créé !");
      }
      navigate(from, { replace: true });
    } catch (err: unknown) {
      toast.error(getApiError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.35 }}
      className="min-h-screen bg-background flex flex-col"
    >
      <header className="px-6 py-5">
        <Link to="/" className="font-display font-extrabold text-2xl tracking-tight">
          Anime<span className="text-primary">Cey</span>
        </Link>
      </header>

      <main className="flex-1 flex items-center justify-center px-4 py-10">
        <motion.div
          initial={{ opacity: 0, y: 12, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.4 }}
          className="w-full max-w-md bg-surface border border-border-subtle rounded-2xl p-7 md:p-9 shadow-[var(--shadow-card)]"
        >
          <div className="text-center mb-6">
            <h1 className="font-display font-extrabold text-2xl">
              {mode === "login" ? "Bon retour" : "Crée ton compte"}
            </h1>
            <p className="text-sm text-muted-foreground font-body mt-1.5">
              {mode === "login"
                ? "Reprends ton anime là où tu l'avais laissé."
                : "Construis ta liste, like, commente — gratuitement."}
            </p>
          </div>

          <div className="relative grid grid-cols-2 bg-surface-2 rounded-lg p-1 mb-6">
            <motion.div
              layout
              transition={{ type: "spring", stiffness: 400, damping: 30 }}
              className={cn(
                "absolute top-1 bottom-1 w-[calc(50%-4px)] rounded-md bg-primary",
                mode === "login" ? "left-1" : "left-[calc(50%+2px)]",
              )}
            />
            {(["login", "register"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={cn(
                  "relative z-10 py-2 text-sm font-body font-semibold transition-colors",
                  mode === m ? "text-primary-foreground" : "text-muted-foreground",
                )}
              >
                {m === "login" ? "Se connecter" : "S'inscrire"}
              </button>
            ))}
          </div>

          <AnimatePresence mode="wait">
            <motion.form
              key={mode}
              initial={{ opacity: 0, x: mode === "login" ? -20 : 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: mode === "login" ? 20 : -20 }}
              transition={{ duration: 0.2 }}
              onSubmit={handleSubmit}
              className="space-y-4"
            >
              {mode === "register" && (
                <Field icon={<User className="w-4 h-4" />} label="Nom d'utilisateur">
                  <input
                    type="text"
                    placeholder="ton_pseudo"
                    className="auth-input"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    required
                  />
                </Field>
              )}

              <Field icon={<Mail className="w-4 h-4" />} label="Email">
                <input
                  type="email"
                  placeholder="toi@exemple.com"
                  className="auth-input"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </Field>

              <Field
                icon={<Lock className="w-4 h-4" />}
                label="Mot de passe"
                rightAction={
                  mode === "login" ? (
                    <button
                      type="button"
                      className="text-xs text-primary hover:text-primary-dim font-body font-semibold"
                    >
                      Oublié ?
                    </button>
                  ) : null
                }
              >
                <input
                  type={showPwd ? "text" : "password"}
                  placeholder="••••••••"
                  className="auth-input pr-10"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPwd((v) => !v)}
                  aria-label={showPwd ? "Masquer" : "Afficher"}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </Field>

              {mode === "register" && password.length > 0 && (
                <div className="space-y-1.5">
                  <div className="flex gap-1">
                    {[1, 2, 3, 4, 5].map((i) => (
                      <div
                        key={i}
                        className={cn(
                          "h-1 flex-1 rounded-full transition-colors",
                          i <= strength.score ? strength.color : "bg-border",
                        )}
                      />
                    ))}
                  </div>
                  <p className={cn(
                    "text-[11px] font-body font-semibold",
                    strength.score <= 1 ? "text-red-500" : strength.score <= 2 ? "text-orange-500" : strength.score <= 3 ? "text-yellow-500" : "text-emerald-500",
                  )}>
                    {strength.label}
                    {strength.score <= 2 && " — ajoute des majuscules, chiffres ou symboles"}
                  </p>
                </div>
              )}

              {mode === "register" && (
                <Field icon={<Lock className="w-4 h-4" />} label="Confirmer le mot de passe">
                  <input
                    type={showPwd2 ? "text" : "password"}
                    placeholder="••••••••"
                    className="auth-input pr-10"
                    value={password2}
                    onChange={(e) => setPassword2(e.target.value)}
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPwd2((v) => !v)}
                    aria-label={showPwd2 ? "Masquer" : "Afficher"}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showPwd2 ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </Field>
              )}

              <motion.button
                type="submit"
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.98 }}
                disabled={loading}
                className="w-full bg-primary text-primary-foreground font-body font-semibold rounded-lg py-3.5 transition-colors hover:bg-primary-dim disabled:opacity-50"
              >
                {loading
                  ? "Chargement..."
                  : mode === "login"
                    ? "Se connecter"
                    : "Créer mon compte"}
              </motion.button>

              {mode === "register" && (
                <p className="text-[11px] text-muted-foreground font-body text-center leading-relaxed">
                  En créant un compte, tu acceptes les conditions d'utilisation
                  et la politique de confidentialité.
                </p>
              )}
            </motion.form>
          </AnimatePresence>
        </motion.div>
      </main>

      <Footer />
    </motion.div>
  );
}

function Field({
  icon,
  label,
  children,
  rightAction,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
  rightAction?: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <label className="text-xs font-body font-semibold text-muted-foreground uppercase tracking-wider">
          {label}
        </label>
        {rightAction}
      </div>
      <div className="relative">
        <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted-foreground">
          {icon}
        </span>
        {children}
      </div>
    </div>
  );
}
