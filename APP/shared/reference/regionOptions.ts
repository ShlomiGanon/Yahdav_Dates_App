// The seven region options offered on the profile-edit picker — was
// duplicated as a {label,value}[] array on mobile (ProfileScreen.tsx) and a
// flat string[] on web (ProfilePage.tsx). Label and value are always the
// same string for a region, so both platforms render identically from this
// single {value,label}[] shape. See APP/review.md finding 2.7.
export const REGION_OPTIONS: Array<{ value: string; label: string }> =
[
    { value: 'מחוז הצפון',    label: 'מחוז הצפון'    },
    { value: 'מחוז חיפה',     label: 'מחוז חיפה'     },
    { value: 'מחוז המרכז',    label: 'מחוז המרכז'    },
    { value: 'מחוז תל אביב',  label: 'מחוז תל אביב'  },
    { value: 'מחוז ירושלים',  label: 'מחוז ירושלים'  },
    { value: 'מחוז הדרום',    label: 'מחוז הדרום'    },
    { value: 'יהודה ושומרון', label: 'יהודה ושומרון' },
];
