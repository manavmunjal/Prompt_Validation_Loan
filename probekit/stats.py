"""Fisher's exact test and Holm's correction, in plain Python (no scipy needed)."""

from math import comb


def fisher_exact(a, b, c, d):
    """Two-sided p for the table [[a, b], [c, d]], as scipy.stats.fisher_exact: the sum over all tables with the same
    margins that are no more likely than the observed one."""
    r1, r2, c1 = a + b, c + d, a + c
    total = comb(r1 + r2, c1)
    pmf = [comb(r1, k) * comb(r2, c1 - k) / total for k in range(max(0, c1 - r2), min(r1, c1) + 1)]
    p0 = comb(r1, a) * comb(r2, c1 - a) / total
    return min(1.0, sum(p for p in pmf if p <= p0 * (1 + 1e-7)))


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run = [0.0] * len(ps), 0.0
    for k, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - k) * ps[i]))
        adj[i] = run
    return adj


def smallest_detectable_gap(n, alpha=0.05):
    """Smallest gap (points) from a zero baseline that reaches p < alpha with n runs in each arm."""
    for k in range(1, n + 1):
        if fisher_exact(0, n, k, n - k) < alpha:
            return round(100 * k / n)
    return None
