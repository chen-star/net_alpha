"""Guard: the wash-sale engine must always run over the full taxpayer trade
history.

A UI filter for the multi-account selector must never reach the engine —
cross-account wash sales (Rev. Rul. 2008-5 IRA traps in particular) would be
missed if the engine only saw a subset of the user's trades. The route layer
applies the filter on the *read* side; the engine itself remains unaware.
"""

from __future__ import annotations

import inspect

from net_alpha.engine import detector, recompute, washsale_watch


def _public_funcs(module):
    out = []
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if not callable(obj):
            continue
        if getattr(obj, "__module__", "") != module.__name__:
            continue
        out.append(obj)
    return out


def test_engine_detector_has_no_accounts_kwarg():
    """No function in net_alpha.engine.detector may accept an 'accounts' kwarg."""
    offenders = []
    for fn in _public_funcs(detector):
        sig = inspect.signature(fn)
        if "accounts" in sig.parameters:
            offenders.append(fn.__qualname__)
    assert not offenders, (
        f"Engine detector functions must not accept 'accounts' (would let UI filter "
        f"leak in and miss cross-account wash sales). Offenders: {offenders}"
    )


def test_engine_washsale_watch_has_no_accounts_kwarg():
    """No function in net_alpha.engine.washsale_watch may accept an 'accounts' kwarg.

    Note: ``evaluate_target`` does take a single ``account`` (per-target context,
    not a filter) — that's expected and allowed.
    """
    offenders = []
    for fn in _public_funcs(washsale_watch):
        sig = inspect.signature(fn)
        if "accounts" in sig.parameters:
            offenders.append(fn.__qualname__)
    assert not offenders, f"Engine washsale_watch functions must not accept 'accounts'. Offenders: {offenders}"


def test_engine_recompute_has_no_accounts_kwarg():
    """No function in net_alpha.engine.recompute may accept an 'accounts' kwarg."""
    offenders = []
    for fn in _public_funcs(recompute):
        sig = inspect.signature(fn)
        if "accounts" in sig.parameters:
            offenders.append(fn.__qualname__)
    assert not offenders, f"Engine recompute functions must not accept 'accounts'. Offenders: {offenders}"
