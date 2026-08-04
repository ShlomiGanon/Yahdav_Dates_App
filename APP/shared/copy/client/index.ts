import { he } from './locales/he';

export type ClientMessageKey = keyof typeof he;

const LOCALES =
{
    he,
};

const ACTIVE_LOCALE: keyof typeof LOCALES = 'he';

export function clientMessage(key: ClientMessageKey): string
{
    return LOCALES[ACTIVE_LOCALE][key] ?? key;
}
