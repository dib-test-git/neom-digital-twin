export interface Alert {
  id: string;
  module: number;
  floor: number;
  loop: string;
  score: number;
  openedAt: string;
}

interface Props {
  alerts: Alert[];
  onAck?: (id: string) => void;
}

export function AlertDrawer({ alerts, onAck }: Props) {
  return (
    <aside
      style={{
        width: 320,
        background: "#0f172a",
        color: "white",
        padding: 12,
        height: "100%",
        overflowY: "auto",
        fontFamily: "system-ui, sans-serif",
      }}
    >
      <h3 style={{ marginTop: 0 }}>Active alerts ({alerts.length})</h3>
      {alerts.length === 0 && <p style={{ opacity: 0.6 }}>No active anomalies.</p>}
      {alerts.map((a) => (
        <div key={a.id} style={{ borderTop: "1px solid #1e293b", padding: "8px 0" }}>
          <div style={{ fontWeight: 600 }}>
            M{a.module} F{a.floor} · {a.loop}
          </div>
          <div style={{ fontSize: 12, opacity: 0.7 }}>
            score {a.score.toFixed(3)} · since {new Date(a.openedAt).toLocaleTimeString()}
          </div>
          <button onClick={() => onAck?.(a.id)} style={{ marginTop: 4 }}>
            Acknowledge
          </button>
        </div>
      ))}
    </aside>
  );
}
