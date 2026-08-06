import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { RemoteImage } from '../components/RemoteImage';
import { usersApi } from '../api/client';
import { PAGE_ROUTES } from './routes';
import { clientMessage } from '@shared/copy/client';

// Deliberately outside AppShell — mobile's version is a full-bleed,
// distraction-free photo viewer, and the sidebar nav would only get in the
// way of that here too. "חזרה" is the only way out, same as mobile.
export function PeerPhotosPage()
{
    const { peer_id } = useParams<{ peer_id: string }>();
    const navigate     = useNavigate();

    const [photos,    setPhotos]    = useState<Array<{ url: string }>>([]);
    const [peerName,  setPeerName]  = useState('');
    const [loading,   setLoading]   = useState(true);
    const [loadError, setLoadError] = useState('');
    const [current,   setCurrent]   = useState(0);

    useEffect(() =>
    {
        if (!peer_id) return;

        (async () =>
        {
            try
            {
                const data = await usersApi.getPeerPhotos(peer_id);
                if (!data.success)
                {
                    setLoadError(data.message);
                    return;
                }
                setPeerName(data.name ?? '');
                setPhotos(data.photos ?? []);
            }
            catch
            {
                setLoadError(clientMessage('load_peer_photos_failed'));
            }
            finally
            {
                setLoading(false);
            }
        })();
    }, [peer_id]);

    function backToProfile(): void
    {
        navigate(PAGE_ROUTES.peerProfile.replace(':peer_id', peer_id ?? ''));
    }

    const heading = peerName ? `התמונות של ${peerName}` : clientMessage('additional_photos_label');

    if (loading)
    {
        return (
            <div className="min-h-screen bg-black flex items-center justify-center">
                <p className="text-white/70">טוען...</p>
            </div>
        );
    }

    if (loadError || photos.length === 0)
    {
        return (
            <div className="min-h-screen bg-black flex flex-col items-center justify-center gap-4 px-4">
                <p className="text-white/70">{loadError || 'אין תמונות להצגה.'}</p>
                <button type="button" onClick={backToProfile} className="text-white underline">
                    חזרה
                </button>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-black flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 bg-black/60">
                <button type="button" onClick={backToProfile} className="text-white underline text-sm">
                    חזרה
                </button>
                <div className="text-center">
                    <p className="text-white font-semibold">{heading}</p>
                    <p className="text-white/60 text-xs">{current + 1} / {photos.length}</p>
                </div>
                <span className="w-12" />
            </div>

            <div className="flex-1 flex items-center justify-center relative px-4">
                {photos.length > 1 && (
                    <button
                        type="button"
                        aria-label="הקודם"
                        onClick={() => setCurrent((c) => (c - 1 + photos.length) % photos.length)}
                        className="absolute right-4 text-white/70 hover:text-white text-3xl px-3 py-2"
                    >
                        ›
                    </button>
                )}

                <RemoteImage
                    src={photos[current]?.url}
                    className="max-h-[80vh] max-w-full object-contain"
                />

                {photos.length > 1 && (
                    <button
                        type="button"
                        aria-label="הבא"
                        onClick={() => setCurrent((c) => (c + 1) % photos.length)}
                        className="absolute left-4 text-white/70 hover:text-white text-3xl px-3 py-2"
                    >
                        ‹
                    </button>
                )}
            </div>
        </div>
    );
}
