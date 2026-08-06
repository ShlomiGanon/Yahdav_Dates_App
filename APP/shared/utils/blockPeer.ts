import { clientMessage } from '../copy/client';
import type { ApiEnvelope } from '../types/api';

export interface BlockPeerCallbacks
{
    onSuccess: () => void;
    onError:   (message: string) => void;
}

// The "call block, then either proceed or surface an error" orchestration
// — was duplicated identically in mobile's hooks/usePeerProfile.ts
// (handleBlock) and web's PeerProfilePage.tsx (confirmBlock), differing
// only in what "proceed"/"surface an error" mean per platform (native
// Alert vs. navigate+state) — passed in via callbacks, same DI pattern as
// createAuthApi(client). The confirmation UI that triggers this stays
// entirely platform-specific. Takes the bound API call (e.g.
// usersApi.blockUser) rather than the whole usersApi object, to keep this
// narrowly testable. See APP/review.md finding 2.14.
export async function blockPeer(
    callBlockUser: (peerId: string) => Promise<ApiEnvelope>,
    peerId:        string,
    callbacks:     BlockPeerCallbacks,
): Promise<void>
{
    try
    {
        const data = await callBlockUser(peerId);

        if (data.success)
        {
            callbacks.onSuccess();
        }
        else
        {
            callbacks.onError(data.message);
        }
    }
    catch
    {
        callbacks.onError(clientMessage('block_user_failed'));
    }
}
