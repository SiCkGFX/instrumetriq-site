/**
 * Entry Deep Dive Metrics Calculator
 * 
 * Pure functions to compute derived metrics from a single entry.
 * All calculations are retrospective and descriptive only.
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
 * Extract price path from spot_raw with elapsed time in minutes
 */
export function extractPricePath(entry: any): PricePoint[] {
  const spotRaw = entry?.spot_raw;
  if (!spotRaw || !Array.isArray(spotRaw) || spotRaw.length === 0) {
    return [];
  }

  const startTs = entry?.meta?.start_ts;
  if (!startTs) return [];

  const startTime = new Date(startTs).getTime();

  return spotRaw.map((spot: any) => {
    const ts = spot.ts || spot.timestamp;
    if (!ts) return null;
    
    const spotTime = new Date(ts).getTime();
    const elapsed_min = (spotTime - startTime) / (1000 * 60);
    
    // Use mid price if available, otherwise use price field
    const price = spot.mid ?? spot.price ?? null;
    
    return price !== null ? { elapsed_min, price } : null;
  }).filter((p: any) => p !== null);
}

/**
 * Extract sentiment scores over time from twitter_sentiment_windows
 */
export function extractSentimentPath(entry: any): SentimentPoint[] {
  const windows = entry?.twitter_sentiment_windows;
  if (!windows) return [];

  const points: SentimentPoint[] = [];
  const meta = entry?.meta;
  
  if (!meta?.start_ts) return [];
  
  // For simplicity, we'll use the window end times if available
  // last_cycle typically represents the most recent cycle
  // last_2_cycles represents aggregation over last 2 cycles
  
  const startTime = new Date(meta.start_ts).getTime();
  const endTime = meta.end_ts ? new Date(meta.end_ts).getTime() : startTime;
  const duration_min = (endTime - startTime) / (1000 * 60);
  
  if (windows.last_cycle?.hybrid_decision_stats?.mean_score !== undefined) {
    points.push({
      elapsed_min: duration_min * 0.75, // Place at 75% mark
      mean_score: windows.last_cycle.hybrid_decision_stats.mean_score,
      window_label: 'last_cycle'
    });
  }
  
  if (windows.last_2_cycles?.hybrid_decision_stats?.mean_score !== undefined) {
    points.push({
      elapsed_min: duration_min, // Place at end
      mean_score: windows.last_2_cycles.hybrid_decision_stats.mean_score,
      window_label: 'last_2_cycles'
    });
  }
  
  return points;
}

/**
 * Calculate derived metrics from a single entry
 */
export function calculateMetrics(entry: any): EntryMetrics {
  const pricePath = extractPricePath(entry);
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
  
  return {
    startPrice,
    endPrice,
    absoluteReturn,
    logReturn,
    mfe,
    mae,
    drawdown,
    volatility,
    medianSpread: derived.spread_bps ?? null,
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
