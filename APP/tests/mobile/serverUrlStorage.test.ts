jest.mock('@react-native-async-storage/async-storage', () =>
    require('@react-native-async-storage/async-storage/jest/async-storage-mock'),
);

import AsyncStorage from '@react-native-async-storage/async-storage';
import { saveServerUrl, loadServerUrl } from '../../mobile/src/auth/serverUrlStorage';

beforeEach(async () =>
{
    await AsyncStorage.clear();
});

describe('serverUrlStorage', () =>
{
    it('loadServerUrl returns null when nothing has been saved yet', async () =>
    {
        expect(await loadServerUrl()).toBeNull();
    });

    it('saveServerUrl then loadServerUrl round-trips the same value', async () =>
    {
        await saveServerUrl('http://192.168.1.5:3000');

        expect(await loadServerUrl()).toBe('http://192.168.1.5:3000');
    });

    it('a second saveServerUrl call overwrites the first', async () =>
    {
        await saveServerUrl('http://old-host:3000');
        await saveServerUrl('http://new-host:3000');

        expect(await loadServerUrl()).toBe('http://new-host:3000');
    });
});
