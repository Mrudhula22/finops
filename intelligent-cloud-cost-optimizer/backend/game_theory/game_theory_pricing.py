"""
Cross-Cloud Economic Game Theory — Multi-Cloud Arbitrage as a Strategic Game
============================================================================
Models cloud pricing as a REPEATED GAME where:
  - Players     : AWS, Azure, GCP (providers) + Tenants (us + others)
  - Actions     : Price adjustments, spot market bids, discount offers
  - Information : Aggregate demand signals, historical price moves
  - Payoffs     : Provider = revenue maximisation | Tenant = cost minimisation

Key insight: Your own migration decisions shift aggregate demand, which
triggers provider repricing. Naive comparison ignores this feedback loop.

Game-theoretic approach:
  1. Model provider pricing as a Bertrand competition with switching costs
  2. Estimate Nash Equilibrium prices under current demand
  3. Simulate how YOUR action shifts demand → triggers price response
  4. Choose action that minimises cost over the HORIZON, not just today
"""

import logging
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class ProviderPriceState:
    provider: str
    current_price: float          # INR/unit/month
    base_price: float             # cost floor (provider's marginal cost proxy)
    market_share: float           # 0-1
    switching_cost: float         # INR — how much it costs tenant to switch away
    demand_elasticity: float      # how sensitive price is to demand shift
    spot_discount: float          # current spot/preemptible discount %
    committed_discount: float     # 1yr reserved discount %
    egress_cost_per_gb: float     # INR/GB — often hidden cost
    price_history: List[float] = field(default_factory=list)


@dataclass
class GameEquilibrium:
    provider: str
    equilibrium_price: float
    predicted_price_30d: float
    predicted_price_90d: float
    price_stability: str          # stable | volatile | falling | rising
    arbitrage_window: bool        # True if price likely to rise after your move
    confidence: float


@dataclass
class ArbitrageOpportunity:
    from_provider: str
    to_provider: str
    current_saving_pct: float
    game_adjusted_saving_pct: float   # after modelling price response
    naive_monthly_saving: float       # what static comparison shows
    game_adjusted_monthly_saving: float  # realistic saving after repricing
    horizon_months: int
    total_horizon_saving: float
    risk_of_repricing: str            # low | medium | high
    recommendation: str
    game_theory_explanation: str


@dataclass
class TenantInfluenceModel:
    """How much a single tenant's action moves aggregate demand."""
    tenant_workload_pct_of_market: float   # our share of provider's demand
    demand_shift_on_migration: float       # % change in provider demand if we leave
    expected_price_response_pct: float     # how much provider reprices in response
    other_tenants_copycat_probability: float  # probability others follow our move


# ── Provider pricing models ────────────────────────────────────────────────────

# Realistic 2024 INR pricing for equivalent 4vCPU 16GB workload
PROVIDER_STATES: Dict[str, ProviderPriceState] = {
    "aws": ProviderPriceState(
        provider="aws",
        current_price=20318,
        base_price=14000,
        market_share=0.32,
        switching_cost=8000,
        demand_elasticity=0.15,
        spot_discount=0.68,
        committed_discount=0.35,
        egress_cost_per_gb=7.0,
        price_history=[21000, 20800, 20500, 20400, 20318],
    ),
    "azure": ProviderPriceState(
        provider="azure",
        current_price=17940,
        base_price=13000,
        market_share=0.22,
        switching_cost=7500,
        demand_elasticity=0.18,
        spot_discount=0.70,
        committed_discount=0.38,
        egress_cost_per_gb=7.5,
        price_history=[18500, 18300, 18100, 18000, 17940],
    ),
    "gcp": ProviderPriceState(
        provider="gcp",
        current_price=15769,
        base_price=11000,
        market_share=0.11,
        switching_cost=6500,
        demand_elasticity=0.22,
        spot_discount=0.72,
        committed_discount=0.40,
        egress_cost_per_gb=8.0,
        price_history=[16200, 16000, 15900, 15800, 15769],
    ),
}


