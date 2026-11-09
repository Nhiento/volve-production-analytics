"""Arps decline curve analysis for the Volve producers.

Used by notebooks/02_decline_curve_analysis.ipynb. Run directly to rebuild the
result tables and charts:

    python python/decline_curves.py

Rates are producing-day rates (oil / on-stream days), so downtime does not look
like decline. Volumes are converted back to calendar volumes with each well's
recent uptime.
"""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit

ROOT = Path(__file__).resolve().parents[1]
DAILY = ROOT / "data" / "processed" / "production_daily_clean.csv"
OUT_DIR = ROOT / "data" / "processed"
IMG_DIR = ROOT / "images"

WELLS = ["15/9-F-12", "15/9-F-14", "15/9-F-11"]
BACKTEST_CUTOFF = pd.Timestamp("2016-01-01")  # train on everything before, test on 2016
MIN_PROD_DAYS = 10        # months with fewer producing days are too noisy to fit
JUMP_RATIO = 1.3          # a month-over-month rate rise of 30%+ marks a restart / intervention
WINDOW_MONTHS = 24        # fit at most the last 24 months
SM3_TO_BBL = 6.2898
ECON_LIMITS = [50, 100, 150]  # Sm3 per producing day
MAX_FORECAST_MONTHS = 240

COLORS = {"exp": "#2a78d6", "hyp": "#eb6834", "naive": "#8a8984",
          "ink": "#0b0b0b", "muted": "#52514e", "grid": "#e4e3df"}


# --------------------------------------------------------------------------- data
def monthly_rates(path=DAILY):
    d = pd.read_csv(path, parse_dates=["DATEPRD"])
    d["month"] = d["DATEPRD"].dt.to_period("M").dt.to_timestamp()
    m = (d.groupby(["NPD_WELL_BORE_NAME", "month"])
           .agg(oil=("BORE_OIL_VOL", "sum"), on_hrs=("ON_STREAM_HRS", "sum"))
           .reset_index()
           .rename(columns={"NPD_WELL_BORE_NAME": "well"}))
    m["prod_days"] = m["on_hrs"] / 24
    m["cal_days"] = m["month"].dt.days_in_month
    m["uptime"] = (m["prod_days"] / m["cal_days"]).clip(upper=1)
    m["rate"] = m["oil"] / m["prod_days"].where(m["prod_days"] > 0)
    return m


def months_between(a, b):
    return (b.year - a.year) * 12 + (b.month - a.month)


def fit_window_start(well_m, end):
    """Start of the current decline segment, using data before `end` only.

    1. Find the last month whose rate jumped 30%+ over the previous producing
       month (a restart or intervention: the old decline no longer applies).
    2. Start at the peak rate on or after that jump.
    3. Never look back more than WINDOW_MONTHS: the decline steepens as water
       cut rises, so old data makes the curve too flat.
    """
    x = well_m[(well_m["month"] < end) & (well_m["prod_days"] >= MIN_PROD_DAYS)].reset_index(drop=True)
    jumps = x.index[x["rate"] / x["rate"].shift(1) >= JUMP_RATIO]
    seg = x.loc[jumps[-1]:] if len(jumps) else x
    peak_month = seg.loc[seg["rate"].idxmax(), "month"]
    cap = end - pd.DateOffset(months=WINDOW_MONTHS)
    return max(peak_month, cap)


# ----------------------------------------------------------------------- models
def exponential(t, qi, di):
    return qi * np.exp(-di * t)


def hyperbolic(t, qi, di, b):
    return qi / (1 + b * di * t) ** (1 / b)


def fit_models(t, q):
    """Fit both Arps models in log space (so a 10% miss counts the same at any rate)."""
    q0 = float(q[0])
    pe, _ = curve_fit(lambda t, a, d: np.log(exponential(t, a, d)), t, np.log(q),
                      p0=[q0, 0.05], bounds=([0, 0], [1e5, 1]))
    ph, _ = curve_fit(lambda t, a, d, b: np.log(hyperbolic(t, a, d, b)), t, np.log(q),
                      p0=[q0, 0.05, 0.5], bounds=([0, 1e-4, 0.01], [1e5, 2, 1.0]))
    return {"exp": pe, "hyp": ph}


