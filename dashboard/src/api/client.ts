import {
  HealthResponse,
  Incident,
  IncidentsListResponse,
  ZonesResponse,
  StatsResponse,
} from "./schema";

export function isMockMode(): boolean {
  return false;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = endpoint.startsWith("http") ? endpoint : `/api${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;
  try {
    const res = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });

    if (!res.ok) {
      let code = "UNKNOWN_ERROR";
      let message = `Request failed with status ${res.status}`;
      try {
        const body = await res.json();
        if (body.detail) {
          message = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
        } else if (body.error) {
          code = body.error.code || code;
          message = body.error.message || message;
        }
      } catch {
        // fallback
      }
      throw new ApiError(res.status, code, message);
    }

    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(500, "NETWORK_ERROR", "Could not reach SiteSentinel backend at http://localhost:8000.");
  }
}

export const api = {
  async getHealth(): Promise<HealthResponse> {
    return request<HealthResponse>("/health");
  },

  async listIncidents(params?: {
    limit?: number;
    cursor?: string;
    since?: string;
    until?: string;
    type?: string;
    zone?: string;
    severity?: string;
    status?: string;
    q?: string;
  }): Promise<IncidentsListResponse> {
    const query = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== "") query.set(k, String(v));
      });
    }
    const qs = query.toString();
    const res = await request<any>(`/incidents${qs ? `?${qs}` : ""}`);
    if (Array.isArray(res)) {
      return { items: res, total: res.length };
    }
    return res as IncidentsListResponse;
  },

  async getIncident(id: string): Promise<Incident> {
    return request<Incident>(`/incidents/${id}`);
  },

  async ackIncident(id: string, user: string = "safety-officer", comment?: string): Promise<Incident> {
    return request<Incident>(`/incidents/${id}/ack`, {
      method: "POST",
      body: JSON.stringify({ user, comment }),
    });
  },

  async bulkAck(incidentIds: string[], user: string = "safety-officer", comment?: string): Promise<{ acknowledged_count: number }> {
    const res = await request<any>("/incidents/bulk-ack", {
      method: "POST",
      body: JSON.stringify({ incident_ids: incidentIds, user, comment }),
    });
    return { acknowledged_count: res.count || res.acknowledged_count || incidentIds.length };
  },

  async addNote(id: string, note: string, author: string = "safety-officer"): Promise<Incident> {
    return request<Incident>(`/incidents/${id}/note`, {
      method: "POST",
      body: JSON.stringify({ author, note }),
    });
  },

  async getZones(): Promise<ZonesResponse> {
    return request<ZonesResponse>("/zones");
  },

  async updateZones(zonesConfig: ZonesResponse): Promise<ZonesResponse> {
    await request<any>("/zones", {
      method: "PUT",
      body: JSON.stringify(zonesConfig),
    });
    return zonesConfig;
  },

  async getStats(window: string = "24h"): Promise<StatsResponse> {
    return request<StatsResponse>(`/stats?window=${window}`);
  },

  async getSystem(): Promise<any> {
    return request<any>("/system");
  },

  async getEngineReport(): Promise<any> {
    return request<any>("/system/engine-report");
  },

  async getPrivacyAudit(): Promise<any> {
    return request<any>("/system/privacy-audit");
  },
};
