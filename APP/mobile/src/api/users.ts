import { createUsersApi } from '@shared/api/users';
import { api } from './axios';
import type { Profile as MobileProfile } from '../types/user';
import type { Profile as SharedProfile } from '@shared/types/user';

const shared = createUsersApi(api);

// Delegates to shared/api/users.ts for every endpoint. Three methods keep a
// thin bridge here because mobile's local types are looser than shared's —
// see APP/review.md finding 2.2 for the full rationale.
export const usersApi =
{
    ...shared,

    // Mobile's local method predates shared's `deleteMyPhoto` naming — kept
    // as an alias so callers don't need to change.
    deletePhoto: shared.deleteMyPhoto,

    // Mobile's gender state (ModalPicker) is plain `string | null`, not
    // branded as shared's `Gender` union — the cast is safe because
    // GENDER_OPTIONS' values are already 'male'/'female'/'other'.
    updateMyProfile: (data: Partial<MobileProfile>) =>
        shared.updateMyProfile(data as Partial<SharedProfile>),

    // Platform.OS's RN type is wider than shared's 'ios' | 'android'.
    registerPushToken: (token: string, platform: string) =>
        shared.registerPushToken(token, platform as 'ios' | 'android'),
};
