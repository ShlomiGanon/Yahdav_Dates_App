import type { AxiosInstance } from 'axios';
import type { Profile, Candidate, PeerProfile, Photo } from '../types/user';
import type { ApiEnvelope } from '../types/api';

export function createUsersApi(client: AxiosInstance)
{
    return {
        getMyProfile(): Promise<ApiEnvelope & Profile>
        {
            return client.get('/api/users/me').then((r) => r.data);
        },

        updateMyProfile(data: Partial<Profile>): Promise<ApiEnvelope & Profile>
        {
            return client.put('/api/users/me', data).then((r) => r.data);
        },

        uploadMainPhoto(form: FormData): Promise<ApiEnvelope & { photo_url: string }>
        {
            return client.post('/api/users/me/photo', form, {
                headers: { 'Content-Type': 'multipart/form-data' },
            }).then((r) => r.data);
        },

        discoverCandidates(page: number, limit: number): Promise<ApiEnvelope & { candidates: Candidate[] }>
        {
            return client
                .get('/api/users/discover', { params: { page, limit } })
                .then((r) => r.data);
        },

        getPeerProfile(peer_id: string): Promise<ApiEnvelope & PeerProfile>
        {
            return client.get(`/api/users/${peer_id}`).then((r) => r.data);
        },

        getPeerPhotos(peer_id: string): Promise<ApiEnvelope & { name: string; photos: Photo[] }>
        {
            return client.get(`/api/users/${peer_id}/photos`).then((r) => r.data);
        },

        blockUser(peer_id: string): Promise<ApiEnvelope>
        {
            return client
                .post(`/api/users/${peer_id}/block`)
                .then((r) => r.data);
        },

        getMyPhotos(): Promise<ApiEnvelope & { photos: Photo[] }>
        {
            return client.get('/api/users/me/photos').then((r) => r.data);
        },

        uploadPhoto(form: FormData): Promise<ApiEnvelope & Photo>
        {
            return client.post('/api/users/me/photos', form, {
                headers: { 'Content-Type': 'multipart/form-data' },
            }).then((r) => r.data);
        },

        deleteMyPhoto(photo_id: string): Promise<ApiEnvelope>
        {
            return client.delete(`/api/users/me/photos/${photo_id}`).then((r) => r.data);
        },

        registerPushToken(token: string, platform?: 'ios' | 'android'): Promise<ApiEnvelope>
        {
            return client.post('/api/users/me/push-token', { token, platform }).then((r) => r.data);
        },

        unregisterPushToken(): Promise<ApiEnvelope>
        {
            return client.delete('/api/users/me/push-token').then((r) => r.data);
        },
    };
}
