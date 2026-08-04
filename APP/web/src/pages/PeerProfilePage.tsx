import { useParams } from 'react-router-dom';
import { PageShell } from '../components/PageShell';

export function PeerProfilePage()
{
    const { peer_id } = useParams<{ peer_id: string }>();

    return (
        <PageShell title="פרופיל">
            <p className="text-secondary opacity-60">
                פרופיל המשתמש {peer_id} יוצג כאן.
            </p>
        </PageShell>
    );
}
