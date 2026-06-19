import { useState } from "react";

import { Heatmap } from "../components/Heatmap";
import { ModuleStrip } from "../components/ModuleStrip";
import { AlertDrawer, type Alert } from "../components/AlertDrawer";

const ONBOARDED_MODULES = [1, 2, 3, 4]; // KAN-24

export function Dashboard() {
  // Placeholder until /api/alerts subscription is wired in.
  const [alerts, setAlerts] = useState<Alert[]>([]);

  return (
    <div
      style={{
        display: "grid",
        gridTemplateRows: "auto 1fr",
        gridTemplateColumns: "1fr 320px",
        height: "100vh",
        background: "#020617",
        color: "white",
      }}
    >
      <header style={{ gridColumn: "1 / 3" }}>
        <ModuleStrip
          modules={ONBOARDED_MODULES.map((id) => ({ id, status: "ok" as const }))}
        />
      </header>
      <main>
        <Heatmap modules={ONBOARDED_MODULES} />
      </main>
      <AlertDrawer alerts={alerts} onAck={(id) => setAlerts((a) => a.filter((x) => x.id !== id))} />
    </div>
  );
}
