import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { PageShell } from '../components/PageShell';
import { RemoteImage } from '../components/RemoteImage';
import { ConfirmBanner } from '../components/ConfirmBanner';
import { usersApi } from '../api/client';
import { PAGE_ROUTES } from './routes';
import type { PeerProfile } from '@shared/types/user';

function genderLabel(g: string | null): string | null
{
    if (g === 'male')   return 'זכר';
    if (g === 'female') return 'נקבה';
    if (g === 'other')  return 'אחר';
    return null;
}

function calcAge(dob: string | null): number | null
{
    if (!dob) return null;
    const d = new Date(dob);
    if (isNaN(d.getTime()) || d.getFullYear() <= 1900) return null;
    return Math.floor((Date.now() - d.getTime()) / (365.25 * 24 * 3600 * 1000));
}

function FieldRow({ label, value }: { label: string; value: string })
{
    return (
        <div className="w-full border-b border-gray-100 py-2">
            <p className="text-xs text-secondary opacity-60">{label}</p>
            <p className="text-secondary">{value}</p>
        </div>
    );
}

export function PeerProfilePage()
{
    const { peer_id } = useParams<{ peer_id: string }>();
    const navigate     = useNavigate();

    const [profile,   setProfile]   = useState<PeerProfile | null>(null);
    const [loading,   setLoading]   = useState(true);
    const [blocking,  setBlocking]  = useState(false);
    const [loadError, setLoadError] = useState('');
    const [confirmingBlock, setConfirmingBlock] = useState(false);
    const [blockError,      setBlockError]      = useState('');

    useEffect(() =>
    {
        if (!peer_id) return;

        (async () =>
        {
            try
            {
                const data = await usersApi.getPeerProfile(peer_id);
                if (!data.success)
                {
                    setLoadError(data.message);
                    return;
                }
                setProfile(data);
            }
            catch
            {
                setLoadError('משהו השתבש בטעינת הפרופיל');
            }
            finally
            {
                setLoading(false);
            }
        })();
    }, [peer_id]);

    async function confirmBlock(): Promise<void>
    {
        setConfirmingBlock(false);
        if (!peer_id)
        {
            return;
        }

        setBlocking(true);
        try
        {
            const data = await usersApi.blockUser(peer_id);
            if (data.success)
            {
                navigate(PAGE_ROUTES.discover);
            }
            else
            {
                setBlockError(data.message);
            }
        }
        catch
        {
            setBlockError('החסימה נכשלה. נסה/י שנית.');
        }
        finally
        {
            setBlocking(false);
        }
    }

    if (loading)
    {
        return (
            <AppShell>
                <PageShell title="פרופיל">
                    <p className="text-secondary opacity-60">טוען...</p>
                </PageShell>
            </AppShell>
        );
    }

    if (loadError || !profile)
    {
        return (
            <AppShell>
                <PageShell title="פרופיל">
                    <p className="text-danger text-sm mb-4" role="alert">
                        {loadError || 'הפרופיל לא נמצא.'}
                    </p>
                    <button
                        type="button"
                        onClick={() => navigate(PAGE_ROUTES.discover)}
                        className="text-sm text-secondary underline"
                    >
                        חזור
                    </button>
                </PageShell>
            </AppShell>
        );
    }

    const age      = calcAge(profile.date_of_birth);
    const gender   = genderLabel(profile.gender);
    const location = [profile.city, profile.region].filter(Boolean).join(', ');

    return (
        <AppShell>
            <PageShell title={profile.name || 'משתמש/ת'}>
                <div className="flex justify-end mb-2">
                    <button
                        type="button"
                        onClick={() => setConfirmingBlock(true)}
                        disabled={blocking}
                        className="text-sm text-danger underline disabled:opacity-50"
                    >
                        חסימת משתמש
                    </button>
                </div>

                {confirmingBlock && (
                    <ConfirmBanner
                        message={`האם לחסום את ${profile.name || 'משתמש/ת'}?`}
                        confirmLabel="חסום משתמש"
                        onConfirm={confirmBlock}
                        onCancel={() => setConfirmingBlock(false)}
                    />
                )}

                {blockError && (
                    <p className="text-danger text-sm mb-4" role="alert">{blockError}</p>
                )}

                <div className="flex flex-col items-center gap-3 mb-6">
                    {profile.photo_url ? (
                        <RemoteImage
                            src={profile.photo_url}
                            className="w-28 h-28 rounded-full object-cover"
                        />
                    ) : (
                        <div className="w-28 h-28 rounded-full bg-background/10 flex items-center
                                        justify-center text-4xl">
                            👤
                        </div>
                    )}
                </div>

                <div className="flex flex-col">
                    {gender && <FieldRow label="מין" value={gender} />}
                    {age !== null && <FieldRow label="גיל" value={String(age)} />}
                    {location && <FieldRow label="מיקום" value={location} />}
                    {!!profile.bio && <FieldRow label="קצת עליי" value={profile.bio} />}
                    {!gender && age === null && !location && !profile.bio && (
                        <FieldRow label="פרטים נוספים" value="המשתמש/ת עדיין לא השלים/ה את הפרופיל." />
                    )}
                </div>

                <div className="flex flex-col gap-3 mt-6">
                    {profile.has_extra_photos && (
                        <button
                            type="button"
                            onClick={() => navigate(PAGE_ROUTES.peerPhotos.replace(':peer_id', peer_id ?? ''))}
                            className="w-full py-3 rounded-card bg-primary text-white font-semibold"
                        >
                            להצגת תמונות נוספות
                        </button>
                    )}
                    <button
                        type="button"
                        onClick={() => navigate(PAGE_ROUTES.chat.replace(':peer_id', peer_id ?? ''))}
                        className="w-full py-3 rounded-card border border-secondary text-secondary font-semibold"
                    >
                        התחל שיחה / שלח הודעה
                    </button>
                    <button
                        type="button"
                        onClick={() => navigate(PAGE_ROUTES.discover)}
                        className="w-full py-2 text-sm text-secondary underline"
                    >
                        חזור
                    </button>
                </div>
            </PageShell>
        </AppShell>
    );
}
