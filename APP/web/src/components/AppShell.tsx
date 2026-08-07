import type { ReactNode } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { PAGE_ROUTES } from '../pages/routes';
import { useAuth } from '../auth/AuthContext';
import { WEB_DESTINATIONS } from '../auth/destinations';
import { APP_NAME } from '@shared/config';

interface Props
{
    children: ReactNode;
}

const NAV_ITEMS: Array<{ to: string; label: string }> =
[
    { to: PAGE_ROUTES.menu,        label: 'דף הבית'        },
    { to: PAGE_ROUTES.discover,    label: 'גילוי חברים'    },
    { to: PAGE_ROUTES.chatHistory, label: 'הודעות'         },
    { to: PAGE_ROUTES.profile,     label: 'הפרופיל שלי'    },
];

function navLinkClass({ isActive }: { isActive: boolean }): string
{
    return isActive
        ? 'block rounded-card px-4 py-3 text-white bg-white/15 font-semibold'
        : 'block rounded-card px-4 py-3 text-white/70 hover:bg-white/10 hover:text-white transition-colors';
}

// The persistent desktop nav shell for every authenticated page — a
// left-hand (visually right, since the document is `dir="rtl"`) rail with
// the primary destinations always in view, plus a scrollable content pane.
// Mobile has no equivalent: it relies on MenuScreen as a standalone hub and
// per-screen back buttons, which reads as an app-shell-less stack on a
// phone but would feel wrong copied verbatim onto a wide desktop viewport.
export function AppShell({ children }: Props)
{
    const { logout } = useAuth();
    const navigate    = useNavigate();

    async function handleLogout(): Promise<void>
    {
        await logout();
        navigate(WEB_DESTINATIONS.login, { replace: true });
    }

    return (
        <div className="min-h-screen bg-background flex">
            <aside className="w-64 shrink-0 flex flex-col gap-1 p-6 border-e border-black/20">
                <h1 className="text-white text-xl font-bold mb-6 px-2">{APP_NAME}</h1>

                <nav className="flex flex-col gap-1">
                    {NAV_ITEMS.map((item) => (
                        <NavLink key={item.to} to={item.to} className={navLinkClass}>
                            {item.label}
                        </NavLink>
                    ))}
                </nav>

                <button
                    type="button"
                    onClick={handleLogout}
                    className="mt-auto px-4 py-3 text-sm text-white/60 hover:text-white text-right"
                >
                    התנתק מהמערכת
                </button>
            </aside>

            <main className="flex-1 min-w-0 overflow-y-auto">
                {children}
            </main>
        </div>
    );
}
