import { api } from './axios';
import type { Profile, Photo, Candidate, PeerProfile } from '../types/user';
import type { ApiEnvelope } from '../types/api';

export const usersApi = {
  getMyProfile: () =>
    api.get<ApiEnvelope & Profile>('/users/me').then((r) => r.data),

  updateMyProfile: (data: Partial<Profile>) =>
    api.put<ApiEnvelope & Profile>('/users/me', data).then((r) => r.data),

  uploadMainPhoto: (form: FormData) =>
    api.post<ApiEnvelope & { photo_url: string }>('/users/me/photo', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data),

  getMyPhotos: () =>
    api.get<ApiEnvelope & { photos: Photo[] }>('/users/me/photos').then((r) => r.data),

  uploadPhoto: (form: FormData) =>
    api.post<ApiEnvelope & Photo>('/users/me/photos', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data),

  deletePhoto: (photo_id: string) =>
    api.delete<ApiEnvelope>(`/users/me/photos/${photo_id}`).then((r) => r.data),

  discoverCandidates: (page: number, limit: number) =>
    api.get<ApiEnvelope & { candidates: Candidate[] }>('/users/discover', { params: { page, limit } }).then((r) => r.data),

  getPeerProfile: (peer_id: string) =>
    api.get<ApiEnvelope & PeerProfile>(`/users/${peer_id}`).then((r) => r.data),

  blockUser: (peer_id: string) =>
    api.post<ApiEnvelope>(`/users/${peer_id}/block`).then((r) => r.data),

  getPeerPhotos: (peer_id: string) =>
    api.get<ApiEnvelope & { name: string; photos: Array<{ url: string }> }>(`/users/${peer_id}/photos`).then((r) => r.data),

  registerPushToken: (token: string, platform: string) =>
    api.post<ApiEnvelope>('/users/me/push-token', { token, platform }).then((r) => r.data),

  unregisterPushToken: () =>
    api.delete<ApiEnvelope>('/users/me/push-token').then((r) => r.data),
};
