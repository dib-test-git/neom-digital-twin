interface ModuleStripProps {
  modules: { id: number; status: "ok" | "warn" | "alert" }[];
  onSelect?: (id: number) => void;
}

const COLOR = { ok: "#15803d", warn: "#d97706", alert: "#b91c1c" };

export function ModuleStrip({ modules, onSelect }: ModuleStripProps) {
  return (
    <div style={{ display: "flex", gap: 4, padding: "8px 12px", background: "#0b1220" }}>
      {modules.map((m) => (
        <button
          key={m.id}
          onClick={() => onSelect?.(m.id)}
          title={`Module ${m.id} — ${m.status}`}
          style={{
            background: COLOR[m.status],
            color: "white",
            border: 0,
            borderRadius: 4,
            padding: "4px 10px",
            cursor: "pointer",
            fontSize: 12,
            fontFamily: "ui-monospace, SFMono-Regular, monospace",
          }}
        >
          M{String(m.id).padStart(2, "0")}
        </button>
      ))}
    </div>
  );
}
