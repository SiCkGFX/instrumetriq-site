/**
 * Entry Deep Dive Metrics Calculator
 * 
 * Pure functions to compute derived metrics from a single entry.
 * All calculations are retrospective and descriptive only.
 * 
 * SCHEMA NOTES (v7):
 * - Spot prices are in separate file: sample_entries_spots_v7.json
 * - Each spot_price element has: {ts, mid, bid, ask, spread_bps}
 * - Sentiment windows: twitter_sentiment_windows.{last_cycle|last_2_cycles}.hybrid_decision_stats.mean_score
 * - Metadata: meta.{added_ts, expires_ts, duration_sec}
 * - Spread: derived.spread_bps
 */

export interface EntryMetrics {
  startPrice: number | null;
  endPrice: number | null;
  absoluteReturn: number | null;
  logReturn: number | null;
  mfe: number | null; // Maximum Favorable Excursion
  mae: number | null; // Maximum Adverse Excursion
  drawdown: number | null; // Peak-to-trough drawdown
  volatility: number | null; // Realized volatility
  medianSpread: number | null;
  meanSentiment: number | null;
}

export interface PricePoint {
  elapsed_min: number;
  price: number;
}

export interface SentimentPoint {
  elapsed_min: number;
  mean_score: number;
  window_label: string;
}

/**
 * Extract price path from spot_prices array (passed separately)
 * Spot prices come from sample_entries_spots_v7.json: spots[].spot_prices[]
 * Each element: {ts: ISO8601, mid: number, bid: number, ask: number, spread_bps: number}
 */
export function extractPricePath(entry: any, spotPrices: any[]): PricePoint[] {
  if (!spotPrices || !Array.isArray(spotPrices) || spotPrices.length === 0) {
    return [];
  }

  const startTs = entry?.meta?.added_ts;
  if (!startTs) return [];

  const startTime = new Date(startTs).getTime();

  const points = spotPrices.map((spot: any) => {
    const ts = spot.ts;
    if (!ts) return null;
    
    const spotTime = new Date(ts).getTime();
    const elapsed_min = (spotTime - startTime) / (1000 * 60);
    
    // Priority: mid price > (bid+ask)/2 > last
    const price = spot.mid ?? (spot.bid != null && spot.ask != null ? (spot.bid + spot.ask) / 2 : null);
    
    return price !== null ? { elapsed_min, price } : null;
  }).filter((p: PricePoint | null): p is PricePoint => p !== null);
  
  return points;
}

/**
 * Extract sentiment scores over time from twitter_sentiment_windows
 * Schema path: entry.twitter_sentiment_windows.{last_cycle|last_2_cycles}.hybrid_decision_stats.mean_score
 */
export function extractSentimentPath(entry: any): SentimentPoint[] {
  const windows = entry?.twitter_sentiment_windows;
  if (!windows) return [];

  const points: SentimentPoint[] = [];
  const meta = entry?.meta;
  
  if (!meta?.added_ts) return [];
  
  // Sentiment windows represent aggregation over different time periods
  // last_cycle = most recent cycle
  // last_2_cycles = aggregation over last 2 cycles
  
  const startTime = new Date(meta.added_ts).getTime();
  const endTime = meta.expires_ts ? new Date(meta.expires_ts).getTime() : startTime;
  const duration_min = (endTime - startTime) / (1000 * 60);
  
  // Add last_cycle at 75% mark if present
  if (windows.last_cycle?.hybrid_decision_stats?.mean_score !== undefined) {
    points.push({
      elapsed_min: duration_min * 0.75,
      mean_score: windows.last_cycle.hybrid_decision_stats.mean_score,
      window_label: 'last_cycle'
    });
  }
  
  // Add last_2_cycles at end if present
  if (windows.last_2_cycles?.hybrid_decision_stats?.mean_score !== undefined) {
    points.push({
      elapsed_min: duration_min,
      mean_score: windows.last_2_cycles.hybrid_decision_stats.mean_score,
      window_label: 'last_2_cycles'
    });
  }
  
  return points;
}

