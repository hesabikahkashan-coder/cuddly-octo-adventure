"""
Trend Following Strategy
Uses EMA crossovers, RSI confirmation, and Ichimoku for entries.
Multi-timeframe confluence required for high-confidence signals.
"""
from typing import List, Dict, Optional
from dataclasses import dataclass
from ..base_strategy import BaseStrategy, StrategySignal, SignalType, StrategyConfig
from ..technical_indicators import TechnicalIndicators
from ...core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TrendFollowingConfig(StrategyConfig):
    """Trend following specific parameters."""
    fast_ema: int = 9
    slow_ema: int = 21
    trend_ema: int = 200
    rsi_period: int = 14
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    atr_period: int = 14
    atr_multiplier_sl: float = 2.0
    atr_multiplier_tp: float = 4.0
    min_confidence: float = 0.65
    require_ichimoku: bool = True
    volume_confirmation: bool = True


class TrendFollowingStrategy(BaseStrategy):
    """
    Trend Following Strategy.
    
    Entry conditions (LONG):
    1. Price above 200 EMA (major trend)
    2. 9 EMA crosses above 21 EMA (golden cross)
    3. RSI between 40-65 (not overbought)
    4. Price above Ichimoku cloud
    5. Volume above average (confirmation)
    
    Entry conditions (SHORT):
    1. Price below 200 EMA (downtrend)
    2. 9 EMA crosses below 21 EMA (death cross)
    3. RSI between 35-60 (not oversold)
    4. Price below Ichimoku cloud
    5. Volume above average
    
    Stop Loss: 2x ATR below entry
    Take Profit 1: 2x Risk (1:2)
    Take Profit 2: 4x Risk (1:4)
    Take Profit 3: 6x Risk (1:6)
    """

    def __init__(self, config: Optional[TrendFollowingConfig] = None):
        if config is None:
            config = TrendFollowingConfig(
                name="Trend Following",
                symbols=["BTC/USDT", "ETH/USDT"],
                timeframe="4h"
            )
        super().__init__(config)
        self.tf_config: TrendFollowingConfig = config
        self.ta = TechnicalIndicators()

    def get_required_candles(self) -> int:
        return max(self.tf_config.trend_ema + 50, 300)

    async def analyze(self, symbol: str, candles: List[Dict]) -> StrategySignal:
        """
        Full multi-factor trend analysis.
        Returns signal only when multiple conditions align.
        """
        try:
            df = TechnicalIndicators.to_dataframe(candles)

            if len(df) < self.get_required_candles():
                return StrategySignal(
                    signal_type=SignalType.HOLD,
                    symbol=symbol,
                    timeframe=self.config.timeframe,
                    confidence=0.0,
                    reason="Insufficient data"
                )

            current_price = df["close"].iloc[-1]

            # ---- Calculate all indicators ----
            rsi = TechnicalIndicators.rsi(df, self.tf_config.rsi_period)
            macd = TechnicalIndicators.macd(df)
            bb = TechnicalIndicators.bollinger_bands(df)
            ema_fast = TechnicalIndicators.ema(df, self.tf_config.fast_ema)
            ema_slow = TechnicalIndicators.ema(df, self.tf_config.slow_ema)
            ema_trend = TechnicalIndicators.ema(df, self.tf_config.trend_ema)
            ema_cross = TechnicalIndicators.ema_cross_signal(df, self.tf_config.fast_ema, self.tf_config.slow_ema)
            atr = TechnicalIndicators.atr(df, self.tf_config.atr_period)
            volume_data = TechnicalIndicators.volume_analysis(df)
            ichimoku = TechnicalIndicators.ichimoku(df)
            sr = TechnicalIndicators.support_resistance(df)
            patterns = TechnicalIndicators.candlestick_patterns(df)

            indicators = {
                "rsi": rsi.value,
                "macd": macd.macd,
                "macd_signal": macd.signal,
                "macd_histogram": macd.histogram,
                "ema_fast": ema_fast,
                "ema_slow": ema_slow,
                "ema_trend": ema_trend,
                "ema_cross": ema_cross,
                "atr": atr,
                "volume_ratio": volume_data["volume_ratio"],
                "ichimoku_cloud": ichimoku.price_vs_cloud,
                "bb_position": bb.price_position,
                "patterns": patterns,
            }

            # ============================================================
            # LONG SIGNAL ANALYSIS
            # ============================================================
            long_score = 0
            long_reasons = []

            if current_price > ema_trend:
                long_score += 3
                long_reasons.append("Price above 200 EMA")

            if ema_cross == "golden_cross":
                long_score += 3
                long_reasons.append("EMA golden cross")
            elif ema_fast > ema_slow:
                long_score += 1
                long_reasons.append("Bullish EMA alignment")

            if not rsi.is_overbought and rsi.value > 40:
                long_score += 2
                long_reasons.append(f"RSI neutral-bullish: {rsi.value:.1f}")
            elif rsi.is_oversold:
                long_score += 1
                long_reasons.append(f"RSI oversold recovery: {rsi.value:.1f}")

            if ichimoku.price_vs_cloud == "above":
                long_score += 2
                long_reasons.append("Price above Ichimoku cloud")
            if ichimoku.tk_cross == "bullish":
                long_score += 2
                long_reasons.append("Ichimoku TK bullish cross")

            if macd.trend == "bullish" or macd.crossover == "golden_cross":
                long_score += 2
                long_reasons.append("MACD bullish")

            if volume_data["is_high_volume"] and volume_data["obv_trend"] == "bullish":
                long_score += 1
                long_reasons.append("High volume + bullish OBV")

            if patterns.get("hammer") or patterns.get("morning_star") or patterns.get("bullish_engulfing"):
                long_score += 1
                long_reasons.append("Bullish candlestick pattern")

            # ============================================================
            # SHORT SIGNAL ANALYSIS
            # ============================================================
            short_score = 0
            short_reasons = []

            if current_price < ema_trend:
                short_score += 3
                short_reasons.append("Price below 200 EMA")

            if ema_cross == "death_cross":
                short_score += 3
                short_reasons.append("EMA death cross")
            elif ema_fast < ema_slow:
                short_score += 1
                short_reasons.append("Bearish EMA alignment")

            if not rsi.is_oversold and rsi.value < 60:
                short_score += 2
                short_reasons.append(f"RSI neutral-bearish: {rsi.value:.1f}")

            if ichimoku.price_vs_cloud == "below":
                short_score += 2
                short_reasons.append("Price below Ichimoku cloud")
            if ichimoku.tk_cross == "bearish":
                short_score += 2
                short_reasons.append("Ichimoku TK bearish cross")

            if macd.trend == "bearish" or macd.crossover == "death_cross":
                short_score += 2
                short_reasons.append("MACD bearish")

            if volume_data["is_high_volume"] and volume_data["obv_trend"] == "bearish":
                short_score += 1
                short_reasons.append("High volume + bearish OBV")

            if patterns.get("shooting_star") or patterns.get("bearish_engulfing"):
                short_score += 1
                short_reasons.append("Bearish candlestick pattern")

            # ============================================================
            # DECISION
            # ============================================================
            max_score = 16  # Maximum possible score
            long_confidence = long_score / max_score
            short_confidence = short_score / max_score

            min_conf = self.tf_config.min_confidence

            if long_confidence >= min_conf and long_confidence > short_confidence:
                stop_loss = current_price - (atr * self.tf_config.atr_multiplier_sl)
                risk = current_price - stop_loss

                return StrategySignal(
                    signal_type=SignalType.BUY,
                    symbol=symbol,
                    timeframe=self.config.timeframe,
                    confidence=round(long_confidence, 2),
                    entry_price=current_price,
                    stop_loss=round(stop_loss, 6),
                    take_profit_1=round(current_price + risk * 2, 6),
                    take_profit_2=round(current_price + risk * 4, 6),
                    take_profit_3=round(current_price + risk * 6, 6),
                    reason=" | ".join(long_reasons),
                    indicators=indicators,
                )

            elif short_confidence >= min_conf and short_confidence > long_confidence:
                stop_loss = current_price + (atr * self.tf_config.atr_multiplier_sl)
                risk = stop_loss - current_price

                return StrategySignal(
                    signal_type=SignalType.SELL,
                    symbol=symbol,
                    timeframe=self.config.timeframe,
                    confidence=round(short_confidence, 2),
                    entry_price=current_price,
                    stop_loss=round(stop_loss, 6),
                    take_profit_1=round(current_price - risk * 2, 6),
                    take_profit_2=round(current_price - risk * 4, 6),
                    take_profit_3=round(current_price - risk * 6, 6),
                    reason=" | ".join(short_reasons),
                    indicators=indicators,
                )

            return StrategySignal(
                signal_type=SignalType.HOLD,
                symbol=symbol,
                timeframe=self.config.timeframe,
                confidence=max(long_confidence, short_confidence),
                reason=f"No clear signal (long: {long_confidence:.0%}, short: {short_confidence:.0%})",
                indicators=indicators,
            )

        except Exception as e:
            logger.error(f"Trend following analysis error for {symbol}: {e}", exc_info=True)
            return StrategySignal(
                signal_type=SignalType.HOLD,
                symbol=symbol,
                timeframe=self.config.timeframe,
                confidence=0.0,
                reason=f"Analysis error: {str(e)}"
            )