def predict(model, params, t):
    return exponential(t, *params) if model == "exp" else hyperbolic(t, *params)


def annual_decline(di_monthly):
    """Effective annual decline for an exponential monthly nominal rate."""
    return 1 - np.exp(-12 * di_monthly)


def prepare(well_m, start, end):
    x = well_m[(well_m["month"] >= start) & (well_m["month"] < end)
               & (well_m["prod_days"] >= MIN_PROD_DAYS)].copy()
    x["t"] = x["month"].apply(lambda mo: months_between(start, mo))
    return x


# --------------------------------------------------------------------- backtest
def backtest(m):
    rows, curves = [], {}
    for well in WELLS:
        wm = m[m["well"] == well]
        start = fit_window_start(wm, BACKTEST_CUTOFF)
        train = prepare(wm, start, BACKTEST_CUTOFF)
        test = prepare(wm, start, pd.Timestamp("2100-01-01"))
        test = test[test["month"] >= BACKTEST_CUTOFF]
        fits = fit_models(train["t"].values, train["rate"].values)
        naive = train["rate"].tail(3).mean()

        preds = {"exp": predict("exp", fits["exp"], test["t"].values),
                 "hyp": predict("hyp", fits["hyp"], test["t"].values),
                 "naive": np.full(len(test), naive)}
        actual = test["rate"].values
        # volume check: predicted rate x actual producing days, so it isolates the rate forecast
        actual_vol = (actual * test["prod_days"].values).sum()
        for name, p in preds.items():
            rows.append({
                "well": well, "model": name,
                "fit_from": start.strftime("%Y-%m"), "train_months": len(train),
                "test_months": len(test),
                "mape_pct": np.mean(np.abs(p - actual) / actual) * 100,
                "volume_error_pct": ((p * test["prod_days"].values).sum() / actual_vol - 1) * 100,
            })
        curves[well] = {"start": start, "train": train, "test": test, "fits": fits, "naive": naive}
    return pd.DataFrame(rows), curves


def full_history_check(m, well="15/9-F-14"):
    """Same backtest, but fitting from the well's peak with no 24-month cap."""
    wm = m[m["well"] == well]
    x = wm[(wm["month"] < BACKTEST_CUTOFF) & (wm["prod_days"] >= MIN_PROD_DAYS)]
    start = x.loc[x["rate"].idxmax(), "month"]
    train = prepare(wm, start, BACKTEST_CUTOFF)
    test = prepare(wm, start, pd.Timestamp("2100-01-01"))
    test = test[test["month"] >= BACKTEST_CUTOFF]
    fits = fit_models(train["t"].values, train["rate"].values)
    p = predict("exp", fits["exp"], test["t"].values)
    return {"well": well, "fit_from": start.strftime("%Y-%m"),
            "mape_pct": np.mean(np.abs(p - test["rate"].values) / test["rate"].values) * 100}


# --------------------------------------------------------------------- forecast
def forecast_remaining(m):
    """Refit on all data and project each well to several economic limits."""
    rows, curves = [], {}
    for well in WELLS:
        wm = m[m["well"] == well]
        last = wm[wm["prod_days"] >= MIN_PROD_DAYS]["month"].max()
        end = last + pd.DateOffset(months=1)
        start = fit_window_start(wm, end)
        train = prepare(wm, start, end)
        fits = fit_models(train["t"].values, train["rate"].values)
        uptime = wm[wm["month"] <= last].tail(12)["uptime"].mean()

        t_last = months_between(start, last)
        t_future = np.arange(t_last + 1, t_last + 1 + MAX_FORECAST_MONTHS)
        months = pd.date_range(last + pd.DateOffset(months=1), periods=MAX_FORECAST_MONTHS, freq="MS")
        days = months.days_in_month.values
        curves[well] = {"start": start, "train": train, "fits": fits, "t_future": t_future,
                        "months": months, "uptime": uptime, "last": last}

        for model in ["exp", "hyp"]:
            q = predict(model, fits[model], t_future)
            for limit in ECON_LIMITS:
                keep = q >= limit
                n = int(np.argmin(keep)) if not keep.all() else len(q)
                vol = (q[:n] * days[:n] * uptime).sum()
                rows.append({
                    "well": well, "model": model, "econ_limit_sm3d": limit,
                    "last_rate_sm3d": train["rate"].iloc[-1],
                    "fitted_annual_decline_pct": annual_decline(fits["exp"][1]) * 100 if model == "exp" else np.nan,
                    "hyp_b": fits["hyp"][2] if model == "hyp" else np.nan,
                    "uptime_assumed_pct": uptime * 100,
                    "months_to_limit": n,
                    "limit_reached": months[n - 1].strftime("%Y-%m") if n else "already below",
                    "remaining_oil_sm3": vol,
                    "remaining_oil_bbl": vol * SM3_TO_BBL,
                })
    return pd.DataFrame(rows), curves


