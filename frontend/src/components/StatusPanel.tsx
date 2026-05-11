import type { AdvisorStatus, AdvisorSuggestResponse } from "../types";

interface StatusPanelProps {
  status: AdvisorStatus;
  advisor: AdvisorSuggestResponse | null;
  observations: number;
  pending: number;
  completedRows: number;
}

export function StatusPanel({ status, advisor, observations, pending, completedRows }: StatusPanelProps) {
  return (
    <section className="panel status-panel" aria-labelledby="status-title">
      <div className="section-heading">
        <div>
          <h2 id="status-title">Advisor Status</h2>
          <p>Track the current ask/tell phase and the amount of usable evidence.</p>
        </div>
        <span className={`connection-dot ${status !== "error" ? "connected" : ""}`} aria-label={status} />
      </div>

      <div className="status-stack">
        <div>
          <span className="metric-label">Phase</span>
          <strong>{advisor?.phase ?? "not started"}</strong>
        </div>
        <div>
          <span className="metric-label">Algorithm</span>
          <strong className="status-value">{advisor?.algorithm ?? "optional"}</strong>
        </div>
      </div>

      <div className="metric-grid">
        <Metric label="Status" value={status} />
        <Metric label="Saved" value={observations} />
        <Metric label="Editable" value={pending} />
        <Metric label="Complete" value={completedRows} />
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string | number; value: string | number }) {
  return (
    <div className="metric-card">
      <span className="metric-label">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
