import api from "./axios";

export interface CommentData {
  id: number;
  user: { id: number; username: string; avatar_url?: string };
  content: string;
  likes_count: number;
  is_liked_by_me: boolean;
  parent_id?: number;
  replies: CommentData[];
  created_at: string;
}

export interface PaginatedComments {
  items: CommentData[];
  total: number;
  page: number;
  pages: number;
}

export async function fetchComments(
  episodeId: number,
  page = 1,
  limit = 20,
): Promise<PaginatedComments> {
  const res = await api.get("/comments", { params: { episode_id: episodeId, page, limit } });
  return res.data;
}

export async function createComment(data: {
  episode_id: number;
  content: string;
  parent_id?: number;
}) {
  const res = await api.post("/comments", data);
  return res.data;
}

export async function likeComment(id: number) {
  const res = await api.post(`/comments/${id}/like`);
  return res.data as { liked: boolean; likes_count: number };
}

export async function unlikeComment(id: number) {
  const res = await api.delete(`/comments/${id}/like`);
  return res.data as { liked: boolean; likes_count: number };
}