# ------------------------------------------------------------------------ charts
def _style(ax):
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    for side in ["left", "bottom"]:
        ax.spines[side].set_color(COLORS["grid"])
    ax.tick_params(colors=COLORS["muted"], labelsize=9)
    ax.grid(axis="y", color=COLORS["grid"], linewidth=0.8)
    ax.set_axisbelow(True)


def plot_backtest(curves, results, path):
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), facecolor="#fcfcfb")
    for ax, well in zip(axes, WELLS):
        c = curves[well]
        _style(ax)
        ax.set_facecolor("#fcfcfb")
        ax.scatter(c["train"]["month"], c["train"]["rate"], s=22, color=COLORS["muted"],
                   label="Training data", zorder=3)
        ax.scatter(c["test"]["month"], c["test"]["rate"], s=34, facecolor="#fcfcfb",
                   edgecolor=COLORS["ink"], linewidth=1.5, label="2016 actual (held out)", zorder=4)
        t_all = np.arange(0, months_between(c["start"], c["test"]["month"].max()) + 1)
        months = pd.date_range(c["start"], periods=len(t_all), freq="MS")
        ax.plot(months, predict("exp", c["fits"]["exp"], t_all), color=COLORS["exp"], lw=2,
                label="Exponential")
        ax.plot(months, predict("hyp", c["fits"]["hyp"], t_all), color=COLORS["hyp"], lw=2,
                ls="--", label="Hyperbolic")
        test_months = c["test"]["month"]
        ax.plot(test_months, np.full(len(test_months), c["naive"]), color=COLORS["naive"], lw=2,
                ls=":", label="Naive (last 3 months)")
        ax.axvline(BACKTEST_CUTOFF, color=COLORS["grid"], lw=1.2)
        r = results[results["well"] == well].set_index("model")["mape_pct"]
        ax.set_title(f"{well}\nerror: exp {r['exp']:.0f}%  ·  hyp {r['hyp']:.0f}%  ·  naive {r['naive']:.0f}%",
                     fontsize=10.5, color=COLORS["ink"], loc="left")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
        ax.set_ylim(bottom=0)
    axes[0].set_ylabel("Oil rate (Sm³ per producing day)", color=COLORS["muted"], fontsize=9.5)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=5, frameon=False, fontsize=9.5)
    fig.suptitle("Backtest: curves fit on data before 2016, scored on 2016 (mean absolute % error)",
                 x=0.01, ha="left", fontsize=12, color=COLORS["ink"])
    fig.tight_layout(rect=[0, 0.07, 1, 0.95])
    fig.savefig(path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)


def window_sensitivity(m, well="15/9-F-11", starts=("2015-04", "2016-01", "2016-04"), limit=100):
    """Remaining oil for one well when the fit starts at different months."""
    wm = m[m["well"] == well]
    last = wm[wm["prod_days"] >= MIN_PROD_DAYS]["month"].max()
    uptime = wm[wm["month"] <= last].tail(12)["uptime"].mean()
    months = pd.date_range(last + pd.DateOffset(months=1), periods=MAX_FORECAST_MONTHS, freq="MS")
    days = months.days_in_month.values
    rows, curves = [], {}
    for s in starts:
        start = pd.Timestamp(s)
        train = prepare(wm, start, last + pd.DateOffset(months=1))
        pe = fit_models(train["t"].values, train["rate"].values)["exp"]
        t_future = np.arange(train["t"].max() + 1, train["t"].max() + 1 + MAX_FORECAST_MONTHS)
        q = exponential(t_future, *pe)
        n = int(np.argmin(q >= limit)) if not (q >= limit).all() else len(q)
        vol = (q[:n] * days[:n] * uptime).sum()
        rows.append({"well": well, "fit_from": s, "fit_months": len(train),
                     "annual_decline_pct": annual_decline(pe[1]) * 100,
                     "limit_reached": months[n - 1].strftime("%Y-%m") if n else "already below",
                     "remaining_oil_sm3": vol, "remaining_oil_bbl": vol * SM3_TO_BBL})
        curves[s] = (months, q)
    return pd.DataFrame(rows), curves


