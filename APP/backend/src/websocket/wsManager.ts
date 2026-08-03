import { WebSocket } from 'ws';

// Singleton registry: userId → active WebSocket connection.
// One connection per user; a new login from the same account replaces the old one.
class WsManager {
  private connections = new Map<string, WebSocket>();

  register(userId: string, ws: WebSocket): void {
    const existing = this.connections.get(userId);
    if (existing && existing.readyState === WebSocket.OPEN) {
      existing.close(1000, 'replaced');
    }
    this.connections.set(userId, ws);
  }

  unregister(userId: string, ws: WebSocket): void {
    if (this.connections.get(userId) === ws) {
      this.connections.delete(userId);
    }
  }

  isOnline(userId: string): boolean {
    const ws = this.connections.get(userId);
    return ws !== undefined && ws.readyState === WebSocket.OPEN;
  }

  send(userId: string, data: unknown): boolean {
    const ws = this.connections.get(userId);
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    ws.send(JSON.stringify(data));
    return true;
  }
}

export const wsManager = new WsManager();
