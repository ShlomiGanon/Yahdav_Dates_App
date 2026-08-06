import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { PageShell } from '../components/PageShell';
import { PhotoUpload } from '../components/PhotoUpload';
import { RemoteImage } from '../components/RemoteImage';
import { ConfirmBanner } from '../components/ConfirmBanner';
import { usersApi } from '../api/client';
import { PAGE_ROUTES } from './routes';
import { MAX_ADDITIONAL_PHOTOS } from '@shared/config';
import { clientMessage } from '@shared/copy/client';
import type { Photo } from '@shared/types/user';

export function AdditionalPhotosPage()
{
    const navigate = useNavigate();

    const [photos,    setPhotos]    = useState<Photo[]>([]);
    const [loading,   setLoading]   = useState(true);
    const [uploading, setUploading] = useState(false);
    const [status,    setStatus]    = useState<{ message: string; ok: boolean } | null>(null);
    const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

    useEffect(() =>
    {
        (async () =>
        {
            try
            {
                const data = await usersApi.getMyPhotos();
                if (data.success)
                {
                    setPhotos(data.photos);
                }
                else
                {
                    setStatus({ message: data.message, ok: false });
                }
            }
            catch
            {
                setStatus({ message: clientMessage('load_photos_failed'), ok: false });
            }
            finally
            {
                setLoading(false);
            }
        })();
    }, []);

    async function handleFile(file: File): Promise<void>
    {
        setUploading(true);
        setStatus(null);
        try
        {
            const form = new FormData();
            form.append('photo', file);
            const data = await usersApi.uploadPhoto(form);
            setStatus({ message: data.message, ok: data.success });
            if (data.success)
            {
                setPhotos((prev) => [...prev, data]);
            }
        }
        catch
        {
            setStatus({ message: clientMessage('upload_photo_failed'), ok: false });
        }
        finally
        {
            setUploading(false);
        }
    }

    async function confirmRemove(): Promise<void>
    {
        const photoId = pendingDeleteId;
        setPendingDeleteId(null);
        if (!photoId)
        {
            return;
        }

        try
        {
            const data = await usersApi.deleteMyPhoto(photoId);
            setStatus({ message: data.message, ok: data.success });
            if (data.success)
            {
                setPhotos((prev) => prev.filter((p) => p.photo_id !== photoId));
            }
        }
        catch
        {
            setStatus({ message: clientMessage('delete_photo_failed'), ok: false });
        }
    }

    const atLimit = photos.length >= MAX_ADDITIONAL_PHOTOS;

    return (
        <AppShell>
            <PageShell title={clientMessage('additional_photos_label')}>
                {loading ? (
                    <p className="text-secondary opacity-60">טוען...</p>
                ) : (
                    <>
                        {status && (
                            <p
                                className={`text-sm mb-4 ${status.ok ? 'text-success' : 'text-danger'}`}
                                role="alert"
                            >
                                {status.message}
                            </p>
                        )}

                        {pendingDeleteId && (
                            <ConfirmBanner
                                message={clientMessage('confirm_delete_photo_message')}
                                confirmLabel="מחק תמונה"
                                onConfirm={confirmRemove}
                                onCancel={() => setPendingDeleteId(null)}
                            />
                        )}

                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-6">
                            {photos.map((photo) => (
                                <div key={photo.photo_id} className="relative aspect-square">
                                    <RemoteImage
                                        src={photo.url}
                                        className="w-full h-full object-cover rounded-card"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setPendingDeleteId(photo.photo_id)}
                                        aria-label="מחק תמונה"
                                        className="absolute top-1 left-1 w-7 h-7 rounded-full bg-black/60
                                                   text-white text-sm leading-none flex items-center
                                                   justify-center hover:bg-danger transition-colors"
                                    >
                                        ✕
                                    </button>
                                </div>
                            ))}

                            {photos.length === 0 && (
                                <p className="col-span-full text-secondary opacity-60 text-center py-6">
                                    עדיין לא הוספתם תמונות.
                                </p>
                            )}
                        </div>

                        <div className="flex flex-col items-center gap-3">
                            <PhotoUpload
                                onFile={handleFile}
                                disabled={uploading || atLimit}
                                label={atLimit ? clientMessage('photo_limit_reached') : clientMessage('add_photo_label')}
                            />
                            <button
                                type="button"
                                onClick={() => navigate(PAGE_ROUTES.profile)}
                                className="text-sm text-secondary underline"
                            >
                                חזור לפרופיל שלי
                            </button>
                        </div>
                    </>
                )}
            </PageShell>
        </AppShell>
    );
}