class GameTheoryPricingEngine:
    """
    Models multi-cloud pricing as a repeated Bertrand competition.
    Computes game-theoretic arbitrage opportunities beyond naive comparison.
    """

    def __init__(self):
        self.states = {k: v for k, v in PROVIDER_STATES.items()}
        self._rng = random.Random(42)

    # ── Public API ─────────────────────────────────────────────────────────────

    def compute_nash_equilibrium(self) -> Dict[str, GameEquilibrium]:
        """
        Compute Nash Equilibrium prices for all providers.
        In Bertrand competition with switching costs, equilibrium price > marginal cost.
        Equilibrium condition: p_i* = c_i + switching_cost * (1 - share_j) / elasticity
        """
        equilibria = {}
        for prov, state in self.states.items():
            competitors = [s for k, s in self.states.items() if k != prov]
            avg_competitor_price = np.mean([c.current_price for c in competitors])

            # Nash equilibrium price formula (Bertrand with differentiation)
            eq_price = (
                state.base_price
                + state.switching_cost * (1 - state.market_share)
                + (avg_competitor_price - state.base_price) * state.demand_elasticity
            )
            eq_price = max(state.base_price, min(eq_price, state.current_price * 1.15))

            # Predict 30/90 day prices using trend + reversion to equilibrium
            trend_30 = self._price_trend(state.price_history, 30)
            trend_90 = self._price_trend(state.price_history, 90)
            pred_30  = state.current_price + trend_30 + (eq_price - state.current_price) * 0.3
            pred_90  = state.current_price + trend_90 + (eq_price - state.current_price) * 0.6

            stability = self._classify_stability(state.price_history)
            arb_window = pred_30 > state.current_price * 1.05

            equilibria[prov] = GameEquilibrium(
                provider=prov,
                equilibrium_price=round(eq_price, 2),
                predicted_price_30d=round(pred_30, 2),
                predicted_price_90d=round(pred_90, 2),
                price_stability=stability,
                arbitrage_window=arb_window,
                confidence=round(self._compute_confidence(state), 3),
            )

        logger.info("Nash equilibria computed: %s",
                    {k: round(v.equilibrium_price) for k, v in equilibria.items()})
        return equilibria

    def model_tenant_influence(
        self,
        tenant_monthly_spend: float,
        total_market_size: float = 50_000_000_000,  # INR — proxy for AWS India market
    ) -> TenantInfluenceModel:
        """
        Estimate how much this tenant's migration decision shifts aggregate demand
        and triggers provider repricing.
        """
        share = min(tenant_monthly_spend / max(total_market_size, 1), 0.01)
        demand_shift = share * 100  # % change in demand if tenant migrates
        # Providers reprice proportionally to demand shift, scaled by elasticity
        avg_elasticity = np.mean([s.demand_elasticity for s in self.states.values()])
        price_response = demand_shift * avg_elasticity
        # Large tenants trigger copycat behaviour (others follow the cheaper provider)
        copycat_prob = min(share * 500, 0.30)

        return TenantInfluenceModel(
            tenant_workload_pct_of_market=round(share * 100, 4),
            demand_shift_on_migration=round(demand_shift, 4),
            expected_price_response_pct=round(price_response, 4),
            other_tenants_copycat_probability=round(copycat_prob, 4),
        )

    def compute_arbitrage(
        self,
        from_provider: str,
        to_provider: str,
        monthly_spend: float,
        horizon_months: int = 12,
    ) -> ArbitrageOpportunity:
        """
        Compare naive saving vs game-adjusted saving after modelling
        how migration shifts demand and triggers repricing.
        """
        src = self.states.get(from_provider)
        dst = self.states.get(to_provider)
        if not src or not dst:
            raise ValueError(f"Unknown provider: {from_provider} or {to_provider}")

        equilibria  = self.compute_nash_equilibrium()
        influence   = self.model_tenant_influence(monthly_spend)
        dst_eq      = equilibria[to_provider]

        # Naive saving (static price comparison)
        naive_saving_pct = (src.current_price - dst.current_price) / src.current_price * 100
        naive_monthly    = monthly_spend * (naive_saving_pct / 100)

        # Game-adjusted: destination price will RISE after demand influx
        # Factor 1: direct repricing from our migration
        price_rise_factor = influence.expected_price_response_pct / 100
        # Factor 2: if others follow (copycat), destination demand rises more
        copycat_amplifier = 1 + influence.other_tenants_copycat_probability * 0.5
        # Factor 3: equilibrium reversion
        eq_reversion = (dst_eq.equilibrium_price - dst.current_price) / dst.current_price

        adjusted_dst_price = dst.current_price * (
            1 + price_rise_factor * copycat_amplifier + eq_reversion * 0.4
        )
        game_saving_pct    = (src.current_price - adjusted_dst_price) / src.current_price * 100
        game_saving_pct    = max(0, game_saving_pct)  # can't be negative saving shown
        game_monthly       = monthly_spend * (game_saving_pct / 100)

        # Horizon total (accounts for 90d price trajectory)
        horizon_saving = 0.0
        for month in range(horizon_months):
            decay = 1.0 - (month / horizon_months) * (naive_saving_pct - game_saving_pct) / 100
            horizon_saving += game_monthly * max(0.5, decay)

        # Repricing risk
        if price_rise_factor > 0.02:
            repricing_risk = "high"
        elif price_rise_factor > 0.005:
            repricing_risk = "medium"
        else:
            repricing_risk = "low"

        explanation = (
            f"Naive comparison shows {naive_saving_pct:.1f}% saving by moving from "
            f"{from_provider.upper()} to {to_provider.upper()}. "
            f"However, game-theoretic modelling predicts that this migration will shift "
            f"~{influence.demand_shift_on_migration:.4f}% of market demand to "
            f"{to_provider.upper()}, triggering a price increase of "
            f"~{price_rise_factor*100:.2f}%. "
            f"With a {influence.other_tenants_copycat_probability*100:.0f}% probability "
            f"that other tenants copy this move (amplifying demand), the realistic "
            f"saving reduces to {game_saving_pct:.1f}%. "
            f"Equilibrium price for {to_provider.upper()} is estimated at "
            f"₹{dst_eq.equilibrium_price:,.0f}, currently at ₹{dst.current_price:,.0f}."
        )

        return ArbitrageOpportunity(
            from_provider=from_provider,
            to_provider=to_provider,
            current_saving_pct=round(naive_saving_pct, 2),
            game_adjusted_saving_pct=round(game_saving_pct, 2),
            naive_monthly_saving=round(naive_monthly, 2),
            game_adjusted_monthly_saving=round(game_monthly, 2),
            horizon_months=horizon_months,
            total_horizon_saving=round(horizon_saving, 2),
            risk_of_repricing=repricing_risk,
            recommendation=(
                f"Proceed — game-adjusted saving is still {game_saving_pct:.1f}%"
                if game_saving_pct > 10
                else f"Caution — after repricing, saving drops to {game_saving_pct:.1f}%"
            ),
            game_theory_explanation=explanation,
        )

    def best_provider_game_theoretic(
        self,
        current_provider: str,
        monthly_spend: float,
        horizon_months: int = 12,
    ) -> Dict[str, Any]:
        """
        Find the best provider considering game-theoretic price dynamics,
        not just current prices.
        """
        equilibria = self.compute_nash_equilibrium()
        opportunities = []
        for prov in ["aws", "azure", "gcp"]:
            if prov == current_provider:
                continue
            arb = self.compute_arbitrage(current_provider, prov, monthly_spend, horizon_months)
            opportunities.append(arb)

        if not opportunities:
            return {"recommendation": "Stay on current provider"}

        best = max(opportunities, key=lambda o: o.game_adjusted_monthly_saving)

        return {
            "current_provider":         current_provider,
            "recommended_provider":     best.to_provider,
            "naive_monthly_saving":     best.naive_monthly_saving,
            "game_adjusted_saving":     best.game_adjusted_monthly_saving,
            "total_horizon_saving":     best.total_horizon_saving,
            "repricing_risk":           best.risk_of_repricing,
            "recommendation":           best.recommendation,
            "game_theory_explanation":  best.game_theory_explanation,
            "all_opportunities": [
                {
                    "to": o.to_provider,
                    "naive_saving_pct":          o.current_saving_pct,
                    "game_adjusted_saving_pct":  o.game_adjusted_saving_pct,
                    "naive_monthly":             o.naive_monthly_saving,
                    "game_adjusted_monthly":     o.game_adjusted_monthly_saving,
                    "repricing_risk":            o.risk_of_repricing,
                }
                for o in opportunities
            ],
            "nash_equilibria": {
                k: {
                    "current_price":      self.states[k].current_price,
                    "equilibrium_price":  v.equilibrium_price,
                    "predicted_30d":      v.predicted_price_30d,
                    "predicted_90d":      v.predicted_price_90d,
                    "stability":          v.price_stability,
                }
                for k, v in equilibria.items()
            },
        }

    # ── Internals ──────────────────────────────────────────────────────────────

    @staticmethod
    def _price_trend(history: List[float], days: int) -> float:
        if len(history) < 2:
            return 0.0
        monthly_change = np.mean(np.diff(history))
        return monthly_change * (days / 30)

    @staticmethod
    def _classify_stability(history: List[float]) -> str:
        if len(history) < 3:
            return "unknown"
        changes = np.diff(history)
        avg_change = np.mean(changes)
        std_change = np.std(changes)
        if std_change / max(abs(avg_change), 1) > 2:
            return "volatile"
        if avg_change < -100:
            return "falling"
        if avg_change > 100:
            return "rising"
        return "stable"

    @staticmethod
    def _compute_confidence(state: ProviderPriceState) -> float:
        if len(state.price_history) < 3:
            return 0.6
        cv = np.std(state.price_history) / max(np.mean(state.price_history), 1)
        return max(0.5, min(0.95, 1.0 - cv * 10))
