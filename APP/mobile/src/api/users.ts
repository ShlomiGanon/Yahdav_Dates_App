import { api } from './axios';
import type { Profile, Photo, Candidate, PeerProfile } from '../types/user';

export const usersApi = {
  getMyProfile: () =>
    api.get<Profile>('/users/me').then((r) => r.data),

  updateMyProfile: (data: Partial<Profile>) =>
    api.put<Profile>('/users/me', data).then((r) => r.data),

  uploadMainPhoto: (form: FormData) =>
    api.post<{ photo_url: string }>('/users/me/photo', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data),

  getMyPhotos: () =>
    api.get<Photo[]>('/users/me/photos').then((r) => r.data),

  uploadPhoto: (form: FormData) =>
    api.post<Photo>('/users/me/photos', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data),

  deletePhoto: (photo_id: string) =>
    api.delete(`/users/me/photos/${photo_id}`),

  discoverCandidates: (page: number, limit: number) =>
    api.get<Candidate[]>('/users/discover', { params: { page, limit } }).then((r) => r.data),

  getPeerProfile: (peer_id: string) =>
    api.get<PeerProfile>(`/users/${peer_id}`).then((r) => r.data),

  blockUser: (peer_id: string) =>
    api.post(`/users/${peer_id}/block`),

  getPeerPhotos: (peer_id: string) =>
    api.get<{ name: string; photos: Array<{ url: string }> }>(`/users/${peer_id}/photos`).then((r) => r.data),

  registerPushToken: (token: string, platform: string) =>
    api.post('/users/me/push-token', { token, platform }),

  unregisterPushToken: () =>
    api.delete('/users/me/push-token'),
};
