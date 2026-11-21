"""Lowest 7-day jump chance shown (model.py live section). Its own module so it can be tested without the store."""
import pandas as pd

FLOOR_UNDER, FLOOR_DAYS, FLOOR_MIN, FLOOR_CAP = 0.05, 730, 100, 0.12


def jump_floor(C, fuels):
    """Lowest jump chance to show, per fuel: how often a 5c+ jump actually followed, in the walk-forward
    (backtest_cls.parquet: date, fuel, y_jump7, p), on the days the classifier rated under 5%, over the last 730 days.
    The classifier rates many days near 0 that still see jumps (2025-26: 0.8% predicted, 7.2% actual), so the live
    figure is raised to this (max of the two, so a day rated 4% never shows more than one rated 6%). A fuel with under
    100 such days uses all fuels pooled. Capped at 0.12: at 0.12 the 14-day chance is 1 - 0.88^2 = 22.6%, under
    market()'s 25% rise-date line, and calls need 35%, so the floor changes the figure shown, never a call or a date."""
    C = C[C.date >= C.date.max() - pd.Timedelta(days=FLOOR_DAYS)]
    low = C[C.p < FLOOR_UNDER]
    pooled = float(low.y_jump7.mean()) if len(low) else 0.0
    out = {}
    for f in fuels:
        g = low[low.fuel == f]
        out[f] = round(min(float(g.y_jump7.mean()) if len(g) >= FLOOR_MIN else pooled, FLOOR_CAP), 3)
    return out
