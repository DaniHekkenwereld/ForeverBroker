"""Completed-day intraday auction timings: advisory only, never executes game trades.

Window comparisons are paired within the same calendar day and based on
per-item historical asking prices, not observed executable fills. All model
inputs predate asof; no partial current day or future rows enter training.
"""
import datetime as dt
import math
import statistics as st
from collections import defaultdict
from zoneinfo import ZoneInfo

# Four fixed local-time windows avoid mining hundreds of pairs from tiny samples.
WINDOWS = (
    ('Nacht', 0, 6),
    ('Ochtend', 6, 12),
    ('Middag', 12, 17),
    ('Avond', 17, 23),
)


def _q25(values):
    values = sorted(values)
    return values[max(0, math.ceil(.25 * len(values)) - 1)]


def analyse(db, item_id, asof, config, source='tk'):
    """Pick paired buy/sell windows if evidence is strong enough for paper advice.

    Minimum five COMPLETE days with >=16 distinct hourly price observations;
    at least two observations in each buy/sell window for each paired day.
    """
    z = ZoneInfo(config.get('timezone', 'Europe/Amsterdam'))
    today = dt.datetime.fromtimestamp(asof, dt.timezone.utc).astimezone(z).date()
    byday = defaultdict(dict)
    since = asof - 35 * 86400
    for at, ask in db.execute('''SELECT t,ask FROM price_history WHERE item_id=? AND source=?
                                AND t>=? AND t<? AND ask>0 ORDER BY t''', (item_id, source, since, asof)):
        d = dt.datetime.fromtimestamp(at, dt.timezone.utc).astimezone(z)
        if d.date() >= today:
            continue
        # One sample per local hour: irregular sampling cannot inflate evidence.
        byday[d.date()][d.hour] = int(ask)
    full = {d: hours for d, hours in byday.items() if len(hours) >= 16}
    if len(full) < config.get('daily_min_days', 5):
        return None
    daybase = {d: st.median(h.values()) for d, h in full.items()}
    baseline = st.median(v for _, v in sorted(daybase.items())[-3:])
    cut = config.get('cut_pct', 5) / 100
    minimum = config.get('daily_min_days', 5)
    min_roi = config.get('daily_min_net_roi_pct', 8)
    min_win = config.get('daily_min_win_rate', .7)
    best = None
    for ai, (buy_label, b0, b1) in enumerate(WINDOWS[:-1]):
        for sell_label, s0, s1 in WINDOWS[ai + 1:]:
            if s0 - b1 < 0:
                continue
            pairs = []
            for day, hours in full.items():
                bp = [v for h, v in hours.items() if b0 <= h < b1]
                sp = [v for h, v in hours.items() if s0 <= h < s1]
                if len(bp) < 2 or len(sp) < 2:
                    continue
                pairs.append((day, st.median(bp), st.median(sp), daybase[day]))
            if len(pairs) < minimum:
                continue
            gains = [(sell * (1 - cut) - buy) / buy * 100 for _, buy, sell, _ in pairs]
            win = sum(g > min_roi for g in gains) / len(gains)
            safe_roi = _q25(gains)
            median_roi = st.median(gains)
            buy_ratio = st.median(b / base for _, b, _, base in pairs)
            sale_ratio = _q25([s / base for _, _, s, base in pairs])
            target = max(1, math.floor(baseline * sale_ratio * .99))
            ceiling = max(1, math.floor(baseline * buy_ratio * 1.02))
            confidence = min(.85, .35 + .04 * (len(pairs) - 5)) * win
            eligible = (win >= min_win and safe_roi >= min_roi
                        and target * (1 - cut) > ceiling and s0 > b0)
            plan = dict(item_id=item_id, buy=buy_label, sell=sell_label,
                        buy_start=b0, buy_end=b1, sell_start=s0, sell_end=s1,
                        samples=len(pairs), win_rate=win, median_net_roi=median_roi,
                        conservative_net_roi=safe_roi, confidence=confidence,
                        target=target, ceiling=ceiling, eligible=eligible,
                        baseline=baseline, asof=asof)
            # Prefer validated windows; otherwise display the best observed
            # (explicitly unvalidated) median spread instead of arbitrary ties.
            score = (int(eligible), safe_roi if eligible else median_roi, win, len(pairs))
            if best is None or score > best[0]:
                best = (score, plan)
    return best[1] if best else None


def opportunity(plan, ask, local_hour, config, vendor=0):
    """One advisory paper proposal, only inside the detected buy window."""
    if not plan or not plan['eligible'] or not plan['buy_start'] <= local_hour < plan['buy_end']:
        return None
    if type(ask) is not int or ask <= 0 or ask > plan['ceiling']:
        return None
    deposit = math.ceil(vendor * config.get('deposit_vendor_pct', 15) / 100)
    net = plan['target'] - math.ceil(plan['target'] * config.get('cut_pct', 5) / 100) - ask - deposit
    if net / ask * 100 < config.get('daily_min_net_roi_pct', 8):
        return None
    hold = plan['sell_start'] - local_hour
    if hold <= 0 or hold >= config.get('max_hold_hours', 168):
        return None
    return ('daily', plan['target'], hold, plan['confidence'], {
        'buy_window': plan['buy'], 'sell_window': plan['sell'],
        'buy_hours': [plan['buy_start'], plan['buy_end']],
        'sell_hours': [plan['sell_start'], plan['sell_end']],
        'paired_days': plan['samples'], 'win_rate': round(plan['win_rate'], 3),
        'conservative_net_roi': round(plan['conservative_net_roi'], 2),
        'buy_ceiling': plan['ceiling'], 'hold_hours': hold,
        'pattern_source': 'hourly historical asks; no confirmed fills',
    })
