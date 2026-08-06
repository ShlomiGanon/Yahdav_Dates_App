import type { Gender } from '../types/user';

// The three gender options offered on the signup/profile-edit pickers — was
// duplicated as separate literal arrays in mobile's ProfileScreen.tsx and
// web's ProfilePage.tsx. See APP/review.md finding 2.7.
export const GENDER_OPTIONS: Array<{ value: Gender; label: string }> =
[
    { value: 'male',   label: 'זכר'  },
    { value: 'female', label: 'נקבה' },
    { value: 'other',  label: 'אחר'  },
];
