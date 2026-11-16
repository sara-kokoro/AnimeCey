/** API publique des dons (JessiKaPay). Aucun compte requis. */
const BASE = (import.meta.env.VITE_JKPAY_API_URL as string | undefined)?.replace(/\/+$/, "") || "https://preferred-antonia-youtub-c1a62de8.koyeb.app";

export type DonateCountry = {
  code: string;
  name: string;
  dial: string;
  currency: string;
  rate_fcfa?: number;
  min: number;
  max: number;
  presets: number[];
  operators: string[];
};
export type DonateConfig = { countries: DonateCountry[] };
export type DonationStatus = "awaiting_payment" | "paid" | "failed" | "expired";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = (data as { detail?: unknown })?.detail;
    throw new Error(typeof detail === "string" ? detail : "Une erreur est survenue. Réessaie dans un instant.");
  }
  return data as T;
}

export const fetchDonateConfig = () => call<DonateConfig>("/donate/config");

export const createDonation = (body: { amount: number; country: string; operator: string; phone: string; donor_name?: string }) =>
  call<{ id: string; status: DonationStatus; payment_url: string }>("/donate/create", { method: "POST", body: JSON.stringify(body) });

export const fetchDonationStatus = (id: string) =>
  call<{ status: DonationStatus; amount: number; currency: string; donor_name: string | null }>(`/donate/status/${encodeURIComponent(id)}`);
