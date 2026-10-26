import api from "./axios";

export async function subscribe(endpoint: string, p256dh: string, auth: string) {
  const res = await api.post("/push/subscribe", { endpoint, p256dh, auth });
  return res.data;
}

export async function unsubscribe(endpoint: string) {
  const res = await api.delete("/push/unsubscribe", { data: { endpoint } });
  return res.data;
}
