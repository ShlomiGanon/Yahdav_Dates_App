import { useNavigate } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { PageShell } from '../components/PageShell';
import { PAGE_ROUTES } from './routes';

interface QuickLink
{
    to:          string;
    title:       string;
    description: string;
}

const QUICK_LINKS: QuickLink[] =
[
    {
        to:          PAGE_ROUTES.discover,
        title:       'גילוי חברים',
        description: 'עיינו בפרופילים של אנשים חדשים והתחילו להכיר.',
    },
    {
        to:          PAGE_ROUTES.chatHistory,
        title:       'הודעות',
        description: 'המשיכו שיחות קיימות או קראו הודעות שהתקבלו.',
    },
    {
        to:          PAGE_ROUTES.profile,
        title:       'הפרופיל שלי',
        description: 'עדכנו את הפרטים, התמונה והביוגרפיה שלכם.',
    },
];

// Menu no longer has to double as the app's only navigation — AppShell's
// sidebar covers that now — so this is a lightweight dashboard/landing
// pane instead of mobile's plain button hub.
export function MenuPage()
{
    const navigate = useNavigate();

    return (
        <AppShell>
            <PageShell title="תפריט ראשי">
                <div className="grid gap-4 sm:grid-cols-2">
                    {QUICK_LINKS.map((link) => (
                        <button
                            key={link.to}
                            type="button"
                            onClick={() => navigate(link.to)}
                            className="text-right border border-gray-200 rounded-card p-5 hover:border-primary
                                       hover:shadow-md transition-all"
                        >
                            <h2 className="text-lg font-semibold text-secondary mb-1">{link.title}</h2>
                            <p className="text-sm text-secondary opacity-70">{link.description}</p>
                        </button>
                    ))}
                </div>
            </PageShell>
        </AppShell>
    );
}
