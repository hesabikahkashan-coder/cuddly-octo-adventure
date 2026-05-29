"""
Multi-Timeframe Confirmation
Entry on lower timeframe only when higher timeframes confirm trend.
Significantly improves Win Rate by filtering low-quality setups.
"""
import asyncio
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from ..core.logging import get_logger
from ..strategies.technical_indicators import TechnicalIndicators

logger = get_logger(__name__)


class MTFBias(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass
class TimeframeBias:
    timeframe: str
    bias: MTFBias
    strength: float      # 0.0 to 1.0
    ema_alignment: bool  # EMA 9 > 21 > 200
    above_cloud: bool    # Price above Ichimoku cloud
    rsi: float
    trend_ema: float
    current_price: float


@dataclass
class MTFConfirmation:
    confirmed: bool
    direction: str               # long / short
    overall_bias: MTFBias
    confidence: float
    timeframe_biases: List[TimeframeBias]
    reason: str
    conflicting_timeframes: List[str]


class MultiTimeframeAnalyzer:
    """
    Multi-Timeframe Analysis Engine.

    Hierarchy: 1D > 4h > 1h > 15m > 5m

    Rules:
    - For LONG: 4h and 1h must be bullish before entering on 5m/15m
    - For SHORT: 4h and 1h must be bearish before entering on 5m/15m
    - If higher TFs conflict → no trade
    """

    TIMEFRAME_WEIGHTS = {
        "1d": 5,
        "4h": 4,
        "1h": 3,
        "15m": 2,
        "5m": 1,
    }

    def __init__(self, entry_timeframe: str = "5m", confirmation_timeframes: List[str] = None):
        self.entry_tf = entry_timeframe
        self.confirmation_tfs = confirmation_timeframes or ["1h", "4h"]

    def analyze(self, candles_by_tf: Dict[str, List[Dict]]) -> MTFConfirmation:
        """
        Analyze multiple timeframes and return confirmation result.

        Args:
            candles_by_tf: dict mapping timeframe string to candle list
                           e.g. {"5m": [...], "1h": [...], "4h": [...]}

        Returns:
            MTFConfirmation with go/no-go decision
        """
        biases: List[TimeframeBias] = []

        for tf, candles in candles_by_tf.items():
            if len(candles) < 50:
                continue
            bias = self._analyze_timeframe(tf, candles)
            biases.append(bias)

        if not biases:
            return MTFConfirmation(
                confirmed=False, direction="none", overall_bias=MTFBias.NEUTRAL,
                confidence=0.0, timeframe_biases=[], reason="No data",
                conflicting_timeframes=[]
            )

        return self._make_decision(biases)

    def _analyze_timeframe(self, timeframe: str, candles: List[Dict]) -> TimeframeBias:
        """Analyze a single timeframe."""
        df = TechnicalIndicators.to_dataframe(candles)
        current_price = df["close"].iloc[-1]

        rsi = TechnicalIndicators.rsi(df, 14)
        ema9 = TechnicalIndicators.ema(df, 9)
        ema21 = TechnicalIndicators.ema(df, 21)
        ema200 = TechnicalIndicators.ema(df, 200) if len(df) >= 200 else current_price
        macd = TechnicalIndicators.macd(df)
        ichimoku = TechnicalIndicators.ichimoku(df)

        # EMA alignment
        bullish_alignment = ema9 > ema21 and current_price > ema21
        bearish_alignment = ema9 < ema21 and current_price < ema21

        above_cloud = ichimoku.price_vs_cloud == "above"
        below_cloud = ichimoku.price_vs_cloud == "below"

        # Score
        bull_score = 0
        bear_score = 0

        if current_price > ema200: bull_score += 3
        else: bear_score += 3

        if bullish_alignment: bull_score += 2
        elif bearish_alignment: bear_score += 2

        if macd.trend == "bullish": bull_score += 2
        elif macd.trend == "bearish": bear_score += 2

        if above_cloud: bull_score += 2
        elif below_cloud: bear_score += 2

        if rsi.value > 50 and not rsi.is_overbought: bull_score += 1
        elif rsi.value < 50 and not rsi.is_oversold: bear_score += 1

        total = bull_score + bear_score
        if total == 0:
            bias = MTFBias.NEUTRAL
            strength = 0.0
        elif bull_score > bear_score:
            bias = MTFBias.BULLISH
            strength = bull_score / total
        elif bear_score > bull_score:
            bias = MTFBias.BEARISH
            strength = bear_score / total
        else:
            bias = MTFBias.NEUTRAL
            strength = 0.5

        return TimeframeBias(
            timeframe=timeframe,
            bias=bias,
            strength=round(strength, 2),
            ema_alignment=bullish_alignment or bearish_alignment,
            above_cloud=above_cloud,
            rsi=round(rsi.value, 1),
            trend_ema=round(ema200, 4),
            current_price=round(current_price, 4),
        )

    def _make_decision(self, biases: List[TimeframeBias]) -> MTFConfirmation:
        """Make final go/no-go decision based on all timeframe biases."""

        # Higher timeframes weighted more
        bull_weight = 0
        bear_weight = 0
        conflicting = []

        for bias in biases:
            weight = self.TIMEFRAME_WEIGHTS.get(bias.timeframe, 1)
            if bias.bias == MTFBias.BULLISH:
                bull_weight += weight * bias.strength
            elif bias.bias == MTFBias.BEARISH:
                bear_weight += weight * bias.strength

        # Check confirmation TFs specifically
        confirmation_biases = {b.timeframe: b for b in biases if b.timeframe in self.confirmation_tfs}
        all_bullish = all(b.bias == MTFBias.BULLISH for b in confirmation_biases.values())
        all_bearish = all(b.bias == MTFBias.BEARISH for b in confirmation_biases.values())

        conflicting = [b.timeframe for b in confirmation_biases.values() if
                       (all_bullish and b.bias != MTFBias.BULLISH) or
                       (all_bearish and b.bias != MTFBias.BEARISH)]

        total = bull_weight + bear_weight
        if total == 0:
            overall = MTFBias.NEUTRAL
            confidence = 0.0
        elif bull_weight > bear_weight:
            overall = MTFBias.BULLISH
            confidence = bull_weight / total
        else:
            overall = MTFBias.BEARISH
            confidence = bear_weight / total

        # Confirm only if higher TFs agree AND confidence is high enough
        confirmed = (
            (all_bullish or all_bearish) and
            confidence >= 0.6 and
            len(conflicting) == 0
        )

        direction = "long" if overall == MTFBias.BULLISH else "short" if overall == MTFBias.BEARISH else "none"

        reason_parts = []
        for b in sorted(biases, key=lambda x: self.TIMEFRAME_WEIGHTS.get(x.timeframe, 0), reverse=True):
            reason_parts.append(f"{b.timeframe}:{b.bias.value}({b.strength:.0%})")

        return MTFConfirmation(
            confirmed=confirmed,
            direction=direction,
            overall_bias=overall,
            confidence=round(confidence, 2),
            timeframe_biases=biases,
            reason=" | ".join(reason_parts),
            conflicting_timeframes=conflicting,
        )
