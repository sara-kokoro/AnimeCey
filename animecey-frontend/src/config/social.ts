/**
 * Réseaux et dons de Magi-Stream.
 * - telegram : mets le lien de ta chaîne/groupe (https://t.me/...) ici, ou dans VITE_TELEGRAM_URL sur Vercel.
 *   Vide = le bouton « Nous suivre sur Telegram » n'est pas affiché.
 * - wallets : adresses de dons (une par réseau). Les mêmes adresses sont dans app/www/offline.html.
 */
export const SOCIAL = {
  telegram: ((import.meta.env.VITE_TELEGRAM_URL as string | undefined) ?? "").trim(),
};

export interface Wallet {
  id: string;
  name: string;
  networks: string;
  address: string;
}

export const WALLETS: Wallet[] = [
  { id: "ton", name: "TON", networks: "Réseau TON (et jettons TON)", address: "UQCnV7ridLgpX5ijC9nUezc5Xj9aqz5qvdpLuycpVLAIwe7d" },
  {
    id: "evm",
    name: "Ethereum et réseaux compatibles",
    networks: "Ethereum, BNB Chain, Robinhood Chain, Arbitrum, Polygon, Base, Avalanche",
    address: "0x7D4C4a0398eac6a796eC71C658278a8F20e182FF",
  },
  { id: "sol", name: "Solana", networks: "Réseau Solana", address: "4pDxQq8RNiutmmM5kYHCHPCKok6AF6ZaebT59kH2Xw8U" },
  { id: "tron", name: "Tron", networks: "Réseau Tron (TRC-20)", address: "TGuwVYkbp4GEG85cmHFc3FtpHRTfHcnBRh" },
  { id: "btc", name: "Bitcoin", networks: "Réseau Bitcoin", address: "bc1qqtpnrz4sts6usg294gt89sy8khl7ddezcgkdsh" },
];
