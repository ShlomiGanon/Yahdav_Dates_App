import { useParams } from 'react-router-dom';
import { PageShell } from '../components/PageShell';

export function ChatPage()
{
    const { peer_id } = useParams<{ peer_id: string }>();

    return (
        <PageShell title="שיחה">
            <p className="text-secondary opacity-60">
                השיחה עם {peer_id} תוצג כאן.
            </p>
        </PageShell>
    );
}
