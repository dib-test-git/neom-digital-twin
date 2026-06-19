/**
 * Live floor-by-floor heatmap for The Line.
 *
 * Each module renders as a vertical column; each floor is a cell whose color
 * is driven by the latest HVAC anomaly score for that floor. Rendered with
 * regl so we can keep 60fps when all ~3000 floors are visible.
 *
 * KAN-26 — initial implementation.
 * KAN-49 — heatmap currently freezes when Modules 12–14 are in view. Working
 *          theory: we re-upload the full vertex buffer every frame instead
 *          of streaming updates per-floor. Fix in flight on
 *          `fix/heatmap-chunked-render`.
 */

import { useEffect, useRef } from "react";
import createREGL from "regl";

import { useLiveTelemetry } from "../hooks/useLiveTelemetry";

export interface HeatmapProps {
  modules: number[];          // module ids to display
  floorsPerModule?: number;   // defaults to 120
}

const VERT = `
precision mediump float;
attribute vec2 position;
attribute float score;
varying float vScore;
void main() {
  vScore = score;
  gl_Position = vec4(position, 0.0, 1.0);
}`;

const FRAG = `
precision mediump float;
varying float vScore;
void main() {
  // 0.0 = green (nominal), 1.0 = red (anomaly)
  vec3 ok    = vec3(0.10, 0.70, 0.35);
  vec3 alert = vec3(0.90, 0.20, 0.20);
  gl_FragColor = vec4(mix(ok, alert, clamp(vScore, 0.0, 1.0)), 1.0);
}`;

export function Heatmap({ modules, floorsPerModule = 120 }: HeatmapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const scores = useLiveTelemetry(modules);

  useEffect(() => {
    if (!canvasRef.current) return;
    const regl = createREGL({ canvas: canvasRef.current, attributes: { antialias: false } });

    const cellW = 2.0 / modules.length;
    const cellH = 2.0 / floorsPerModule;

    // KAN-49 NOTE: this builds the full buffer up front every render. That
    // is the root of the freeze for the Modules 12-14 case — we should
    // build per-module chunks and call regl.draw per chunk so the main
    // thread can yield between modules.
    const positions: number[] = [];
    const scoreAttr: number[] = [];
    modules.forEach((mod, mi) => {
      for (let f = 0; f < floorsPerModule; f++) {
        const x0 = -1 + mi * cellW;
        const y0 = -1 + f * cellH;
        positions.push(
          x0, y0,
          x0 + cellW, y0,
          x0 + cellW, y0 + cellH,
          x0, y0,
          x0 + cellW, y0 + cellH,
          x0, y0 + cellH,
        );
        const s = scores[`${mod}:${f}`] ?? 0.0;
        for (let k = 0; k < 6; k++) scoreAttr.push(s);
      }
    });

    const draw = regl({
      vert: VERT,
      frag: FRAG,
      attributes: { position: positions, score: scoreAttr },
      count: positions.length / 2,
    });

    let raf = 0;
    const loop = () => {
      regl.poll();
      regl.clear({ color: [0.05, 0.06, 0.08, 1] });
      draw();
      raf = requestAnimationFrame(loop);
    };
    loop();

    return () => {
      cancelAnimationFrame(raf);
      regl.destroy();
    };
  }, [modules, floorsPerModule, scores]);

  return <canvas ref={canvasRef} style={{ width: "100%", height: "100%" }} width={1600} height={900} />;
}
