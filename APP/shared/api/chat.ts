import type { AxiosInstance } from 'axios';
import type { Message, Conversation, MsgType } from '../types/chat';
import type { ApiEnvelope } from '../types/api';

interface GetMessagesParams
{
    limit?:  number;
    before?: string;
}

export function createChatApi(client: AxiosInstance)
{
    return {
        getConversations(): Promise<ApiEnvelope & { conversations: Conversation[] }>
        {
            return client.get('/chat/conversations').then((r) => r.data);
        },

        getMessages(peer_id: string, params?: GetMessagesParams): Promise<ApiEnvelope & { messages: Message[] }>
        {
            return client
                .get(`/chat/${peer_id}`, { params })
                .then((r) => r.data);
        },

        sendMessage(
            peer_id:  string,
            content:  string,
            msg_type: MsgType = 'TEXT',
        ): Promise<ApiEnvelope & Message>
        {
            return client
                .post(`/chat/${peer_id}`, { content, msg_type })
                .then((r) => r.data);
        },

        markRead(peer_id: string): Promise<ApiEnvelope>
        {
            return client
                .put(`/chat/${peer_id}/read`)
                .then((r) => r.data);
        },
    };
}
