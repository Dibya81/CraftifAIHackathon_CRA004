export type WebSocketConnectionState = "connected" | "reconnecting" | "disconnected";

export interface LiveMessage {
  type: "incident" | "incident_updated" | "incident_acked" | "health" | "stats_delta" | "ping" | "pong";
  data?: any;
}

export type MessageListener = (msg: LiveMessage) => void;

class WebSocketManager {
  private ws: WebSocket | null = null;
  private listeners: Set<MessageListener> = new Set();
  private connectionListeners: Set<(state: WebSocketConnectionState) => void> = new Set();
  private reconnectAttempts = 0;
  private reconnectTimer: any = null;
  private pingIntervalTimer: any = null;
  private seenIncidentIds: Set<string> = new Set();
  private currentState: WebSocketConnectionState = "disconnected";

  constructor() {
    if (typeof window !== "undefined") {
      this.init();
    }
  }

  private setConnectionState(state: WebSocketConnectionState) {
    this.currentState = state;
    this.connectionListeners.forEach((l) => l(state));
  }

  public getConnectionState(): WebSocketConnectionState {
    return this.currentState;
  }

  public subscribe(listener: MessageListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  public onConnectionChange(listener: (state: WebSocketConnectionState) => void): () => void {
    this.connectionListeners.add(listener);
    listener(this.currentState);
    return () => this.connectionListeners.delete(listener);
  }

  private init() {
    this.connect();
  }

  private connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.setConnectionState(this.reconnectAttempts === 0 ? "disconnected" : "reconnecting");

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const url = `${protocol}//${host}/ws/live`;

    try {
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this.setConnectionState("connected");
        this.startHeartbeat();
      };

      this.ws.onmessage = (event) => {
        try {
          const msg: LiveMessage = JSON.parse(event.data);
          this.handleIncomingMessage(msg);
        } catch {
          // Ignore unparseable frames
        }
      };

      this.ws.onclose = () => {
        this.stopHeartbeat();
        this.scheduleReconnect();
      };

      this.ws.onerror = () => {
        if (this.ws) this.ws.close();
      };
    } catch {
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect() {
    this.setConnectionState("reconnecting");
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);

    // Exponential backoff with ceiling (1s, 2s, 4s, 8s, max 10s)
    const delay = Math.min(1000 * Math.pow(1.5, this.reconnectAttempts), 10000);
    this.reconnectAttempts++;

    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, delay);
  }

  private startHeartbeat() {
    this.stopHeartbeat();
    this.pingIntervalTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: "ping" }));
      }
    }, 15000);
  }

  private stopHeartbeat() {
    if (this.pingIntervalTimer) clearInterval(this.pingIntervalTimer);
  }

  private handleIncomingMessage(msg: LiveMessage) {
    if (msg.type === "incident" && msg.data?.incident_id) {
      if (this.seenIncidentIds.has(msg.data.incident_id)) {
        return; // Deduplicate
      }
      this.seenIncidentIds.add(msg.data.incident_id);
    }
    this.listeners.forEach((l) => l(msg));
  }

  public destroy() {
    if (this.ws) this.ws.close();
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.stopHeartbeat();
    this.listeners.clear();
    this.connectionListeners.clear();
  }
}

export const wsManager = new WebSocketManager();
