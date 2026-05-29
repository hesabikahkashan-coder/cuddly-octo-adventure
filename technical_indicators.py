"""
Technical Indicators Library
Production-grade TA implementations using pandas-ta and numpy.
Supports: RSI, MACD, Bollinger Bands, EMA, SMA, ATR, Fibonacci,
          Ichimoku, Volume Analysis, Support/Resistance, Candlestick Patterns.
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from ..core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RSIResult:
    value: float
    is_overbought: bool  # > 70
    is_oversold: bool    # < 30
    signal: str          # overbought/oversold/neutral


@dataclass
class MACDResult:
    macd: float
    signal: float
    histogram: float
    trend: str  # bullish/bearish/neutral
    crossover: Optional[str]  # golden_cross/death_cross/None


@dataclass
class BollingerBandsResult:
    upper: float
    middle: float
    lower: float
    bandwidth: float
    percent_b: float
    is_squeezed: bool
    price_position: str  # above_upper/below_lower/inside


@dataclass
class IchimokuResult:
    tenkan_sen: float
    kijun_sen: float
    senkou_span_a: float
    senkou_span_b: float
    chikou_span: float
    cloud_color: str  # green/red
    price_vs_cloud: str  # above/inside/below
    tk_cross: Optional[str]  # bullish/bearish/None


@dataclass
class SupportResistanceResult:
    supports: List[float]
    resistances: List[float]
    nearest_support: Optional[float]
    nearest_resistance: Optional[float]
    strength_map: Dict[float, int]


class TechnicalIndicators:
    """
    Production-grade technical analysis engine.
    All methods accept pandas DataFrame with OHLCV columns.
    """

    @staticmethod
    def to_dataframe(candles: List[Dict]) -> pd.DataFrame:
        """Convert candle list to pandas DataFrame."""
        df = pd.DataFrame(candles)
        required = ["open", "high", "low", "close", "volume"]
        for col in required:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df.dropna(subset=["close"])

    # ============================================================
    # RSI
    # ============================================================

    @staticmethod
    def rsi(df: pd.DataFrame, period: int = 14) -> RSIResult:
        """Calculate RSI using Wilder's smoothing method."""
        close = df["close"].values
        if len(close) < period + 1:
            return RSIResult(value=50.0, is_overbought=False, is_oversold=False, signal="neutral")

        deltas = np.diff(close)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            rsi_value = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi_value = 100 - (100 / (1 + rs))

        signal = "overbought" if rsi_value > 70 else "oversold" if rsi_value < 30 else "neutral"
        return RSIResult(
            value=round(rsi_value, 2),
            is_overbought=rsi_value > 70,
            is_oversold=rsi_value < 30,
            signal=signal
        )

    # ============================================================
    # MACD
    # ============================================================

    @staticmethod
    def macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> MACDResult:
        """Calculate MACD with signal line and histogram."""
        close = df["close"]

        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()

        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line

        current_macd = macd_line.iloc[-1]
        current_signal = signal_line.iloc[-1]
        current_hist = histogram.iloc[-1]
        prev_hist = histogram.iloc[-2] if len(histogram) > 1 else 0

        trend = "bullish" if current_macd > current_signal else "bearish"

        crossover = None
        if prev_hist < 0 and current_hist > 0:
            crossover = "golden_cross"
        elif prev_hist > 0 and current_hist < 0:
            crossover = "death_cross"

        return MACDResult(
            macd=round(current_macd, 6),
            signal=round(current_signal, 6),
            histogram=round(current_hist, 6),
            trend=trend,
            crossover=crossover
        )

    # ============================================================
    # Bollinger Bands
    # ============================================================

    @staticmethod
    def bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> BollingerBandsResult:
        """Calculate Bollinger Bands."""
        close = df["close"]
        middle = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()

        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)

        current_price = close.iloc[-1]
        current_upper = upper.iloc[-1]
        current_middle = middle.iloc[-1]
        current_lower = lower.iloc[-1]

        bandwidth = (current_upper - current_lower) / current_middle if current_middle > 0 else 0
        percent_b = (current_price - current_lower) / (current_upper - current_lower) if (current_upper - current_lower) > 0 else 0.5

        # Squeeze detection (bandwidth below 20-period average)
        avg_bandwidth = ((upper - lower) / middle).rolling(20).mean().iloc[-1]
        is_squeezed = bandwidth < avg_bandwidth * 0.8 if not pd.isna(avg_bandwidth) else False

        if current_price > current_upper:
            price_position = "above_upper"
        elif current_price < current_lower:
            price_position = "below_lower"
        else:
            price_position = "inside"

        return BollingerBandsResult(
            upper=round(current_upper, 6),
            middle=round(current_middle, 6),
            lower=round(current_lower, 6),
            bandwidth=round(bandwidth, 4),
            percent_b=round(percent_b, 4),
            is_squeezed=is_squeezed,
            price_position=price_position
        )

    # ============================================================
    # EMA / SMA
    # ============================================================

    @staticmethod
    def ema(df: pd.DataFrame, period: int) -> float:
        """Exponential Moving Average."""
        return round(df["close"].ewm(span=period, adjust=False).mean().iloc[-1], 6)

    @staticmethod
    def sma(df: pd.DataFrame, period: int) -> float:
        """Simple Moving Average."""
        return round(df["close"].rolling(window=period).mean().iloc[-1], 6)

    @staticmethod
    def ema_cross_signal(df: pd.DataFrame, fast: int = 9, slow: int = 21) -> str:
        """Detect EMA crossover."""
        ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
        ema_slow = df["close"].ewm(span=slow, adjust=False).mean()

        if ema_fast.iloc[-1] > ema_slow.iloc[-1] and ema_fast.iloc[-2] <= ema_slow.iloc[-2]:
            return "golden_cross"
        elif ema_fast.iloc[-1] < ema_slow.iloc[-1] and ema_fast.iloc[-2] >= ema_slow.iloc[-2]:
            return "death_cross"
        elif ema_fast.iloc[-1] > ema_slow.iloc[-1]:
            return "bullish"
        return "bearish"

    # ============================================================
    # ATR
    # ============================================================

    @staticmethod
    def atr(df: pd.DataFrame, period: int = 14) -> float:
        """Average True Range."""
        high = df["high"]
        low = df["low"]
        close = df["close"]

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return round(tr.ewm(span=period, adjust=False).mean().iloc[-1], 6)

    # ============================================================
    # Fibonacci Retracement
    # ============================================================

    @staticmethod
    def fibonacci_levels(df: pd.DataFrame, lookback: int = 50) -> Dict[str, float]:
        """Calculate Fibonacci retracement levels."""
        recent = df.tail(lookback)
        high = recent["high"].max()
        low = recent["low"].min()
        diff = high - low

        levels = {
            "0.0": round(low, 6),
            "0.236": round(low + diff * 0.236, 6),
            "0.382": round(low + diff * 0.382, 6),
            "0.5": round(low + diff * 0.5, 6),
            "0.618": round(low + diff * 0.618, 6),
            "0.786": round(low + diff * 0.786, 6),
            "1.0": round(high, 6),
            "1.618": round(high + diff * 0.618, 6),
        }
        return levels

    # ============================================================
    # Volume Analysis
    # ============================================================

    @staticmethod
    def volume_analysis(df: pd.DataFrame, period: int = 20) -> Dict[str, Any]:
        """Analyze volume for trends and anomalies."""
        volume = df["volume"]
        close = df["close"]

        avg_volume = volume.rolling(period).mean().iloc[-1]
        current_volume = volume.iloc[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

        # On-Balance Volume
        obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()
        obv_trend = "bullish" if obv.iloc[-1] > obv.iloc[-5] else "bearish"

        return {
            "current_volume": current_volume,
            "avg_volume": avg_volume,
            "volume_ratio": round(volume_ratio, 2),
            "is_high_volume": volume_ratio > 1.5,
            "obv": obv.iloc[-1],
            "obv_trend": obv_trend,
        }

    # ============================================================
    # Support & Resistance
    # ============================================================

    @staticmethod
    def support_resistance(df: pd.DataFrame, lookback: int = 100, window: int = 5) -> SupportResistanceResult:
        """Detect key support and resistance levels using pivot points."""
        if len(df) < lookback:
            lookback = len(df)

        recent = df.tail(lookback)
        highs = recent["high"].values
        lows = recent["low"].values
        closes = recent["close"].values
        current_price = closes[-1]

        pivots_high = []
        pivots_low = []

        for i in range(window, len(highs) - window):
            if all(highs[i] >= highs[i-j] for j in range(1, window+1)) and \
               all(highs[i] >= highs[i+j] for j in range(1, window+1)):
                pivots_high.append(highs[i])

            if all(lows[i] <= lows[i-j] for j in range(1, window+1)) and \
               all(lows[i] <= lows[i+j] for j in range(1, window+1)):
                pivots_low.append(lows[i])

        # Cluster levels
        def cluster_levels(levels, tolerance=0.002):
            if not levels:
                return []
            levels = sorted(set(levels))
            clustered = [levels[0]]
            for level in levels[1:]:
                if (level - clustered[-1]) / clustered[-1] > tolerance:
                    clustered.append(level)
            return clustered

        supports = cluster_levels(pivots_low)
        resistances = cluster_levels(pivots_high)

        nearest_support = max((s for s in supports if s < current_price), default=None)
        nearest_resistance = min((r for r in resistances if r > current_price), default=None)

        return SupportResistanceResult(
            supports=supports,
            resistances=resistances,
            nearest_support=nearest_support,
            nearest_resistance=nearest_resistance,
            strength_map={}
        )

    # ============================================================
    # Ichimoku Cloud
    # ============================================================

    @staticmethod
    def ichimoku(df: pd.DataFrame) -> IchimokuResult:
        """Calculate Ichimoku Cloud components."""
        high = df["high"]
        low = df["low"]
        close = df["close"]

        # Tenkan-sen (Conversion Line): (9-period high + 9-period low) / 2
        tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2

        # Kijun-sen (Base Line): (26-period high + 26-period low) / 2
        kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2

        # Senkou Span A: (Tenkan + Kijun) / 2, shifted 26 periods
        span_a = ((tenkan + kijun) / 2).shift(26)

        # Senkou Span B: (52-period high + 52-period low) / 2, shifted 26
        span_b = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)

        # Chikou Span: close shifted back 26 periods
        chikou = close.shift(-26)

        current_price = close.iloc[-1]
        current_span_a = span_a.iloc[-1] if not pd.isna(span_a.iloc[-1]) else 0
        current_span_b = span_b.iloc[-1] if not pd.isna(span_b.iloc[-1]) else 0

        cloud_color = "green" if current_span_a > current_span_b else "red"
        cloud_top = max(current_span_a, current_span_b)
        cloud_bottom = min(current_span_a, current_span_b)

        if current_price > cloud_top:
            price_vs_cloud = "above"
        elif current_price < cloud_bottom:
            price_vs_cloud = "below"
        else:
            price_vs_cloud = "inside"

        # TK Cross
        tk_cross = None
        if len(tenkan) > 1:
            if tenkan.iloc[-1] > kijun.iloc[-1] and tenkan.iloc[-2] <= kijun.iloc[-2]:
                tk_cross = "bullish"
            elif tenkan.iloc[-1] < kijun.iloc[-1] and tenkan.iloc[-2] >= kijun.iloc[-2]:
                tk_cross = "bearish"

        return IchimokuResult(
            tenkan_sen=round(tenkan.iloc[-1], 6),
            kijun_sen=round(kijun.iloc[-1], 6),
            senkou_span_a=round(current_span_a, 6),
            senkou_span_b=round(current_span_b, 6),
            chikou_span=round(chikou.iloc[-27] if len(chikou) > 27 else 0, 6),
            cloud_color=cloud_color,
            price_vs_cloud=price_vs_cloud,
            tk_cross=tk_cross
        )

    # ============================================================
    # Candlestick Patterns
    # ============================================================

    @staticmethod
    def candlestick_patterns(df: pd.DataFrame) -> Dict[str, bool]:
        """Detect common candlestick patterns."""
        if len(df) < 3:
            return {}

        o = df["open"].values
        h = df["high"].values
        l = df["low"].values
        c = df["close"].values

        patterns = {}

        # Doji
        body = abs(c[-1] - o[-1])
        total_range = h[-1] - l[-1]
        patterns["doji"] = total_range > 0 and (body / total_range) < 0.1

        # Hammer (bullish reversal)
        lower_shadow = min(o[-1], c[-1]) - l[-1]
        upper_shadow = h[-1] - max(o[-1], c[-1])
        patterns["hammer"] = (
            lower_shadow > 2 * body and
            upper_shadow < body and
            c[-1] > o[-1]
        )

        # Shooting Star (bearish reversal)
        patterns["shooting_star"] = (
            upper_shadow > 2 * body and
            lower_shadow < body and
            c[-1] < o[-1]
        )

        # Bullish Engulfing
        if len(df) >= 2:
            patterns["bullish_engulfing"] = (
                c[-2] < o[-2] and  # Previous candle bearish
                c[-1] > o[-1] and  # Current candle bullish
                o[-1] < c[-2] and  # Opens below previous close
                c[-1] > o[-2]      # Closes above previous open
            )
            # Bearish Engulfing
            patterns["bearish_engulfing"] = (
                c[-2] > o[-2] and
                c[-1] < o[-1] and
                o[-1] > c[-2] and
                c[-1] < o[-2]
            )

        # Morning Star (3-candle bullish)
        if len(df) >= 3:
            patterns["morning_star"] = (
                c[-3] < o[-3] and  # First: bearish
                abs(c[-2] - o[-2]) < 0.3 * (h[-2] - l[-2]) and  # Second: doji/small
                c[-1] > o[-1] and  # Third: bullish
                c[-1] > (o[-3] + c[-3]) / 2  # Closes above midpoint of first
            )

        return {k: bool(v) for k, v in patterns.items()}
