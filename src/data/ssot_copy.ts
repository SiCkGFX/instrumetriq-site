export const PLATFORM = 'X (Twitter)' as const;
export const SCORING = 'Hybrid sentiment system (RUN7 + RUN8)' as const;
export const AGGREGATION = 'cycle-based windows' as const;

export const WHAT_WE_DO = `Instrumetriq collects public posts from ${PLATFORM}, scores them with the ${SCORING}, aggregates activity and silence into ${AGGREGATION}, and compares aggregated signals with external market factors.` as const;
