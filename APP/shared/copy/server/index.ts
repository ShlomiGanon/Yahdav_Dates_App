import { he } from './locales/he';

export type ServerMessageKey = keyof typeof he;

const LOCALES =
{
    he,
};

const ACTIVE_LOCALE: keyof typeof LOCALES = 'he';

const FALLBACK_MESSAGE = 'אירעה שגיאה, נסה שוב מאוחר יותר';

export function serverMessage(key: string): string
{
    return (LOCALES[ACTIVE_LOCALE] as Record<string, string>)[key] ?? FALLBACK_MESSAGE;
}
