jest.mock('../../mobile/src/auth/serverUrlStorage', () => ({
    loadServerUrl: jest.fn(),
    saveServerUrl: jest.fn(),
}));

jest.mock('../../mobile/src/utils/checkServerHealth', () => ({
    checkServerHealth: jest.fn(),
}));

jest.mock('../../mobile/src/api/axios', () => ({
    setBaseURL: jest.fn(),
}));

import React from 'react';
import { Text } from 'react-native';
import { render, fireEvent, waitFor } from '@testing-library/react-native';
import { ServerUrlGate } from '../../mobile/src/components/ServerUrlGate';
import { loadServerUrl, saveServerUrl } from '../../mobile/src/auth/serverUrlStorage';
import { checkServerHealth } from '../../mobile/src/utils/checkServerHealth';
import { setBaseURL } from '../../mobile/src/api/axios';

const loadServerUrlMock = loadServerUrl as jest.Mock;
const saveServerUrlMock = saveServerUrl as jest.Mock;
const checkServerHealthMock = checkServerHealth as jest.Mock;
const setBaseURLMock = setBaseURL as jest.Mock;

const ORIGINAL_ENV = process.env.EXPO_PUBLIC_RUNTIME_API_URL_ENABLED;

function setGateEnabled(enabled: boolean): void
{
    if (enabled)
    {
        process.env.EXPO_PUBLIC_RUNTIME_API_URL_ENABLED = 'true';
    }
    else
    {
        delete process.env.EXPO_PUBLIC_RUNTIME_API_URL_ENABLED;
    }
}

beforeEach(() =>
{
    loadServerUrlMock.mockReset();
    saveServerUrlMock.mockReset();
    checkServerHealthMock.mockReset();
    setBaseURLMock.mockReset();
    loadServerUrlMock.mockResolvedValue(null);
});

afterAll(() =>
{
    if (ORIGINAL_ENV === undefined)
    {
        delete process.env.EXPO_PUBLIC_RUNTIME_API_URL_ENABLED;
    }
    else
    {
        process.env.EXPO_PUBLIC_RUNTIME_API_URL_ENABLED = ORIGINAL_ENV;
    }
});

describe('ServerUrlGate — production (flag unset)', () =>
{
    // render() is async in @testing-library/react-native v14 — same as
    // renderHook(), see tests/mobile/useAutoLogin.test.ts's note.
    it('renders children immediately, with no gate UI and no storage/network calls at all', async () =>
    {
        setGateEnabled(false);

        const { getByText, queryByPlaceholderText } = await render(
            <ServerUrlGate><Text>app content</Text></ServerUrlGate>,
        );

        expect(getByText('app content')).toBeTruthy();
        expect(queryByPlaceholderText('לדוגמה: 192.168.1.5:3000')).toBeNull();
        expect(loadServerUrlMock).not.toHaveBeenCalled();
        expect(checkServerHealthMock).not.toHaveBeenCalled();
    });
});

