import api from "./axios";

export async function register(data: { username: string; email: string; password: string }) {
  const res = await api.post("/auth/register", data);
  return res.data as { access_token: string; user: Record<string, unknown> };
}

export async function login(data: { email: string; password: string }) {
  const res = await api.post("/auth/login", data);
  return res.data as { access_token: string; user: Record<string, unknown> };
}

export async function getMe() {
  const res = await api.get("/auth/me");
  return res.data;
}

export async function updateProfile(data: { username?: string; email?: string; avatar_url?: string }) {
  const res = await api.put("/auth/me", data);
  return res.data;
}

export async function changePassword(data: { current_password: string; new_password: string }) {
  const res = await api.put("/auth/password", data);
  return res.data;
}

export async function deleteAccount() {
  await api.delete("/auth/me");
}
