export const PLATFORM = 'X (Twitter)' as const;
export const SCORING = 'domain-specific sentiment model trained on crypto-related language' as const;
export const AGGREGATION = 'cycle-based windows' as const;

export const WHAT_WE_DO = `Instrumetriq observes public posts from ${PLATFORM}, evaluates sentiment at ingestion time using a ${SCORING}, aggregates activity and silence into ${AGGREGATION}, and compares aggregated signals with external market data for research.` as const;
