"""Monte Carlo on the FIRE projection: how often the plan holds.

The deterministic projection assumes the expected return every month. Real
markets do not oblige, and the order of good and bad years matters most just
after the wage stops. This runs the same projection through a few hundred
random paths of return and inflation and counts how many survive.

Every retirement date is tried against the *same* paths. With common random
numbers a later date can never look worse than an earlier one through luck
of the draw, so the success curve is monotone and the earliest date at a
given rate is well defined.

For each path the earliest surviving retirement month is found by bisection.
That one number per path answers both questions at once: the success rate at
month m is the share of paths whose earliest month is at or before m, and the
earliest month at rate r is the r-quantile of those months.

Months are drawn independently. Multi-year crashes and persistent inflation
are therefore milder here than in history; the volatility settings are the
lever for being more pessimistic.
"""
from __future__ import annotations

import math
import multiprocessing
import os
import random
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from .fire_engine import (
    MONTHS_PER_YEAR,
    FireInputs,
    add_months,
    age_on,
    project,
)

RUNS = 400
SEED = 20261115
# Results are kept per input set; the same page is reloaded far more often
# than the ledger or the settings change
_CACHE_SIZE = 16


class RandomReturns:
    """One random path of monthly return and inflation, drawn up front.

    Nominal growth is lognormal with the expected annual return as its mean
    and the return volatility as its annual standard deviation. Inflation is
    normal around its expectation. Real return is the one deflated by the
    other, the way the deterministic model does it.
    """

    def __init__(
        self,
        months: int,
        nominal: float,
        inflation: float,
        return_volatility: float,
        inflation_volatility: float,
        seed: int,
    ):
        rng = random.Random(seed)
        sigma_annual = math.sqrt(math.log(1.0 + (return_volatility / (1.0 + nominal)) ** 2))
        sigma = sigma_annual / math.sqrt(MONTHS_PER_YEAR)
        mu = math.log(1.0 + nominal) / MONTHS_PER_YEAR - sigma * sigma / 2.0
        infl_mean = (1.0 + inflation) ** (1.0 / MONTHS_PER_YEAR) - 1.0
        infl_sd = inflation_volatility / math.sqrt(MONTHS_PER_YEAR)

        self._real: list[float] = []
        self._inflation: list[float] = []
        for _ in range(months):
            growth = math.exp(rng.gauss(mu, sigma))
            infl = infl_mean + rng.gauss(0.0, infl_sd)
            self._inflation.append(infl)
            self._real.append(growth / (1.0 + infl) - 1.0)

    def monthly_real_return(self, month: int) -> float:
        return self._real[month]

    def monthly_inflation(self, month: int) -> float:
        return self._inflation[month]


@dataclass
class FanPoint:
    year: int
    age: int
    p10: float
    p50: float
    p90: float


@dataclass
class CurvePoint:
    year: int
    age: int
    success_percent: float


@dataclass
class MonteCarloResult:
    runs: int
    target_percent: float
    # Earliest retirement at which at least target_percent of paths hold
    earliest_date: Optional[date]
    earliest_age: Optional[int]
    # The date asked about, or earliest_date when none was
    chosen_date: Optional[date]
    chosen_success_percent: Optional[float]
    curve: list = field(default_factory=list)
    fan: list = field(default_factory=list)


def _path(inputs: FireInputs, vols: tuple[float, float], k: int) -> RandomReturns:
    # One seed per path, so a worker can rebuild any path from its number
    return RandomReturns(
        inputs.horizon_months, inputs.nominal_return, inputs.inflation,
        vols[0], vols[1], SEED + k,
    )


def _earliest_batch(inputs: FireInputs, vols: tuple[float, float], ks: list[int], latest: int):
    return [_earliest_month(inputs, _path(inputs, vols, k), latest) for k in ks]


def _holdings_batch(inputs: FireInputs, vols: tuple[float, float], ks: list[int], month: int):
    return [
        [(row.year, row.age, row.available + row.locked)
         for row in project(inputs, _path(inputs, vols, k), month).rows]
        for k in ks
    ]


# A few thousand projections take tens of seconds on one core. The pool is
# started once, from a clean forkserver rather than a fork of the threaded
# web server, and kept for later requests.
_pool: Optional[ProcessPoolExecutor] = None


