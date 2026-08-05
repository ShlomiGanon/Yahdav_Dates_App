// Live chat (conversation list + open conversation) on both platforms rides
// the same backend `/ws?token=...` connection (see
// backend/src/websocket/wsServer.ts) and the same reconnect policy. This
// used to be two separately-typed-out copies (mobile's useConversations.ts
// and useMessages.ts each carried their own backoff loop) — pulled in here
// so mobile and web share one implementation instead of two that can drift.
export const WS_RECONNECT =
{
    INITIAL_DELAY_MS: 1_000,
    MAX_DELAY_MS:     30_000,
    BACKOFF_FACTOR:   2,
    MAX_ATTEMPTS:     10,
} as const;

// `https?://host` -> `ws(s)://host/ws?token=...`. Works for both a browser
// `axios` baseURL and Expo's, since both are plain http(s) URLs.
export function buildWsUrl(baseUrl: string, token: string): string
{
    const wsBase = (baseUrl ?? '').replace(/^https?/, (protocol) =>
        protocol === 'https' ? 'wss' : 'ws');

    return `${wsBase}/ws?token=${encodeURIComponent(token)}`;
}

export interface ReconnectingSocketOptions
{
    // Called fresh on every (re)connect attempt so a rotated access token is
    // always picked up, rather than closing over a stale one.
    buildUrl:  () => string;
    onMessage: (raw: string) => void;
    onOpen?:   () => void;
}

export interface ReconnectingSocketHandle
{
    // Returns true if the frame went out over a live socket, false if the
    // caller should fall back to an HTTP request instead.
    send:  (data: string) => boolean;
    close: () => void;
}

// Opens a WebSocket that reconnects with exponential backoff on an
// unexpected close, up to WS_RECONNECT.MAX_ATTEMPTS. A deliberate close()
// stops the reconnect loop for good.
export function openReconnectingSocket(options: ReconnectingSocketOptions): ReconnectingSocketHandle
{
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let reconnectDelay = WS_RECONNECT.INITIAL_DELAY_MS as number;
    let reconnectCount = 0;
    let closed = false;

    function connect(): void
    {
        const ws = new WebSocket(options.buildUrl());

        ws.onopen = () =>
        {
            reconnectDelay = WS_RECONNECT.INITIAL_DELAY_MS;
            reconnectCount = 0;
            options.onOpen?.();
        };

        ws.onmessage = (event: { data: unknown }) =>
        {
            options.onMessage(String(event.data));
        };

        ws.onclose = () =>
        {
            if (closed || reconnectCount >= WS_RECONNECT.MAX_ATTEMPTS)
            {
                return;
            }

            reconnectTimer = setTimeout(() =>
            {
                reconnectCount += 1;
                reconnectDelay = Math.min(reconnectDelay * WS_RECONNECT.BACKOFF_FACTOR, WS_RECONNECT.MAX_DELAY_MS);
                connect();
            }, reconnectDelay);
        };

        socket = ws;
    }

    connect();

    return {
        send(data: string): boolean
        {
            if (socket?.readyState === WebSocket.OPEN)
            {
                socket.send(data);
                return true;
            }

            return false;
        },

        close(): void
        {
            closed = true;

            if (reconnectTimer)
            {
                clearTimeout(reconnectTimer);
            }

            socket?.close();
            socket = null;
        },
    };
}
