import { v4 as uuidv4 } from 'uuid';
import { profileQueries, ProfileRow, PhotoRow } from '../database/queries/profile.queries';

export interface MyProfile {
  user_id: string;
  name: string;
  bio: string;
  gender: string | null;
  date_of_birth: string | null;
  city: string;
  region: string;
  photo_url: string | null;
}

export interface PeerProfile {
  user_id: string;
  name: string;
  gender: string | null;
  date_of_birth: string | null;
  city: string;
  region: string;
  bio: string;
  photo_url: string | null;
  has_extra_photos: boolean;
}

export interface Candidate {
  user_id: string;
  name: string;
  gender: string | null;
  date_of_birth: string | null;
  city: string;
  photo_url: string | null;
}

export interface DiscoverResult {
  candidates: Candidate[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

export interface Photo {
  photo_id: string;
  url: string;
}

function toMyProfile(row: ProfileRow): MyProfile {
  return {
    user_id:       row.user_id,
    name:          row.name,
    bio:           row.bio,
    gender:        row.gender,
    date_of_birth: row.date_of_birth,
    city:          row.city,
    region:        row.region,
    photo_url:     row.photo_url,
  };
}

function toCandidate(row: ProfileRow): Candidate {
  return {
    user_id:       row.user_id,
    name:          row.name,
    gender:        row.gender,
    date_of_birth: row.date_of_birth,
    city:          row.city,
    photo_url:     row.photo_url,
  };
}

function toPhoto(row: PhotoRow): Photo {
  return { photo_id: row.photo_id, url: row.url };
}

export const ProfileModel = {
  getMyProfile(userId: string): MyProfile | null {
    const row = profileQueries.findById(userId);
    return row ? toMyProfile(row) : null;
  },

  updateMyProfile(
    userId: string,
    fields: Partial<Pick<ProfileRow, 'name' | 'bio' | 'city' | 'region' | 'gender' | 'date_of_birth'>>,
  ): MyProfile | null {
    profileQueries.update(userId, fields, new Date().toISOString());
    return ProfileModel.getMyProfile(userId);
  },

  discover(callerId: string, page: number, limit: number): DiscoverResult {
    const offset = (page - 1) * limit;
    const rows  = profileQueries.findCandidates(callerId, limit, offset);
    const total = profileQueries.countCandidates(callerId);
    return {
      candidates:  rows.map(toCandidate),
      total,
      page,
      limit,
      total_pages: Math.ceil(total / limit),
    };
  },

  // Returns null if user doesn't exist, is inactive, or the block relationship exists
  getPeerProfile(peerId: string, callerId: string): PeerProfile | null {
    const row = profileQueries.findById(peerId);
    if (!row || row.status !== 'active') return null;

    // Check mutual block
    const { getDb } = require('../database/connection');
    const blocked = getDb()
      .prepare(`
        SELECT 1 FROM user_blocks
        WHERE (blocker_id = ? AND blocked_id = ?)
           OR (blocker_id = ? AND blocked_id = ?)
        LIMIT 1
      `)
      .get(callerId, peerId, peerId, callerId);
    if (blocked) return null;

    const extraPhotos = profileQueries.countPhotos(peerId);
    return {
      user_id:         row.user_id,
      name:            row.name,
      gender:          row.gender,
      date_of_birth:   row.date_of_birth,
      city:            row.city,
      region:          row.region,
      bio:             row.bio,
      photo_url:       row.photo_url,
      has_extra_photos: extraPhotos > 0,
    };
  },

  blockUser(blockerId: string, blockedId: string): void {
    profileQueries.addBlock(blockerId, blockedId, new Date().toISOString());
  },

  // Main photo
  setMainPhoto(userId: string, url: string): string {
    profileQueries.updatePhotoUrl(userId, url, new Date().toISOString());
    return url;
  },

  removeMainPhoto(userId: string): void {
    profileQueries.updatePhotoUrl(userId, null, new Date().toISOString());
  },

  // Additional photos
  getMyPhotos(userId: string): Photo[] {
    return profileQueries.getPhotos(userId).map(toPhoto);
  },

  getPeerPhotos(userId: string): Photo[] {
    return profileQueries.getPhotos(userId).map(toPhoto);
  },

  addPhoto(userId: string, url: string): Photo {
    const photoId = uuidv4();
    profileQueries.addPhoto({ photo_id: photoId, user_id: userId, url, created_at: new Date().toISOString() });
    return { photo_id: photoId, url };
  },

  deletePhoto(userId: string, photoId: string): { url: string } | null {
    const row = profileQueries.findPhoto(photoId);
    if (!row || row.user_id !== userId) return null;
    profileQueries.deletePhoto(photoId);
    return { url: row.url };
  },

  countPhotos(userId: string): number {
    return profileQueries.countPhotos(userId);
  },

  // Push token
  registerPushToken(userId: string, token: string): void {
    profileQueries.updatePushToken(userId, token, new Date().toISOString());
  },

  unregisterPushToken(userId: string): void {
    profileQueries.updatePushToken(userId, null, new Date().toISOString());
  },
};
