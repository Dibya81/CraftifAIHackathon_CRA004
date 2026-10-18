import React, { useState, useEffect } from "react";
import { ShieldCheck, CheckCircle2, Clock, Cpu, RefreshCw, AlertCircle } from "lucide-react";
import { Badge } from "../design/primitives/Badge";
import { Button } from "../design/primitives/Button";
import { Panel } from "../design/primitives/Panel";

interface LedgerEntry {
  claim_key?: string;
  source_file: string;
  sha256?: string;
  status: "MEASURED" | "SIMULATED" | "PENDING";
  description?: string;
  command?: string;
  verified?: boolean;
}

interface LedgerResponse {
  verified: boolean;
  errors?: string[];
  ledger?: {
    claims?: Record<string, LedgerEntry>;
  };
  timestamp?: string;
}

interface IntegrityResponse {
  status: string;
  valid: boolean;
  error?: string | null;
  log_path?: string;
}

export const EvidenceView: React.FC = () => {
  const [ledgerData, setLedgerData] = useState<LedgerResponse | null>(null);
  const [integrityData, setIntegrityData] = useState<IntegrityResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [reverifying, setReverifying] = useState<boolean>(false);

  const fetchEvidence = async () => {
    try {
      setLoading(true);
      const [ledgerRes, integrityRes] = await Promise.all([
        fetch("/api/evidence/ledger").then((r) => (r.ok ? r.json() : null)),
        fetch("/api/system/log-integrity").then((r) => (r.ok ? r.json() : null)),
      ]);
      setLedgerData(ledgerRes);
      setIntegrityData(integrityRes);
    } catch (e) {
      console.error("Failed to fetch evidence ledger", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEvidence();
  }, []);

  const handleReverify = async () => {
    setReverifying(true);
    await fetchEvidence();
    setReverifying(false);
  };

  const claimsList: { key: string; entry: LedgerEntry }[] = [];
  if (ledgerData?.ledger?.claims) {
    Object.entries(ledgerData.ledger.claims).forEach(([key, val]) => {
      claimsList.push({ key, entry: val });
    });
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "MEASURED":
        return <Badge variant="ok">MEASURED</Badge>;
      case "SIMULATED":
        return <Badge variant="warn">SIMULATED</Badge>;
      case "PENDING":
        return <Badge variant="info">PENDING</Badge>;
      default:
        return <Badge variant="neutral">{status}</Badge>;
    }
  };

  return (
    <div style={{ padding: "24px", display: "flex", flexDirection: "column", gap: "24px", maxWidth: "1200px" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 style={{ fontSize: "20px", fontWeight: 600, color: "var(--text)", margin: "0 0 4px 0", display: "flex", alignItems: "center", gap: "8px" }}>
            <ShieldCheck size={22} style={{ color: "var(--accent)" }} />
            Cryptographic Evidence & Claims Ledger
          </h1>
          <p style={{ margin: 0, fontSize: "13px", color: "var(--text-muted)" }}>
            Zero-trust ledger linking architectural claims to committed SHA-256 artifacts.
          </p>
        </div>
        <Button variant="secondary" onClick={handleReverify} disabled={reverifying}>
          <RefreshCw size={14} className={reverifying ? "spin" : ""} style={{ marginRight: "6px" }} />
          Re-verify Hashes
        </Button>
      </div>

      {/* Overview Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "16px" }}>
        <Panel style={{ padding: "16px", display: "flex", alignItems: "center", gap: "14px" }}>
          <div style={{ padding: "10px", borderRadius: "8px", backgroundColor: ledgerData?.verified ? "rgba(16, 185, 129, 0.1)" : "rgba(239, 68, 68, 0.1)" }}>
            {ledgerData?.verified ? <CheckCircle2 size={24} color="#10B981" /> : <AlertCircle size={24} color="#EF4444" />}
          </div>
          <div>
            <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>Claims Ledger Integrity</div>
            <div style={{ fontSize: "16px", fontWeight: 600, color: "var(--text)" }}>
              {ledgerData?.verified ? "All Hashes Verified" : "Verification Failed"}
            </div>
            <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>{claimsList.length} total ledger entries</div>
          </div>
        </Panel>

        <Panel style={{ padding: "16px", display: "flex", alignItems: "center", gap: "14px" }}>
          <div style={{ padding: "10px", borderRadius: "8px", backgroundColor: integrityData?.valid ? "rgba(16, 185, 129, 0.1)" : "rgba(245, 158, 11, 0.1)" }}>
            {integrityData?.valid ? <CheckCircle2 size={24} color="#10B981" /> : <Clock size={24} color="#F59E0B" />}
          </div>
          <div>
            <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>Incident Log Hash Chain</div>
            <div style={{ fontSize: "16px", fontWeight: 600, color: "var(--text)" }}>
              {integrityData?.valid ? "Chain Intact (0 Tampering)" : "Chain Broken"}
            </div>
            <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>logs/incidents.jsonl</div>
          </div>
        </Panel>

        <Panel style={{ padding: "16px", display: "flex", alignItems: "center", gap: "14px" }}>
          <div style={{ padding: "10px", borderRadius: "8px", backgroundColor: "rgba(59, 130, 246, 0.1)" }}>
            <Cpu size={24} color="#3B82F6" />
          </div>
          <div>
            <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>Physical Hardware Gate</div>
            <div style={{ fontSize: "16px", fontWeight: 600, color: "var(--text)" }}>Pending Booth Check-in</div>
            <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>docs/RUNBOOK.md checklist</div>
          </div>
        </Panel>
      </div>

      {/* Ledger Table */}
      <Panel style={{ padding: "0", overflow: "hidden" }}>
        <div style={{ padding: "14px 18px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontWeight: 600, fontSize: "14px", color: "var(--text)" }}>Ledger Claims Matrix</div>
          <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>Source: evidence/ledger.yaml</div>
        </div>

        {loading ? (
          <div style={{ padding: "32px", textAlign: "center", color: "var(--text-muted)", fontSize: "13px" }}>
            Loading ledger verification...
          </div>
        ) : claimsList.length === 0 ? (
          <div style={{ padding: "32px", textAlign: "center", color: "var(--text-muted)", fontSize: "13px" }}>
            No claims ledger records found.
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px", textAlign: "left" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)", backgroundColor: "var(--surface-hover)" }}>
                  <th style={{ padding: "10px 16px", color: "var(--text-muted)", fontWeight: 500 }}>Claim Key</th>
                  <th style={{ padding: "10px 16px", color: "var(--text-muted)", fontWeight: 500 }}>Status</th>
                  <th style={{ padding: "10px 16px", color: "var(--text-muted)", fontWeight: 500 }}>Source File</th>
                  <th style={{ padding: "10px 16px", color: "var(--text-muted)", fontWeight: 500 }}>SHA-256 Digest</th>
                  <th style={{ padding: "10px 16px", color: "var(--text-muted)", fontWeight: 500 }}>Provenance</th>
                </tr>
              </thead>
              <tbody>
                {claimsList.map(({ key, entry }) => (
                  <tr key={key} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td style={{ padding: "12px 16px", fontFamily: "var(--font-mono)", fontWeight: 500 }}>
                      {key}
                    </td>
                    <td style={{ padding: "12px 16px" }}>
                      {getStatusBadge(entry.status)}
                    </td>
                    <td style={{ padding: "12px 16px", color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: "12px" }}>
                      {entry.source_file || "-"}
                    </td>
                    <td style={{ padding: "12px 16px", fontFamily: "var(--font-mono)", fontSize: "11px", color: "var(--text-muted)" }}>
                      {entry.sha256 ? `${entry.sha256.substring(0, 12)}...` : "-"}
                    </td>
                    <td style={{ padding: "12px 16px", color: "var(--text)", fontSize: "12px" }}>
                      {entry.description || entry.command || "Committed repository artifact"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
};