def _map(fn, inputs: FireInputs, vols: tuple[float, float], arg: int) -> list:
    global _pool
    workers = max(1, os.cpu_count() or 1)
    if _pool is None:
        _pool = ProcessPoolExecutor(
            max_workers=workers,
            mp_context=multiprocessing.get_context("forkserver"),
        )
    chunks = [list(range(RUNS))[w::workers] for w in range(workers)]
    results = list(_pool.map(fn, *zip(*[(inputs, vols, c, arg) for c in chunks])))
    # Put the paths back in order: chunk w holds paths w, w+workers, ...
    out: list = [None] * RUNS
    for w, chunk in enumerate(chunks):
        for k, value in zip(chunk, results[w]):
            out[k] = value
    return out


def _earliest_month(inputs: FireInputs, path: RandomReturns, latest: int) -> Optional[int]:
    """First retirement month this path survives, None if not even `latest`."""
    def holds(month: int) -> bool:
        return project(inputs, path, month, stop_when_depleted=True).success

    if not holds(latest):
        return None
    low, high = 0, latest
    while low < high:
        mid = (low + high) // 2
        if holds(mid):
            high = mid
        else:
            low = mid + 1
    return low


def _percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    k = (len(ordered) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


_cache: dict = {}


def simulate(
    inputs: FireInputs,
    return_volatility: float,
    inflation_volatility: float,
    target_percent: float,
    latest_age: int,
    chosen: Optional[date] = None,
) -> MonteCarloResult:
    vols = (return_volatility, inflation_volatility)
    key = (repr(inputs), vols, latest_age)
    cached = _cache.get(key)
    if cached is None:
        latest = min(
            inputs.horizon_months,
            max(0, (latest_age - age_on(inputs.birth_date, inputs.start)) * MONTHS_PER_YEAR),
        )
        earliest = _map(_earliest_batch, inputs, vols, latest)
        cached = (earliest, latest)
        if len(_cache) >= _CACHE_SIZE:
            _cache.pop(next(iter(_cache)))
        _cache[key] = cached
    earliest, latest = cached

    def rate_at(month: int) -> float:
        held = sum(1 for e in earliest if e is not None and e <= month)
        return 100.0 * held / len(earliest)

    # The earliest month at the target rate is that quantile of the
    # per-path earliest months; paths that never hold sort last
    needed = math.ceil(len(earliest) * target_percent / 100.0)
    ordered = sorted(e for e in earliest if e is not None)
    earliest_month = ordered[needed - 1] if 0 < needed <= len(ordered) else None
    earliest_date = add_months(inputs.start, earliest_month) if earliest_month is not None else None

    curve = []
    year = inputs.start.year
    while True:
        when = date(year, 1, 1) if year > inputs.start.year else inputs.start
        month = (when.year - inputs.start.year) * MONTHS_PER_YEAR + (when.month - inputs.start.month)
        if month > latest:
            break
        curve.append(CurvePoint(
            year=year, age=age_on(inputs.birth_date, when),
            success_percent=rate_at(month),
        ))
        year += 1

    chosen_date = chosen or earliest_date
    chosen_rate = None
    fan: list[FanPoint] = []
    if chosen_date is not None:
        month = max(0, (chosen_date.year - inputs.start.year) * MONTHS_PER_YEAR
                    + (chosen_date.month - inputs.start.month))
        chosen_rate = rate_at(month)
        by_year: dict[int, list[float]] = {}
        ages: dict[int, int] = {}
        for rows in _map(_holdings_batch, inputs, vols, month):
            for year, age, held in rows:
                by_year.setdefault(year, []).append(held)
                ages[year] = age
        fan = [
            FanPoint(
                year=y, age=ages[y],
                p10=_percentile(v, 0.10), p50=_percentile(v, 0.50), p90=_percentile(v, 0.90),
            )
            for y, v in sorted(by_year.items())
        ]

    return MonteCarloResult(
        runs=RUNS,
        target_percent=target_percent,
        earliest_date=earliest_date,
        earliest_age=age_on(inputs.birth_date, earliest_date) if earliest_date else None,
        chosen_date=chosen_date,
        chosen_success_percent=chosen_rate,
        curve=curve,
        fan=fan,
    )
