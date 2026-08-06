export const he =
{
    missing_all_fields:     'יש למלא את כל השדות',
    passwords_dont_match:   'הסיסמאות אינן תואמות',
    password_too_short:     'הסיסמה חייבת להכיל לפחות 8 תווים',
    name_required:          'שם מלא הוא שדה חובה',
    gender_required:        'יש לבחור מין',
    date_of_birth_required: 'יש למלא תאריך לידה',
    city_required:          'עיר היא שדה חובה',
    invalid_date:           'תאריך לידה לא תקין',
    age_too_young:          'גיל מינימלי הוא 18',
    age_too_old:            'גיל מקסימלי הוא 100',
    network_error:          'שגיאת רשת, נסה שוב',

    // Chat (finding 2.11) — previously raw inline string literals
    // duplicated identically in mobile/src/hooks/useConversations.ts,
    // hooks/useMessages.ts, and web/src/components/ChatMasterDetail.tsx.
    load_conversations_failed:    'טעינת השיחות נכשלה. אנא נסה/י שוב מאוחר יותר.',
    load_messages_failed:         'טעינת השיחה נכשלה. אנא נסה/י שוב.',
    load_older_messages_failed:   'שגיאה בטעינת הודעות ישנות',
    send_message_failed:          'שליחת ההודעה נכשלה. נסה/י שנית.',

    // Discover (finding 2.12) — previously a raw inline string literal
    // duplicated identically in mobile/src/hooks/useCandidates.ts and
    // web/src/pages/DiscoverPage.tsx.
    load_candidates_failed:       'טעינת האנשים נכשלה. אנא נסה/י שוב מאוחר יותר.',

    // Additional-photos CRUD (finding 2.13) — previously raw inline string
    // literals duplicated identically in mobile/src/hooks/useMyPhotos.ts
    // and web/src/pages/AdditionalPhotosPage.tsx. Note: 'שגיאה בהעלאת
    // התמונה' also appears verbatim in useMyProfile.ts/ProfilePage.tsx's
    // main-photo upload (out of this finding's scope — see Section 7);
    // reusing upload_photo_failed there later is a natural follow-up.
    load_photos_failed:           'שגיאה בטעינת התמונות',
    upload_photo_failed:          'שגיאה בהעלאת התמונה',
    delete_photo_failed:          'שגיאה במחיקת התמונה',

    // Block-user flow (finding 2.14) — previously a raw inline string
    // literal duplicated identically in mobile/src/hooks/usePeerProfile.ts
    // and web/src/pages/PeerProfilePage.tsx.
    block_user_failed:            'החסימה נכשלה. נסה/י שנית.',

    // Section 7 broad sweep — client-facing string literals duplicated
    // identically across mobile and web, found by an exhaustive grep for
    // Hebrew-containing quoted literals in both apps' src trees (both
    // single- and double-quoted). Raw JSX text content (unquoted children)
    // was explicitly left out of this pass. See APP/review.md Section 7.
    unknown_user_label:           'משתמש/ת',
    load_peer_profile_failed:     'משהו השתבש בטעינת הפרופיל',
    load_peer_photos_failed:      'משהו השתבש בטעינת התמונות',
    peer_profile_not_found:       'הפרופיל לא נמצא.',
    photo_limit_reached:          'הגעת למקסימום תמונות',
    load_my_profile_failed:       'שגיאה בטעינת הפרופיל',
    confirm_delete_photo_message: 'האם למחוק את התמונה?',
    // Mobile-only — no web equivalent, since the gallery-permission
    // concept doesn't exist on web. Centralized anyway to remove the
    // internal duplicate between useMyPhotos.ts and useMyProfile.ts.
    gallery_permission_required:  'נדרשת הרשאה לגישה לגלריה',
    gender_label:                 'מין',
    age_label:                    'גיל',
    location_label:               'מיקום',
    about_me_label:               'קצת עליי',
    more_details_label:           'פרטים נוספים',
    profile_incomplete_message:   'המשתמש/ת עדיין לא השלים/ה את הפרופיל.',
    additional_photos_label:      'תמונות נוספות',
    password_min_length_hint:     'לפחות 8 תווים',
    // The signup form's own submit button — distinct from
    // signup_entry_label below (different word, different purpose).
    signup_submit_label:          'הירשם',
    login_label:                  'התחברות',
    // The welcome screen's nav-to-signup button — distinct from
    // signup_submit_label above.
    signup_entry_label:           'הרשמה',
    save_changes_label:           'שמור שינויים',
    back_label:                   'חזרה',
    close_label:                  'סגירה',

    // Section 7 addendum (follow-up pass) — a real duplicate found in the
    // original sweep but dropped before the approved key table; added here
    // once explicitly approved. See APP/review.md Section 7's addendum note.
    add_photo_label:              'הוסף תמונה',
};
