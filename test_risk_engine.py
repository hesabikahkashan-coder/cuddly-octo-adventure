"""
Risk Engine Unit Tests
Critical tests for the most important module.
"""
import pytest
import asyncio
from .engine import RiskEngine
from .models import TradeSignal, RiskStatus, RejectionReason


@pytest.fixture
def risk_engine():
    return RiskEngine(
        max_simultaneous_trades=5,
        max_daily_drawdown_percent=5.0,
        default_risk_per_trade_percent=1.0,
        min_risk_reward_ratio=1.5,
        max_position_size_percent=10.0,
    )


@pytest.fixture
def valid_long_signal():
    return TradeSignal(
        symbol="BTC/USDT",
        direction="long",
        exchange="binance",
        entry_price=50000.0,
        stop_loss=49000.0,  # $1000 risk
        take_profit_1=52000.0,  # $2000 reward = 2:1 RR
        risk_percent=1.0,
    )


class TestRiskEngine:

    @pytest.mark.asyncio
    async def test_valid_trade_approved(self, risk_engine, valid_long_signal):
        result = await risk_engine.validate_trade(
            signal=valid_long_signal,
            user_id="test_user",
            account_balance=10000.0,
            open_trade_count=0,
        )
        assert result.is_approved
        assert result.status == RiskStatus.APPROVED
        assert result.approved_quantity > 0
        assert result.approved_stop_loss == valid_long_signal.stop_loss

    @pytest.mark.asyncio
    async def test_no_stop_loss_rejected(self, risk_engine):
        signal = TradeSignal(
            symbol="BTC/USDT",
            direction="long",
            exchange="binance",
            entry_price=50000.0,
            stop_loss=None,  # NO STOP LOSS
        )
        result = await risk_engine.validate_trade(
            signal=signal,
            user_id="test_user",
            account_balance=10000.0,
            open_trade_count=0,
        )
        assert not result.is_approved
        assert RejectionReason.NO_STOP_LOSS in result.rejection_reasons

    @pytest.mark.asyncio
    async def test_wrong_direction_stop_loss_rejected(self, risk_engine):
        signal = TradeSignal(
            symbol="BTC/USDT",
            direction="long",
            exchange="binance",
            entry_price=50000.0,
            stop_loss=51000.0,  # SL above entry for long = INVALID
        )
        result = await risk_engine.validate_trade(
            signal=signal,
            user_id="test_user",
            account_balance=10000.0,
            open_trade_count=0,
        )
        assert not result.is_approved
        assert RejectionReason.INVALID_STOP_LOSS in result.rejection_reasons

    @pytest.mark.asyncio
    async def test_max_trades_exceeded(self, risk_engine, valid_long_signal):
        result = await risk_engine.validate_trade(
            signal=valid_long_signal,
            user_id="test_user",
            account_balance=10000.0,
            open_trade_count=5,  # At max
        )
        assert not result.is_approved
        assert RejectionReason.MAX_TRADES_REACHED in result.rejection_reasons

    @pytest.mark.asyncio
    async def test_poor_risk_reward_rejected(self, risk_engine):
        signal = TradeSignal(
            symbol="BTC/USDT",
            direction="long",
            exchange="binance",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit_1=50500.0,  # RR = 0.5:1 < 1.5 minimum
        )
        result = await risk_engine.validate_trade(
            signal=signal,
            user_id="test_user",
            account_balance=10000.0,
            open_trade_count=0,
        )
        assert not result.is_approved
        assert RejectionReason.POOR_RISK_REWARD in result.rejection_reasons

    @pytest.mark.asyncio
    async def test_trading_halted(self, risk_engine, valid_long_signal):
        await risk_engine.drawdown_guard._halt_trading("halted_user", "Test halt")
        result = await risk_engine.validate_trade(
            signal=valid_long_signal,
            user_id="halted_user",
            account_balance=10000.0,
            open_trade_count=0,
        )
        assert not result.is_approved
        assert result.status == RiskStatus.TRADING_HALTED

    @pytest.mark.asyncio
    async def test_position_sizing_correct(self, risk_engine, valid_long_signal):
        balance = 10000.0
        result = await risk_engine.validate_trade(
            signal=valid_long_signal,
            user_id="test_user",
            account_balance=balance,
            open_trade_count=0,
        )
        # 1% risk = $100, SL distance = $1000, qty = 100/1000 = 0.1 BTC
        assert result.is_approved
        assert abs(result.approved_quantity - 0.1) < 0.001
        assert abs(result.risk_amount_usd - 100.0) < 1.0
