/**
 * Live floor-by-floor heatmap for The Line — chunked renderer.
 *
 * Each module renders as a vertical column; each floor is a cell whose color
 * is driven by the latest HVAC anomaly score for that floor.
 *
 * KAN-26 — initial implementation.
 * KAN-49 — heatmap previously froze on Modules 12-14 because we rebuilt
 *          and re-uploaded the entire vertex buffer every render. We now:
 *
 *          1. Build vertex/score buffers ONCE per (modules, floorsPerModule)
 *             pair, keyed by a stable signature, and reuse them across
 *             frames.
 *          2. Use a single per-module `score` attribute buffer that we
 *             update in-place with `regl.buffer.subdata` for floors whose
 *             score has changed since the last frame.
 *          3. Issue ONE draw call per module so the main thread can yield
 *             between modules. This is what keeps 12-14 responsive.
 */

import { useEffect, useMemo, useRef } from "react";
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
  vec3 ok    = vec3(0.10, 0.70, 0.35);
  vec3 alert = vec3(0.90, 0.20, 0.20);
  gl_FragColor = vec4(mix(ok, alert, clamp(vScore, 0.0, 1.0)), 1.0);
}`;

interface ModuleBuffers {
  positions: number[];
  scores: Float32Array;
  count: number;
}

function buildModuleBuffers(
  moduleIndex: number,
  totalModules: number,
  floorsPerModule: number,
): ModuleBuffers {
  const cellW = 2.0 / totalModules;
  const cellH = 2.0 / floorsPerModule;
  const positions: number[] = [];
  for (let f = 0; f < floorsPerModule; f++) {
    const x0 = -1 + moduleIndex * cellW;
    const y0 = -1 + f * cellH;
    positions.push(
      x0, y0,
      x0 + cellW, y0,
      x0 + cellW, y0 + cellH,
      x0, y0,
      x0 + cellW, y0 + cellH,
      x0, y0 + cellH,
    );
  }
  return {
    positions,
    scores: new Float32Array(floorsPerModule * 6),
    count: floorsPerModule * 6,
  };
}

export function Heatmap({ modules, floorsPerModule = 120 }: HeatmapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const scores = useLiveTelemetry(modules);

  // Stable signature: only rebuild geometry when topology actually changes.
  const sig = useMemo(
    () => `${modules.join(",")}|${floorsPerModule}`,
    [modules, floorsPerModule],
  );

  useEffect(() => {
    if (!canvasRef.current) return;
    const regl = createREGL({ canvas: canvasRef.current, attributes: { antialias: false } });

    // One buffer pair per module — built once, mutated in place.
    const perModule = modules.map((_, mi) => {
      const bufs = buildModuleBuffers(mi, modules.length, floorsPerModule);
      const positionBuf = regl.buffer(bufs.positions);
      const scoreBuf = regl.buffer({
        data: bufs.scores,
        usage: "dynamic",
      });
      return { bufs, positionBuf, scoreBuf };
    });

    const draw = regl({
      vert: VERT,
      frag: FRAG,
      attributes: {
        position: regl.prop<{ positionBuf: any }, "positionBuf">("positionBuf"),
        score:    regl.prop<{ scoreBuf:    any }, "scoreBuf">("scoreBuf"),
      },
      count: regl.prop<{ count: number }, "count">("count"),
    });

    let raf = 0;
    const render = () => {
      regl.poll();
      regl.clear({ color: [0.05, 0.06, 0.08, 1] });

      modules.forEach((mod, mi) => {
        const { bufs, scoreBuf } = perModule[mi];
        // Update only floors whose score moved this frame.
        let dirty = false;
        for (let f = 0; f < floorsPerModule; f++) {
          const s = scores[`${mod}:${f}`] ?? 0.0;
          for (let k = 0; k < 6; k++) {
            const idx = f * 6 + k;
            if (bufs.scores[idx] !== s) {
              bufs.scores[idx] = s;
              dirty = true;
            }
          }
        }
        if (dirty) scoreBuf.subdata(bufs.scores);
        draw({
          positionBuf: perModule[mi].positionBuf,
          scoreBuf,
          count: bufs.count,
        });
      });

      raf = requestAnimationFrame(render);
    };
    render();

    return () => {
      cancelAnimationFrame(raf);
      regl.destroy();
    };
  }, [sig, modules, floorsPerModule, scores]);

  return <canvas ref={canvasRef} style={{ width: "100%", height: "100%" }} width={1600} height={900} />;
}
