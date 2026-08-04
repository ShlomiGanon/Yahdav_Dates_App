import type { ReactNode } from 'react';

interface Props
{
    title:    string;
    children: ReactNode;
}

export function PageShell({ title, children }: Props)
{
    return (
        <div className="min-h-screen bg-background text-secondary font-he">
            <div className="max-w-2xl mx-auto px-4 py-8">
                <h1 className="text-2xl font-bold mb-6 text-secondary">
                    {title}
                </h1>
                {children}
            </div>
        </div>
    );
}
