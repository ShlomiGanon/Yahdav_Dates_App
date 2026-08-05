import type { ReactNode } from 'react';

interface Props
{
    title:    string;
    children: ReactNode;
}

// The inner centered content column used by every authenticated page that
// isn't a custom full-bleed layout (Discover's grid, Chat's split view,
// PeerPhotos' viewer). The surrounding chrome — dark background, sidebar
// nav — comes from AppShell, which wraps this.
export function PageShell({ title, children }: Props)
{
    return (
        <div className="max-w-2xl mx-auto px-6 py-10 text-secondary font-he">
            <h1 className="text-2xl font-bold mb-6 text-white">
                {title}
            </h1>
            <div className="bg-surface rounded-card p-8 shadow-lg">
                {children}
            </div>
        </div>
    );
}
