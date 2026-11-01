import api from "./axios";

export interface AdData {
  id: number;
  media_url: string;
  mime: string;
  text: string | null;
  button_text: string | null;
  /** adresse qui compte le clic puis redirige vers le lien de l'annonceur */
  link: string;
  button_link: string | null;
}

export interface AdContact {
  telegram: string;
  telegram_name: string;
  email: string;
}

export interface AdResponse {
  ad: AdData | null;
  contact: AdContact;
}

export type AdSlotKey = "home_top" | "home_bottom" | "detail" | "watch" | "downloads" | "offline";

export async function fetchAd(slot: AdSlotKey): Promise<AdResponse> {
  const res = await api.get("/ads", { params: { slot } });
  return res.data;
}

export async function reportAdView(id: number, slot: AdSlotKey): Promise<void> {
  await api.post(`/ads/${id}/view`, { slot });
}
