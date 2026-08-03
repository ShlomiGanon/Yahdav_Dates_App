import { api } from './axios';
import type { Conversation, Message } from '../types/chat';

export const chatApi = {
  getConversations: () =>
    api.get<Conversation[]>('/chat/conversations').then((r) => r.data),

  getMessages: (peer_id: string, params?: { limit?: number; before?: string }) =>
    api.get<Message[]>(`/chat/${peer_id}`, { params }).then((r) => r.data),

  sendMessage: (peer_id: string, content: string, msg_type: string) =>
    api.post<Message>(`/chat/${peer_id}`, { content, msg_type }).then((r) => r.data),

  markRead: (peer_id: string) =>
    api.put(`/chat/${peer_id}/read`),
};