/**
 * Calculate derived metrics from a single entry
 * Requires spot_prices array to be passed separately
 */
export function calculateMetrics(entry: any, spotPrices: any[]): EntryMetrics {
  const pricePath = extractPricePath(entry, spotPrices);
  const derived = entry?.derived || {};
  const sentiment = entry?.twitter_sentiment_windows?.last_2_cycles?.hybrid_decision_stats;
  
  let startPrice: number | null = null;
  let endPrice: number | null = null;
  let absoluteReturn: number | null = null;
  let logReturn: number | null = null;
  let mfe: number | null = null;
  let mae: number | null = null;
  let drawdown: number | null = null;
  let volatility: number | null = null;
  
  if (pricePath.length >= 2) {
    startPrice = pricePath[0].price;
    endPrice = pricePath[pricePath.length - 1].price;
    
    // Absolute return
    absoluteReturn = ((endPrice - startPrice) / startPrice) * 100;
    
    // Log return
    logReturn = Math.log(endPrice / startPrice);
    
    // MFE (Maximum Favorable Excursion) - best price move in direction of profit
    // MAE (Maximum Adverse Excursion) - worst price move against position
    let maxPrice = startPrice;
    let minPrice = startPrice;
    let maxGain = 0;
    let maxLoss = 0;
    
    for (const point of pricePath) {
      if (point.price > maxPrice) maxPrice = point.price;
      if (point.price < minPrice) minPrice = point.price;
      
      const gain = ((point.price - startPrice) / startPrice) * 100;
      const loss = ((point.price - startPrice) / startPrice) * 100;
      
      if (gain > maxGain) maxGain = gain;
      if (loss < maxLoss) maxLoss = loss;
    }
    
    mfe = maxGain;
    mae = maxLoss;
    
    // Peak-to-trough drawdown
    let peak = pricePath[0].price;
    let maxDD = 0;
    
    for (const point of pricePath) {
      if (point.price > peak) {
        peak = point.price;
      }
      const dd = ((point.price - peak) / peak) * 100;
      if (dd < maxDD) {
        maxDD = dd;
      }
    }
    
    drawdown = maxDD;
    
    // Realized volatility (standard deviation of log returns)
    if (pricePath.length > 2) {
      const logReturns = [];
      for (let i = 1; i < pricePath.length; i++) {
        logReturns.push(Math.log(pricePath[i].price / pricePath[i - 1].price));
      }
      
      const mean = logReturns.reduce((a, b) => a + b, 0) / logReturns.length;
      const variance = logReturns.reduce((sum, r) => sum + Math.pow(r - mean, 2), 0) / logReturns.length;
      volatility = Math.sqrt(variance);
    }
  }
  
  // Median spread calculation from spot_prices array
  let medianSpread: number | null = null;
  if (spotPrices && spotPrices.length > 0) {
    const spreads = spotPrices
      .map((s: any) => s.spread_bps)
      .filter((s: any) => s != null && !isNaN(s))
      .sort((a: number, b: number) => a - b);
    
    if (spreads.length > 0) {
      const mid = Math.floor(spreads.length / 2);
      medianSpread = spreads.length % 2 === 0 
        ? (spreads[mid - 1] + spreads[mid]) / 2 
        : spreads[mid];
    }
  }
  
  // Fallback to derived.spread_bps if median not available
  if (medianSpread === null) {
    medianSpread = derived.spread_bps ?? null;
  }
  
  return {
    startPrice,
    endPrice,
    absoluteReturn,
    logReturn,
    mfe,
    mae,
    drawdown,
    volatility,
    medianSpread,
    meanSentiment: sentiment?.mean_score ?? null
  };
}

/**
 * Format a metric value for display
 */
export function formatMetric(value: number | null, decimals: number = 2): string {
  if (value === null || value === undefined || isNaN(value)) {
    return 'N/A';
  }
  return value.toFixed(decimals);
}
