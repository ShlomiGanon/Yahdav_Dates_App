import type { AxiosInstance } from 'axios';
import type { Profile, Candidate, PeerProfile } from '../types/user';

export function createUsersApi(client: AxiosInstance)
{
    return {
        getMyProfile(): Promise<Profile>
        {
            return client.get('/users/me').then((r) => r.data);
        },

        updateMyProfile(data: Partial<Profile>): Promise<Profile>
        {
            return client.put('/users/me', data).then((r) => r.data);
        },

        discoverCandidates(page: number, limit: number): Promise<Candidate[]>
        {
            return client
                .get('/users/discover', { params: { page, limit } })
                .then((r) => r.data);
        },

        getPeerProfile(peer_id: string): Promise<PeerProfile>
        {
            return client.get(`/users/${peer_id}`).then((r) => r.data);
        },

        getPeerPhotos(peer_id: string): Promise<{ name: string; photos: string[] }>
        {
            return client.get(`/users/${peer_id}/photos`).then((r) => r.data);
        },

        blockUser(peer_id: string): Promise<void>
        {
            return client
                .post(`/users/${peer_id}/block`)
                .then(() => undefined);
        },
    };
}
