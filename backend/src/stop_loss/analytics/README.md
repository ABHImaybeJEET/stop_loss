# Analytics Engine (Checkpoint 3)

## Purpose & Scope
This module powers quantitative portfolio risk calculations, volatility indicators, and financial impact estimations:
- **Value at Risk (VaR)** & **Conditional VaR (CVaR)**: Parametric and historical simulation methods.
- **Scenario Stress Testing**: Simulating supply-shock curves, hurricane landfall severity, and energy commodity price surges.
- **Correlation & Beta Modeling**: Calculating dynamic covariance matrices across tracked equities and commodity futures.
- **Hedging Math**: Ratio estimation for options overlays, index hedges, and futures offsets.

## Planned Interfaces
- `RiskCalculator`: Computes portfolio drawdowns and stress scenarios.
- `CorrelationEngine`: Maintains rolling correlation metrics between environmental signals and equity returns.
