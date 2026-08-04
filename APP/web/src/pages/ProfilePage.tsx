import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AUTH_FLOW_EVENTS } from '@shared/flow/authFlow';
import { validateDateOfBirth } from '@shared/validation/profile';
import { clientMessage } from '@shared/copy/client';
import { PageShell } from '../components/PageShell';
import { PhotoUpload } from '../components/PhotoUpload';
import { Button } from '../components/Button';
import { usersApi } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { WEB_DESTINATIONS } from '../auth/destinations';
import type { Gender } from '@shared/types/user';

const GENDER_OPTIONS: Array<{ value: Gender; label: string }> = [
    { value: 'male',   label: 'זכר'  },
    { value: 'female', label: 'נקבה' },
    { value: 'other',  label: 'אחר'  },
];

const REGION_OPTIONS = [
    'מחוז הצפון',
    'מחוז חיפה',
    'מחוז המרכז',
    'מחוז תל אביב',
    'מחוז ירושלים',
    'מחוז הדרום',
    'יהודה ושומרון',
];

const inputClass =
    'border border-gray-300 rounded-lg px-4 py-3 text-base text-right ' +
    'focus:outline-none focus:border-primary bg-white';

export function ProfilePage()
{
    const navigate = useNavigate();
    const { logout } = useAuth();

    const [loading,  setLoading]  = useState(true);
    const [saving,   setSaving]   = useState(false);
    const [uploading, setUploading] = useState(false);
    const [loadError, setLoadError] = useState('');
    const [status,   setStatus]   = useState<{ message: string; ok: boolean } | null>(null);

    const [photoUrl,      setPhotoUrl]      = useState<string | null>(null);
    const [name,          setName]          = useState('');
    const [bio,           setBio]           = useState('');
    const [gender,        setGender]        = useState<Gender | ''>('');
    const [dateOfBirth,   setDateOfBirth]   = useState('');
    const [city,          setCity]          = useState('');
    const [region,        setRegion]        = useState('');
    const [validationError, setValidationError] = useState('');

    useEffect(() =>
    {
        (async () =>
        {
            try
            {
                const data = await usersApi.getMyProfile();
                if (!data.success)
                {
                    setLoadError(data.message);
                    return;
                }
                setPhotoUrl(data.photo_url);
                setName(data.name ?? '');
                setBio(data.bio ?? '');
                setGender((data.gender as Gender) ?? '');
                setDateOfBirth(data.date_of_birth ?? '');
                setCity(data.city ?? '');
                setRegion(data.region ?? '');
            }
            catch
            {
                setLoadError('שגיאה בטעינת הפרופיל');
            }
            finally
            {
                setLoading(false);
            }
        })();
    }, []);

    async function handlePhotoFile(file: File): Promise<void>
    {
        setUploading(true);
        setStatus(null);
        try
        {
            const form = new FormData();
            form.append('photo', file);
            const data = await usersApi.uploadMainPhoto(form);
            setStatus({ message: data.message, ok: data.success });
            if (data.success)
            {
                setPhotoUrl(data.photo_url);
            }
        }
        catch
        {
            setStatus({ message: 'שגיאה בהעלאת התמונה', ok: false });
        }
        finally
        {
            setUploading(false);
        }
    }

    async function handleSave(e: React.FormEvent): Promise<void>
    {
        e.preventDefault();
        setValidationError('');
        setStatus(null);

        if (!name.trim())
        {
            setValidationError(clientMessage('name_required'));
            return;
        }
        if (!gender)
        {
            setValidationError(clientMessage('gender_required'));
            return;
        }
        if (!dateOfBirth)
        {
            setValidationError(clientMessage('date_of_birth_required'));
            return;
        }
        if (!city.trim())
        {
            setValidationError(clientMessage('city_required'));
            return;
        }

        const dateError = validateDateOfBirth(dateOfBirth);
        if (dateError === 'invalid_date')
        {
            setValidationError(clientMessage('invalid_date'));
            return;
        }
        if (dateError === 'age_too_young')
        {
            setValidationError(clientMessage('age_too_young'));
            return;
        }
        if (dateError === 'age_too_old')
        {
            setValidationError(clientMessage('age_too_old'));
            return;
        }

        setSaving(true);
        try
        {
            const data = await usersApi.updateMyProfile({
                name: name.trim(),
                bio: bio.trim(),
                gender,
                date_of_birth: dateOfBirth,
                city: city.trim(),
                region,
            });
            setStatus({ message: data.message, ok: data.success });
        }
        catch
        {
            setStatus({ message: clientMessage('network_error'), ok: false });
        }
        finally
        {
            setSaving(false);
        }
    }

    async function handleLogout(): Promise<void>
    {
        await logout();
        navigate(WEB_DESTINATIONS[AUTH_FLOW_EVENTS.afterLogout], { replace: true });
    }

    if (loading)
    {
        return (
            <PageShell title="הפרופיל שלי">
                <p className="text-secondary opacity-60">טוען...</p>
            </PageShell>
        );
    }

    return (
        <PageShell title="הפרופיל שלי">
            {loadError && (
                <p className="text-danger text-sm mb-4" role="alert">{loadError}</p>
            )}

            <div className="flex flex-col items-center gap-3 mb-6">
                {photoUrl ? (
                    <img
                        src={photoUrl}
                        alt=""
                        className="w-28 h-28 rounded-full object-cover border border-gray-200"
                    />
                ) : (
                    <div className="w-28 h-28 rounded-full bg-surface border-2 border-dashed border-gray-300" />
                )}
                <PhotoUpload onFile={handlePhotoFile} label="החלף תמונה" disabled={uploading} />
            </div>

            <form onSubmit={handleSave} className="flex flex-col gap-4" noValidate>
                <div className="flex flex-col gap-1">
                    <label htmlFor="profile-name" className="text-sm text-secondary">שם מלא</label>
                    <input
                        id="profile-name"
                        type="text"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        maxLength={80}
                        className={inputClass}
                    />
                </div>

                <div className="flex flex-col gap-1">
                    <label htmlFor="profile-gender" className="text-sm text-secondary">מין</label>
                    <select
                        id="profile-gender"
                        value={gender}
                        onChange={(e) => setGender(e.target.value as Gender)}
                        className={inputClass}
                    >
                        <option value="">בחר מין</option>
                        {GENDER_OPTIONS.map((o) => (
                            <option key={o.value} value={o.value}>{o.label}</option>
                        ))}
                    </select>
                </div>

                <div className="flex flex-col gap-1">
                    <label htmlFor="profile-dob" className="text-sm text-secondary">תאריך לידה</label>
                    <input
                        id="profile-dob"
                        type="date"
                        value={dateOfBirth}
                        onChange={(e) => setDateOfBirth(e.target.value)}
                        className={inputClass}
                    />
                </div>

                <div className="flex flex-col gap-1">
                    <label htmlFor="profile-city" className="text-sm text-secondary">עיר</label>
                    <input
                        id="profile-city"
                        type="text"
                        value={city}
                        onChange={(e) => setCity(e.target.value)}
                        maxLength={80}
                        className={inputClass}
                    />
                </div>

                <div className="flex flex-col gap-1">
                    <label htmlFor="profile-region" className="text-sm text-secondary">אזור</label>
                    <select
                        id="profile-region"
                        value={region}
                        onChange={(e) => setRegion(e.target.value)}
                        className={inputClass}
                    >
                        <option value="">בחר אזור</option>
                        {REGION_OPTIONS.map((r) => (
                            <option key={r} value={r}>{r}</option>
                        ))}
                    </select>
                </div>

                <div className="flex flex-col gap-1">
                    <label htmlFor="profile-bio" className="text-sm text-secondary">קצת עליי</label>
                    <textarea
                        id="profile-bio"
                        value={bio}
                        onChange={(e) => setBio(e.target.value.slice(0, 500))}
                        maxLength={500}
                        rows={4}
                        className={inputClass}
                    />
                </div>

                {validationError && (
                    <p className="text-danger text-sm text-center" role="alert">{validationError}</p>
                )}
                {status && (
                    <p className={`text-sm text-center ${status.ok ? 'text-success' : 'text-danger'}`} role="alert">
                        {status.message}
                    </p>
                )}

                <Button type="submit" label="שמור שינויים" loading={saving} />
            </form>

            <button
                type="button"
                onClick={handleLogout}
                className="mt-6 text-sm text-secondary underline block mx-auto"
            >
                התנתק מהמערכת
            </button>
        </PageShell>
    );
}
