import * as fs from 'fs';
import * as path from 'path';
import { colors } from '../../../shared/theme/colors';

// Mobile imports `colors` directly, so it can never drift. Web's colors
// live in a Tailwind @theme CSS block (index.css) — CSS can't import a
// TypeScript module, so this test parses the real file and asserts every
// web-relevant color still matches the shared source of truth byte-for-byte.
// Colors mobile-only (textMain, online, offline) aren't in web's CSS at
// all, so they're intentionally excluded from this map.
const WEB_CSS_KEYS: Partial<Record<keyof typeof colors, string>> =
{
    primary:    'primary',
    secondary:  'secondary',
    background: 'background',
    surface:    'surface',
    danger:     'danger',
    success:    'success',
    selfBubble: 'self-bubble',
    peerBubble: 'peer-bubble',
};

describe('web index.css color drift', () =>
{
    const cssPath = path.resolve(__dirname, '../../../web/src/index.css');
    const cssContent = fs.readFileSync(cssPath, 'utf-8');

    function extractCssColor(cssKey: string): string | null
    {
        const match = cssContent.match(new RegExp(`--color-${cssKey}:\\s*(#[0-9A-Fa-f]{6})`));
        return match ? match[1].toUpperCase() : null;
    }

    for (const [sharedKey, cssKey] of Object.entries(WEB_CSS_KEYS) as Array<[keyof typeof colors, string]>)
    {
        it(`--color-${cssKey} in index.css matches shared colors.${String(sharedKey)}`, () =>
        {
            const cssValue = extractCssColor(cssKey);

            expect(cssValue).not.toBeNull();
            expect(cssValue).toBe(colors[sharedKey].toUpperCase());
        });
    }
});
