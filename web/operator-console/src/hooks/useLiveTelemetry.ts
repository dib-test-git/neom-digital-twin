import { useSubscription, gql } from "@apollo/client";
import { useMemo } from "react";

const SUB = gql`
  subscription LiveHvacScores($modules: [Int!]!) {
    hvacScores(modules: $modules) {
      module
      floor
      score
    }
  }
`;

interface HvacScoreEvent {
  module: number;
  floor: number;
  score: number;
}

export function useLiveTelemetry(modules: number[]): Record<string, number> {
  const { data } = useSubscription<{ hvacScores: HvacScoreEvent }>(SUB, {
    variables: { modules },
  });

  return useMemo(() => {
    const map: Record<string, number> = {};
    if (data?.hvacScores) {
      const e = data.hvacScores;
      map[`${e.module}:${e.floor}`] = e.score;
    }
    return map;
  }, [data]);
}
