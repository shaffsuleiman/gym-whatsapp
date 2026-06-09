"""Weight progress chart with linear-trend prediction -> base64 PNG (matplotlib)."""
import base64
import io
from datetime import datetime, timedelta
from typing import Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


def _to_dt(ts) -> Optional[datetime]:
    if isinstance(ts, datetime):
        return ts
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:
        return None


def build_progress_chart(weights: list[dict], target_weight: Optional[float]) -> tuple[str, str]:
    """Return (summary_text, base64_png). base64_png is '' when there is no data."""
    pts = []
    for w in weights:
        dt = _to_dt(w.get("ts"))
        val = w.get("weight_kg")
        if dt is not None and val is not None:
            pts.append((dt, float(val)))
    if not pts:
        return ("No weight entries yet. Log your weight to start tracking your progress.", "")

    pts.sort(key=lambda p: p[0])
    dates = [p[0] for p in pts]
    ys = np.array([p[1] for p in pts], dtype=float)
    base = dates[0]
    xs = np.array([(d - base).total_seconds() / 86400.0 for d in dates], dtype=float)

    slope, intercept = (0.0, float(ys[0])) if len(xs) < 2 else tuple(np.polyfit(xs, ys, 1))

    last_x = xs[-1]
    future_x = np.array([last_x, last_x + 14.0])
    future_dates = [base + timedelta(days=float(x)) for x in future_x]
    trend_x = np.concatenate([xs, future_x])
    trend_dates = [base + timedelta(days=float(x)) for x in trend_x]
    trend_y = slope * trend_x + intercept

    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=110)
    ax.plot(dates, ys, "-o", color="#2b8cbe", label="Weight (kg)")
    ax.plot(trend_dates, trend_y, "--", color="#e34a33", label="Trend / Prediction")
    if target_weight:
        ax.axhline(target_weight, linestyle=":", color="#31a354", label=f"Target ({target_weight:g} kg)")
    ax.set_title("Weight Progress & Prediction")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    fig.autofmt_xdate()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    per_week = round(slope * 7, 1)
    proj14 = round(slope * (last_x + 14) + intercept, 1)
    word = "losing" if slope < -0.01 else ("gaining" if slope > 0.01 else "holding")
    summary = f"You are {word} about {abs(per_week)} kg/week. Projected ~{proj14} kg in 2 weeks."
    if target_weight:
        summary += f" Target: {target_weight:g} kg."
    return (summary, b64)