describe('ServerUrlGate — dev build (flag enabled)', () =>
{
    beforeEach(() =>
    {
        setGateEnabled(true);
    });

    it('does not render children until a URL is confirmed', async () =>
    {
        const { queryByText } = await render(
            <ServerUrlGate><Text>app content</Text></ServerUrlGate>,
        );

        await waitFor(() => expect(loadServerUrlMock).toHaveBeenCalled());
        expect(queryByText('app content')).toBeNull();
    });

    it('pre-fills the input with a previously saved URL', async () =>
    {
        loadServerUrlMock.mockResolvedValue('http://192.168.1.5:3000');

        const { findByDisplayValue } = await render(
            <ServerUrlGate><Text>app content</Text></ServerUrlGate>,
        );

        expect(await findByDisplayValue('http://192.168.1.5:3000')).toBeTruthy();
    });

    it('leaves the input empty when nothing was previously saved', async () =>
    {
        loadServerUrlMock.mockResolvedValue(null);

        const { findByPlaceholderText } = await render(
            <ServerUrlGate><Text>app content</Text></ServerUrlGate>,
        );

        const input = await findByPlaceholderText('לדוגמה: 192.168.1.5:3000');
        expect(input.props.value).toBe('');
    });

    it('shows an error and never calls checkServerHealth when confirming an empty address', async () =>
    {
        const { findByPlaceholderText, findByText, getByText } = await render(
            <ServerUrlGate><Text>app content</Text></ServerUrlGate>,
        );
        await findByPlaceholderText('לדוגמה: 192.168.1.5:3000');

        await fireEvent.press(getByText('אישור'));

        expect(await findByText('יש להזין כתובת שרת.')).toBeTruthy();
        expect(checkServerHealthMock).not.toHaveBeenCalled();
    });

    it('auto-prepends http:// and trims a trailing slash before validating', async () =>
    {
        checkServerHealthMock.mockResolvedValue(true);
        const { findByPlaceholderText, getByText } = await render(
            <ServerUrlGate><Text>app content</Text></ServerUrlGate>,
        );
        const input = await findByPlaceholderText('לדוגמה: 192.168.1.5:3000');

        await fireEvent.changeText(input, '192.168.1.5:3000/');
        await fireEvent.press(getByText('אישור'));

        await waitFor(() => expect(checkServerHealthMock).toHaveBeenCalledWith('http://192.168.1.5:3000'));
    });

    it('on a successful check: saves the URL, configures the API client, and mounts the app', async () =>
    {
        checkServerHealthMock.mockResolvedValue(true);
        const { findByPlaceholderText, getByText, findByText } = await render(
            <ServerUrlGate><Text>app content</Text></ServerUrlGate>,
        );
        const input = await findByPlaceholderText('לדוגמה: 192.168.1.5:3000');

        await fireEvent.changeText(input, 'http://192.168.1.5:3000');
        await fireEvent.press(getByText('אישור'));

        expect(await findByText('app content')).toBeTruthy();
        expect(saveServerUrlMock).toHaveBeenCalledWith('http://192.168.1.5:3000');
        expect(setBaseURLMock).toHaveBeenCalledWith('http://192.168.1.5:3000');
    });

    it('on a failed check: shows an error, does not save, does not configure the client, stays on the gate', async () =>
    {
        checkServerHealthMock.mockResolvedValue(false);
        const { findByPlaceholderText, getByText, findByText, queryByText } = await render(
            <ServerUrlGate><Text>app content</Text></ServerUrlGate>,
        );
        const input = await findByPlaceholderText('לדוגמה: 192.168.1.5:3000');

        await fireEvent.changeText(input, 'http://unreachable-host:3000');
        await fireEvent.press(getByText('אישור'));

        expect(await findByText('לא ניתן להתחבר לשרת בכתובת הזו. בדקו את הכתובת ונסו שוב.')).toBeTruthy();
        expect(queryByText('app content')).toBeNull();
        expect(saveServerUrlMock).not.toHaveBeenCalled();
        expect(setBaseURLMock).not.toHaveBeenCalled();
    });

    it('a retry after a failed check can still succeed', async () =>
    {
        checkServerHealthMock.mockResolvedValueOnce(false).mockResolvedValueOnce(true);
        const { findByPlaceholderText, getByText, findByText } = await render(
            <ServerUrlGate><Text>app content</Text></ServerUrlGate>,
        );
        const input = await findByPlaceholderText('לדוגמה: 192.168.1.5:3000');

        await fireEvent.changeText(input, 'http://192.168.1.5:3000');
        await fireEvent.press(getByText('אישור'));
        await findByText('לא ניתן להתחבר לשרת בכתובת הזו. בדקו את הכתובת ונסו שוב.');

        await fireEvent.press(getByText('אישור'));

        expect(await findByText('app content')).toBeTruthy();
    });
});
