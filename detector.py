"""
Market Regime Detection
Detects: Trending Up, Trending Down, Ranging, High Volatility, Low Volatility.
Routes the correct strategy to each regime automatically.
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional
from ..core.logging import get_logger
from ..strategies.technical_indicators import TechnicalIndicators

logger = get_logger(__name__)


class MarketRegime(str, Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    UNCERTAIN = "uncertain"


REGIME_STRATEGY_MAP = {
    MarketRegime.TRENDING_UP: ["trend_following"],
    MarketRegime.TRENDING_DOWN: ["trend_following"],
    MarketRegime.RANGING: ["scalping", "dca"],
    MarketRegime.HIGH_VOLATILITY: [],          # No trading in extreme volatility
    MarketRegime.LOW_VOLATILITY: ["dca"],
    MarketRegime.UNCERTAIN: ["dca"],
}

REGIME_DESCRIPTIONS = {
    MarketRegime.TRENDING_UP:   "Strong uptrend — Trend Following active",
    MarketRegime.TRENDING_DOWN: "Strong downtrend — Trend Following (short) active",
    MarketRegime.RANGING:       "Sideways market — Scalping + DCA active",
    MarketRegime.HIGH_VOLATILITY: "Extreme volatility — All trading paused",
    MarketRegime.LOW_VOLATILITY:  "Low volatility — DCA only",
    MarketRegime.UNCERTAIN:     "No clear regime — DCA only",
}


@dataclass
class RegimeResult:
    regime: MarketRegime
    confidence: float          # 0.0 to 1.0
    description: str
    active_strategies: List[str]
    metrics: Dict


class MarketRegimeDetector:
    """
    Detects market regime using:
    1. ADX — trend strength
    2. ATR % — volatility level
    3. Bollinger Band width — squeeze detection
    4. EMA slope — trend direction
    5. Price action structure — higher highs/lows
    """

    def __init__(
        self,
        adx_period: int = 14,
        adx_trend_threshold: float = 25.0,
        adx_strong_trend: float = 40.0,
        volatility_high_threshold: float = 4.0,   # ATR% > 4% = high vol
        volatility_low_threshold: float = 0.8,    # ATR% < 0.8% = low vol
    ):
        self.adx_period = adx_period
        self.adx_trend_threshold = adx_trend_threshold
        self.adx_strong_trend = adx_strong_trend
        self.vol_high = volatility_high_threshold
        self.vol_low = volatility_low_threshold

    def detect(self, candles: List[Dict]) -> RegimeResult:
        """
        Detect market regime from OHLCV candles.

        Args:
            candles: List of OHLCV dicts, min 50 candles

        Returns:
            RegimeResult with regime, confidence, active strategies
        """
        df = TechnicalIndicators.to_dataframe(candles)

        if len(df) < 50:
            return self._uncertain("Insufficient data")

        metrics = self._calculate_metrics(df)
        regime, confidence = self._classify_regime(metrics, df)

        return RegimeResult(
            regime=regime,
            confidence=round(confidence, 2),
            description=REGIME_DESCRIPTIONS[regime],
            active_strategies=REGIME_STRATEGY_MAP[regime],
            metrics=metrics,
        )

    def _calculate_metrics(self, df: pd.DataFrame) -> Dict:
        """Calculate all regime detection metrics."""
        high = df["high"]
        low = df["low"]
        close = df["close"]

        # ---- ADX (Average Directional Index) ----
        adx, plus_di, minus_di = self._adx(df, self.adx_period)

        # ---- ATR % (Volatility) ----
        atr = TechnicalIndicators.atr(df, 14)
        current_price = close.iloc[-1]
        atr_percent = (atr / current_price) * 100 if current_price > 0 else 0

        # ---- Bollinger Band Width ----
        bb = TechnicalIndicators.bollinger_bands(df)
        bb_width = bb.bandwidth * 100  # as percentage

        # ---- EMA Slope ----
        ema_20 = close.ewm(span=20, adjust=False).mean()
        ema_slope = ((ema_20.iloc[-1] - ema_20.iloc[-5]) / ema_20.iloc[-5] * 100) if ema_20.iloc[-5] > 0 else 0

        ema_50 = TechnicalIndicators.ema(df, 50)
        ema_200 = TechnicalIndicators.ema(df, 200)

        # ---- Price Structure (Higher Highs / Lower Lows) ----
        recent_highs = high.tail(20).values
        recent_lows = low.tail(20).values
        hh_count = sum(recent_highs[i] > recent_highs[i-1] for i in range(1, len(recent_highs)))
        ll_count = sum(recent_lows[i] < recent_lows[i-1] for i in range(1, len(recent_lows)))
        hl_count = sum(recent_lows[i] > recent_lows[i-1] for i in range(1, len(recent_lows)))

        # ---- Historical Volatility ----
        returns = close.pct_change().dropna()
        hist_vol = returns.tail(20).std() * np.sqrt(252) * 100  # Annualized %

        return {
            "adx": round(adx, 2),
            "plus_di": round(plus_di, 2),
            "minus_di": round(minus_di, 2),
            "atr_percent": round(atr_percent, 3),
            "bb_width": round(bb_width, 3),
            "ema_slope": round(ema_slope, 4),
            "ema_20": round(ema_20.iloc[-1], 4),
            "ema_50": round(ema_50, 4),
            "ema_200": round(ema_200, 4),
            "current_price": round(current_price, 4),
            "hh_count": hh_count,
            "ll_count": ll_count,
            "hl_count": hl_count,
            "hist_vol": round(hist_vol, 2),
        }

    def _classify_regime(self, m: Dict, df: pd.DataFrame) -> tuple:
        """Classify regime based on metrics."""
        adx = m["adx"]
        atr_pct = m["atr_percent"]
        ema_slope = m["ema_slope"]
        plus_di = m["plus_di"]
        minus_di = m["minus_di"]
        price = m["current_price"]
        ema_50 = m["ema_50"]
        ema_200 = m["ema_200"]

        # ── HIGH VOLATILITY (override everything) ──
        if atr_pct > self.vol_high:
            return MarketRegime.HIGH_VOLATILITY, 0.9

        # ── STRONG TREND ──
        if adx >= self.adx_trend_threshold:
            if plus_di > minus_di and ema_slope > 0.1 and price > ema_50:
                confidence = min((adx - self.adx_trend_threshold) / self.adx_strong_trend + 0.6, 0.95)
                return MarketRegime.TRENDING_UP, confidence

            if minus_di > plus_di and ema_slope < -0.1 and price < ema_50:
                confidence = min((adx - self.adx_trend_threshold) / self.adx_strong_trend + 0.6, 0.95)
                return MarketRegime.TRENDING_DOWN, confidence

        # ── RANGING ──
        if adx < self.adx_trend_threshold and atr_pct < self.vol_high:
            ranging_confidence = (self.adx_trend_threshold - adx) / self.adx_trend_threshold
            if ranging_confidence > 0.4:
                return MarketRegime.RANGING, round(0.5 + ranging_confidence * 0.4, 2)

        # ── LOW VOLATILITY ──
        if atr_pct < self.vol_low:
            return MarketRegime.LOW_VOLATILITY, 0.75

        return MarketRegime.UNCERTAIN, 0.4

    def _adx(self, df: pd.DataFrame, period: int = 14):
        """Calculate ADX, +DI, -DI."""
        high = df["high"]
        low = df["low"]
        close = df["close"]

        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = tr.ewm(alpha=1/period, adjust=False).mean()
        plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)
        minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
        adx = dx.ewm(alpha=1/period, adjust=False).mean()

        return adx.iloc[-1], plus_di.iloc[-1], minus_di.iloc[-1]

    def _uncertain(self, reason: str) -> RegimeResult:
        return RegimeResult(
            regime=MarketRegime.UNCERTAIN,
            confidence=0.0,
            description=reason,
            active_strategies=["dca"],
            metrics={}
        )
