import { useParams } from 'react-router-dom';
import { PageShell } from '../components/PageShell';

export function PeerPhotosPage()
{
    const { peer_id } = useParams<{ peer_id: string }>();

    return (
        <PageShell title="תמונות">
            <p className="text-secondary opacity-60">
                התמונות של המשתמש {peer_id} יוצגו כאן.
            </p>
        </PageShell>
    );
}
