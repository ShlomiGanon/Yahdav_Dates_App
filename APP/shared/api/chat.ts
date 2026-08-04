import type { AxiosInstance } from 'axios';
import type { Message, Conversation } from '../types/chat';

interface GetMessagesParams
{
    limit?:  number;
    before?: string;
}

export function createChatApi(client: AxiosInstance)
{
    return {
        getConversations(): Promise<Conversation[]>
        {
            return client.get('/chat/conversations').then((r) => r.data);
        },

        getMessages(peer_id: string, params?: GetMessagesParams): Promise<Message[]>
        {
            return client
                .get(`/chat/${peer_id}`, { params })
                .then((r) => r.data);
        },

        sendMessage(
            peer_id:  string,
            content:  string,
            msg_type: string = 'TEXT',
        ): Promise<Message>
        {
            return client
                .post(`/chat/${peer_id}`, { content, msg_type })
                .then((r) => r.data);
        },

        markRead(peer_id: string): Promise<void>
        {
            return client
                .put(`/chat/${peer_id}/read`)
                .then(() => undefined);
        },
    };
}
