import React, { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { View, ActivityIndicator, StyleSheet, SafeAreaView } from 'react-native';
import { ScreenHeading } from './ScreenHeading';
import { HebrewInput } from './HebrewInput';
import { PrimaryButton } from './PrimaryButton';
import { loadServerUrl, saveServerUrl } from '../auth/serverUrlStorage';
import { normalizeServerUrl } from '../utils/normalizeServerUrl';
import { checkServerHealth } from '../utils/checkServerHealth';
import { setBaseURL } from '../api/axios';
import { theme } from '../style/theme';

// Dev-build-only gate, sitting above AuthProvider in main.tsx so nothing
// else in the app (including AuthProvider's own boot-time API call) loads
// until a working server URL is confirmed. Production never renders
// ServerUrlGateInner at all — this outer component makes that a plain,
// hook-free conditional return specifically so there's no rules-of-hooks
// concern about a production build sometimes calling the hooks below and
// sometimes not.
export function ServerUrlGate({ children }: { children: ReactNode })
{
    if (process.env.EXPO_PUBLIC_RUNTIME_API_URL_ENABLED !== 'true')
    {
        return <>{children}</>;
    }

    return <ServerUrlGateInner>{children}</ServerUrlGateInner>;
}

function ServerUrlGateInner({ children }: { children: ReactNode })
{
    const [initializing, setInitializing] = useState(true);
    const [url,          setUrl]          = useState('');
    const [checking,     setChecking]     = useState(false);
    const [error,        setError]        = useState<string | null>(null);
    const [confirmed,    setConfirmed]    = useState(false);

    useEffect(() =>
    {
        loadServerUrl()
            .then((saved) =>
            {
                if (saved)
                {
                    setUrl(saved);
                }
            })
            .finally(() => setInitializing(false));
    }, []);

    async function handleConfirm(): Promise<void>
    {
        const normalized = normalizeServerUrl(url);

        if (!normalized)
        {
            setError('יש להזין כתובת שרת.');
            return;
        }

        setError(null);
        setChecking(true);

        try
        {
            const reachable = await checkServerHealth(normalized);

            if (!reachable)
            {
                setError('לא ניתן להתחבר לשרת בכתובת הזו. בדקו את הכתובת ונסו שוב.');
                return;
            }

            await saveServerUrl(normalized);
            setBaseURL(normalized);
            setConfirmed(true);
        }
        finally
        {
            setChecking(false);
        }
    }

    if (confirmed)
    {
        return <>{children}</>;
    }

    if (initializing)
    {
        return (
            <View style={styles.loading}>
                <ActivityIndicator size="large" color={theme.palette.primary} />
            </View>
        );
    }

    return (
        <SafeAreaView style={styles.screen}>
            <View style={styles.content}>
                <ScreenHeading>כתובת שרת</ScreenHeading>

                <HebrewInput
                    label="כתובת השרת (dev)"
                    value={url}
                    onChangeText={setUrl}
                    placeholder="לדוגמה: 192.168.1.5:3000"
                    error={error ?? undefined}
                    onSubmitEditing={handleConfirm}
                />

                <View style={styles.buttonWrap}>
                    <PrimaryButton text="אישור" onPress={handleConfirm} loading={checking} />
                </View>
            </View>
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    loading:
    {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        backgroundColor: theme.palette.background,
    },
    screen:
    {
        flex: 1,
        backgroundColor: theme.palette.background,
    },
    content:
    {
        flex: 1,
        justifyContent: 'center',
        paddingHorizontal: theme.spacing.lg,
        gap: theme.spacing.md,
    },
    buttonWrap:
    {
        alignItems: 'center',
        marginTop: theme.spacing.sm,
    },
});