def plot_forecast(m, curves, sens_curves, path, base_limit=100, low_limit=50):
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), facecolor="#fcfcfb")
    for ax, well in zip(axes, WELLS):
        c = curves[well]
        _style(ax)
        ax.set_facecolor("#fcfcfb")
        hist = m[(m["well"] == well) & (m["month"] >= pd.Timestamp("2013-01-01"))
                 & (m["prod_days"] >= MIN_PROD_DAYS)]
        ax.scatter(hist["month"], hist["rate"], s=16, color=COLORS["muted"], label="Actual", zorder=3)
        q = predict("exp", c["fits"]["exp"], c["t_future"])
        n = int(np.argmin(q >= low_limit))
        ax.plot(c["months"][:n + 1], q[:n + 1], color=COLORS["exp"], lw=2,
                label="Exponential forecast (base case)")
        if well == "15/9-F-11":
            months, qs = sens_curves["2016-04"]
            k = min(int(np.argmin(qs >= base_limit)) if not (qs >= base_limit).all() else len(qs), 36)
            ax.plot(months[:k], qs[:k], color=COLORS["hyp"], lw=2, ls="--",
                    label="If the late-2016 flattening holds")
        for lim, txt in [(base_limit, "base-case limit"), (low_limit, "low limit")]:
            ax.axhline(lim, color=COLORS["ink"] if lim == base_limit else COLORS["naive"],
                       lw=1, ls=(0, (2, 2)))
            if well == WELLS[0]:
                ax.annotate(f"{txt} {lim} Sm³/d", xy=(0.01, lim), xycoords=("axes fraction", "data"),
                            va="bottom" if lim == base_limit else "top", fontsize=8.5,
                            color=COLORS["muted"])
        ax.set_title(well, fontsize=10.5, color=COLORS["ink"], loc="left")
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.set_ylim(bottom=0)
    axes[0].set_ylabel("Oil rate (Sm³ per producing day)", color=COLORS["muted"], fontsize=9.5)
    handles, labels = [], []
    for ax in axes:
        for h, l in zip(*ax.get_legend_handles_labels()):
            if l not in labels:
                handles.append(h); labels.append(l)
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False, fontsize=9.5)
    fig.suptitle("Forecast from the 2016 shut-in: how much oil was left above the economic limit?",
                 x=0.01, ha="left", fontsize=12, color=COLORS["ink"])
    fig.tight_layout(rect=[0, 0.07, 1, 0.95])
    fig.savefig(path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)


# -------------------------------------------------------------------------- main
def main():
    m = monthly_rates()
    bt, bt_curves = backtest(m)
    fc, fc_curves = forecast_remaining(m)
    sens, sens_curves = window_sensitivity(m)
    sens.round(1).to_csv(OUT_DIR / "decline_f11_sensitivity.csv", index=False)
    bt.round(1).to_csv(OUT_DIR / "decline_backtest.csv", index=False)
    fc.round(2).to_csv(OUT_DIR / "decline_forecast.csv", index=False)
    plot_backtest(bt_curves, bt, IMG_DIR / "decline_backtest.png")
    plot_forecast(m, fc_curves, sens_curves, IMG_DIR / "decline_forecast.png")
    print(bt.round(1).to_string(index=False))
    print(full_history_check(m))
    print(fc[fc["model"] == "exp"].round(1).to_string(index=False))
    print(sens.round(1).to_string(index=False))


if __name__ == "__main__":
    main()
