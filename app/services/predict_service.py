from __future__ import annotations

import calendar
import math
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from app.services.supabase_client import supabase


# =============================================================================
# RPC routing
# =============================================================================
# OLD (dashboard materializado)
RPC_SERIES_DIARIA_OLD = "dashboard_series_diaria"
RPC_DOSIS_VACUNA_DIA_OLD = "dashboard_dosis_por_vacuna_dia"

# NEW (regla de negocio para modelos)
RPC_SERIES_DIARIA_NEW = "dashboard_series_diaria_registro"


# =============================================================================
# Helpers fechas
# =============================================================================
def _parse_ym(periodo: str | None) -> date | None:
    if not periodo:
        return None
    s = str(periodo).strip()
    if len(s) >= 7:
        s = s[:7]
    try:
        y, m = s.split("-")
        return date(int(y), int(m), 1)
    except Exception:
        return None


def _month_end(d: date) -> date:
    last = calendar.monthrange(d.year, d.month)[1]
    return date(d.year, d.month, last)


def _next_month_first(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def _date_range(d1: date, d2: date) -> list[date]:
    out: list[date] = []
    cur = d1
    while cur <= d2:
        out.append(cur)
        cur += timedelta(days=1)
    return out

def _add_months(d: date, k: int) -> date:
    y = d.year + (d.month - 1 + k) // 12
    m = (d.month - 1 + k) % 12 + 1
    return date(y, m, 1)


def _future_days_for_horizon(end_month: date, horizon_m: int) -> list[date]:
    # end_month = YYYY-MM-01 (mes base)
    # horizonte: desde mes siguiente hasta el último día del mes (horizon_m meses adelante)
    start = _next_month_first(end_month)
    last_month_first = _add_months(start, max(1, int(horizon_m)) - 1)
    end = _month_end(last_month_first)
    return _date_range(start, end)


def _aggregate_daily_to_monthly(future_days: list[date], y_fc: list[float]) -> list[dict]:
    if not future_days or not y_fc:
        return []
    by_m: dict[str, float] = {}
    for d, v in zip(future_days, y_fc):
        k = d.strftime("%Y-%m")
        by_m[k] = by_m.get(k, 0.0) + float(v or 0.0)
    out = [{"periodo": k, "total": float(round(by_m[k], 0))} for k in sorted(by_m.keys())]
    return out



# =============================================================================
# Normalización numérica
# =============================================================================
def _num_clean(x):
    if x is None:
        return x
    s = str(x).strip()
    if s == "":
        return s

    s = s.replace(" ", "")

    if ("," in s) and ("." in s):
        s = s.replace(".", "").replace(",", ".")
        return s

    if "," in s and "." not in s:
        s = s.replace(",", "")
        return s

    if "." in s and "," not in s:
        parts = s.split(".")
        if len(parts[-1]) == 3 and all(p.isdigit() for p in parts):
            s = "".join(parts)
        return s

    return s


# =============================================================================
# Insumos estimados (diario) - (NO SE CRUZA CON REGLA NUEVA)
# =============================================================================
def _calc_insumos_estimados_diario(start_day: date, end_day: date, vacuna: str | None = None) -> dict:
    rows = supabase.rpc(RPC_DOSIS_VACUNA_DIA_OLD, {
        "p_fecha_desde": start_day.isoformat(),
        "p_fecha_hasta": end_day.isoformat(),
    }).execute().data or []

    vacuna_filtro = vacuna.strip().upper() if vacuna else None

    mrows = supabase.rpc("jeringas_map_por_vacuna", {}).execute().data or []
    vac_to_types: dict[str, list[str]] = {}
    for r in mrows:
        v = (r.get("vacuna") or "").strip()
        t = (r.get("jeringa_tipo") or "").strip()
        if not v or not t:
            continue
        vac_to_types.setdefault(v, []).append(t)

    day_map: dict[date, dict] = {}
    for r in rows:
        f = pd.to_datetime(r["fecha"]).date()
        v = str(r.get("vacuna") or "")
        d = int(r.get("dosis") or 0)
        if f not in day_map:
            day_map[f] = {"dosis_total": 0, "by_vac": {}}
        day_map[f]["dosis_total"] += d
        day_map[f]["by_vac"][v] = day_map[f]["by_vac"].get(v, 0) + d

    cur = start_day
    while cur <= end_day:
        if cur not in day_map:
            day_map[cur] = {"dosis_total": 0, "by_vac": {}}
        cur += timedelta(days=1)

    rows_p = supabase.rpc(RPC_SERIES_DIARIA_OLD, {
        "p_tipo": "PERSONAS_UNICAS_DIA",
        "p_fecha_desde": start_day.isoformat(),
        "p_fecha_hasta": end_day.isoformat(),
    }).execute().data or []

    personas_by_day: dict[date, int] = {}
    for r in rows_p:
        f = pd.to_datetime(r["fecha"]).date()
        personas_by_day[f] = int(r.get("valor") or 0)

    jeringas_por_tipo_total: dict[str, int] = {}
    daily: list[dict] = []

    dosis_total_periodo = 0
    alcohol_ml_total = 0

    for f in sorted(day_map.keys()):
        dosis_dia = int(day_map[f]["dosis_total"] or 0)
        personas_dia = int(personas_by_day.get(f, 0))

        dosis_total_periodo += dosis_dia

        # Regla histórico (dashboard): jeringas=dosis, guantes=personas
        jeringas_total = dosis_dia
        guantes_total = personas_dia
        alcohol_ml = dosis_dia * 1
        alcohol_ml_total += alcohol_ml

        # Pie por tipo (solo afecta breakdown, no afecta jeringas_total)
        for vac, d in day_map[f]["by_vac"].items():
            if vacuna_filtro and vac.upper() != vacuna_filtro:
                continue
            tipos = vac_to_types.get(vac) or []
            if not tipos:
                jeringas_por_tipo_total["SIN MAPEO"] = jeringas_por_tipo_total.get("SIN MAPEO", 0) + d
                continue

            k = len(tipos)
            base = d // k
            rem = d % k
            for i, t in enumerate(tipos):
                add = base + (1 if i < rem else 0)
                if add > 0:
                    jeringas_por_tipo_total[t] = jeringas_por_tipo_total.get(t, 0) + add

        daily.append({
            "fecha": f.isoformat(),
            "dosis": dosis_dia,
            "personas": personas_dia,
            "jeringas": jeringas_total,
            "guantes": guantes_total,
            "alcohol_ml": alcohol_ml
        })

    algodon_rollos = int(math.ceil(dosis_total_periodo / 350.0)) if dosis_total_periodo > 0 else 0

    return {
        "daily": daily,
        "jeringas_por_tipo_total": jeringas_por_tipo_total,
        "kpis": {
            "dosis_total": int(dosis_total_periodo),
            "alcohol_ml_total": int(alcohol_ml_total),
            "algodon_rollos": int(algodon_rollos)
        }
    }


# =============================================================================
# Resultado estándar
# =============================================================================
@dataclass
class ForecastResult:
    label: str | None
    next_value: float | None
    x_hist: list[str]
    y_hist: list[float]
    x_fc: list[str]
    y_fc: list[float]
    model: str
    metrics: dict = field(default_factory=dict)


# =============================================================================
# RPC fetchers
# =============================================================================
def _fetch_reporte_diario_old(tipo_reporte: str, start: date, end: date) -> pd.DataFrame:
    rows = supabase.rpc(RPC_SERIES_DIARIA_OLD, {
        "p_tipo": tipo_reporte,
        "p_fecha_desde": start.isoformat(),
        "p_fecha_hasta": end.isoformat(),
    }).execute().data or []
    if not rows:
        return pd.DataFrame(columns=["fecha", "y"])

    df = pd.DataFrame(rows)
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.date
    df["valor"] = df["valor"].apply(_num_clean)
    df["y"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0).astype(float)
    return df[["fecha", "y"]]


def _fetch_reporte_diario_new(tipo_reporte: str, start: date, end: date) -> pd.DataFrame:
    rows = supabase.rpc(RPC_SERIES_DIARIA_NEW, {
        "p_tipo": tipo_reporte,
        "p_fecha_desde": start.isoformat(),
        "p_fecha_hasta": end.isoformat(),
    }).execute().data or []
    if not rows:
        return pd.DataFrame(columns=["fecha", "y"])

    df = pd.DataFrame(rows)
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.date
    df["valor"] = df["valor"].apply(_num_clean)
    df["y"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0).astype(float)
    return df[["fecha", "y"]]


def _fetch_mov_diario(entidad_tipo: str, start: date, end: date) -> pd.DataFrame:
    rows = supabase.rpc("mov_series_diaria", {
        "p_entidad_tipo": entidad_tipo,
        "p_fecha_desde": start.isoformat(),
        "p_fecha_hasta": end.isoformat(),
    }).execute().data or []
    if not rows:
        return pd.DataFrame(columns=["fecha", "y"])

    df = pd.DataFrame(rows)
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.date
    df["valor"] = df["valor"].apply(_num_clean)
    df["y"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0).astype(float)
    return df[["fecha", "y"]]


def _fetch_mov_mensual(entidad_tipo: str, p_from: str, p_to: str) -> pd.DataFrame:
    rows = supabase.rpc("mov_series_mensual", {
        "p_entidad_tipo": entidad_tipo,
        "p_periodo_desde": p_from,
        "p_periodo_hasta": p_to,
    }).execute().data or []

    if not rows:
        return pd.DataFrame(columns=["periodo", "y"])

    df = pd.DataFrame(rows)
    df["periodo"] = df["periodo"].astype(str)
    df["valor"] = df["valor"].apply(_num_clean)
    df["y"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0).astype(float)
    return df[["periodo", "y"]]


def _fetch_people_mensual_ultimos(end_month: date, max_meses: int = 6) -> pd.DataFrame:
    rows = supabase.rpc("dashboard_people_mes_ultimos", {
        "p_periodo_hasta": end_month.strftime("%Y-%m"),
        "p_max_meses": int(max_meses),
    }).execute().data or []

    if not rows:
        return pd.DataFrame(columns=["periodo", "y"])

    df = pd.DataFrame(rows)
    df["periodo"] = df["periodo"].astype(str)
    df["valor"] = df["valor"].apply(_num_clean)
    df["y"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0).astype(float)
    return df[["periodo", "y"]]


# =============================================================================
# PEOPLE (pipeline antiguo para "people_plot")
# =============================================================================
def _dow_pattern_weights(daily_hist: pd.DataFrame) -> dict[int, float]:
    if daily_hist.empty:
        return {i: 1.0 for i in range(7)}

    tmp = daily_hist.copy()
    tmp["fecha"] = pd.to_datetime(tmp["fecha"])
    tmp["dow"] = tmp["fecha"].dt.dayofweek.astype(int)

    g = tmp.groupby("dow")["y"].mean().to_dict()
    w = {i: float(g.get(i, 0.0)) for i in range(7)}

    if sum(w.values()) <= 0:
        return {i: 1.0 for i in range(7)}
    return w


def _alloc_month_total_by_dow(month_total: float, nm_first: date, nm_last: date, dow_w: dict[int, float]) -> list[int]:
    days = _date_range(nm_first, nm_last)
    if not days:
        return []

    total = max(0.0, float(month_total))

    dows: list[int] = []
    denom = 0.0
    for d in days:
        dow = int(pd.to_datetime(d).dayofweek)
        dows.append(dow)
        denom += float(dow_w.get(dow, 0.0))

    if denom <= 0:
        base = total / float(len(days))
        return [int(round(base)) for _ in days]

    raw = [total * float(dow_w.get(dow, 0.0)) / denom for dow in dows]

    floors = [int(math.floor(x)) for x in raw]
    remainder = int(round(total - sum(floors)))

    fracs = [(i, raw[i] - floors[i]) for i in range(len(raw))]
    fracs.sort(key=lambda t: t[1], reverse=True)

    vals = floors[:]
    if remainder > 0:
        for i, _ in fracs[:remainder]:
            vals[i] += 1
    elif remainder < 0:
        fracs.sort(key=lambda t: t[1])
        need = -remainder
        for i, _ in fracs:
            if need <= 0:
                break
            if vals[i] > 0:
                vals[i] -= 1
                need -= 1

    return vals


def _people_monthly_proxy_from_daily(df_people_daily: pd.DataFrame, months_back: int = 6) -> pd.DataFrame:
    if df_people_daily.empty:
        return pd.DataFrame(columns=["periodo", "y"])

    tmp = df_people_daily.copy()
    tmp["fecha"] = pd.to_datetime(tmp["fecha"])
    tmp["periodo"] = tmp["fecha"].dt.strftime("%Y-%m")
    m = tmp.groupby("periodo")["y"].sum().reset_index()
    m = m.tail(int(months_back))
    m.columns = ["periodo", "y"]
    m["y"] = pd.to_numeric(m["y"], errors="coerce").fillna(0).astype(float)
    return m


def _ratio_doses_per_person(df_total: pd.DataFrame, df_people: pd.DataFrame) -> float:
    try:
        total = float(df_total["y"].sum()) if not df_total.empty else 0.0
        ppl = float(df_people["y"].sum()) if not df_people.empty else 0.0
        if ppl <= 0:
            return 1.0
        r = total / ppl
        r = max(1.0, min(r, 10.0))
        return float(r)
    except Exception:
        return 1.0


# =============================================================================
# Modelos (XGB si existe, si no RF)
# =============================================================================
def _train_regressor(is_count: bool = True):
    try:
        from xgboost import XGBRegressor

        params = dict(
            n_estimators=900,
            learning_rate=0.05,
            max_depth=6,
            subsample=0.9,
            colsample_bytree=0.9,
            reg_lambda=1.0,
            random_state=7,
            n_jobs=-1,
        )

        if is_count:
            params.update(dict(objective="count:poisson", eval_metric="poisson-nloglik"))
            return XGBRegressor(**params), "XGBoost Poisson (count)"
        params.update(dict(objective="reg:squarederror", eval_metric="rmse"))
        return XGBRegressor(**params), "XGBoost (reg)"
    except Exception:
        return RandomForestRegressor(
            n_estimators=450,
            random_state=7,
            max_depth=None,
            min_samples_leaf=2,
            n_jobs=-1
        ), "RandomForest (fallback)"


def _safe_mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    den = np.maximum(1.0, np.abs(y_true))
    return float(np.mean(np.abs(y_true - y_pred) / den))


def _smape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    den = np.maximum(1.0, np.abs(y_true) + np.abs(y_pred))
    return float(np.mean(2.0 * np.abs(y_pred - y_true) / den))


def _build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("fecha").copy()
    dt = pd.to_datetime(df["fecha"])

    df["t"] = np.arange(len(df), dtype=int)
    df["dow"] = dt.dt.dayofweek.astype(int)
    df["month"] = dt.dt.month.astype(int)
    df["is_weekend"] = (df["dow"] >= 5).astype(int)

    doy = dt.dt.dayofyear.astype(float)
    df["sin_doy"] = np.sin(2.0 * np.pi * doy / 365.25)
    df["cos_doy"] = np.cos(2.0 * np.pi * doy / 365.25)

    df["lag1"] = df["y"].shift(1)
    df["lag7"] = df["y"].shift(7)
    df["lag14"] = df["y"].shift(14)
    df["lag28"] = df["y"].shift(28)

    df["ma7"] = df["y"].rolling(7, min_periods=1).mean()
    df["ma14"] = df["y"].rolling(14, min_periods=1).mean()
    df["ma28"] = df["y"].rolling(28, min_periods=1).mean()

    for c in ["lag1", "lag7", "lag14", "lag28", "ma7", "ma14", "ma28"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    return df


def _fit_predict_recursive(model, df_hist: pd.DataFrame, future_dates: list[date], X_cols: list[str], use_log1p: bool) -> list[float]:
    train = df_hist.copy()
    train["y"] = pd.to_numeric(train["y"], errors="coerce").fillna(0).astype(float)

    y_train = train["y"].to_numpy(dtype=float)
    y_fit = np.log1p(np.clip(y_train, 0, None)) if use_log1p else y_train

    feat_train = _build_features(train)
    X_train = np.nan_to_num(feat_train[X_cols].to_numpy(), nan=0.0, posinf=0.0, neginf=0.0)
    model.fit(X_train, y_fit)

    preds: list[float] = []
    buf = train[["fecha", "y"]].copy()

    for d in future_dates:
        buf2 = pd.concat([buf, pd.DataFrame({"fecha": [d], "y": [np.nan]})], ignore_index=True)
        feat = _build_features(buf2)
        row = np.nan_to_num(feat.iloc[[-1]][X_cols].to_numpy(), nan=0.0, posinf=0.0, neginf=0.0)

        yhat = float(model.predict(row)[0])
        if use_log1p:
            yhat = float(np.expm1(yhat))
        yhat = float(max(0.0, yhat))

        preds.append(yhat)
        buf.loc[len(buf)] = {"fecha": d, "y": yhat}

    return preds


def _rf_forecast_next_month_daily_to_monthly(
    df_daily: pd.DataFrame,
    end_month: date,
    window_days: int = 180,
    test_days: int = 50,      # << CAMBIO: 50
    max_window_days: int = 365,
    min_train_days: int = 60,
    round_int_output: bool = True,
    horizon_m: int = 1,
) -> ForecastResult:
    end_day = _month_end(end_month)
    eff_window = int(max(30, min(max_window_days, window_days)))
    start_day = end_day - timedelta(days=eff_window - 1)

    all_days = pd.DataFrame({"fecha": _date_range(start_day, end_day)})
    df = all_days.merge(df_daily, on="fecha", how="left")
    df["y"] = pd.to_numeric(df["y"], errors="coerce").fillna(0).astype(float)

    if len(df) < min_train_days:
        nm = _next_month_first(end_month)
        dias_nm = calendar.monthrange(nm.year, nm.month)[1]
        yhat_day = float(df["y"].tail(7).mean()) if len(df) else 0.0
        month_pred = yhat_day * float(dias_nm)
        return ForecastResult(
            label=nm.strftime("%Y-%m"),
            next_value=round(month_pred, 0),
            x_hist=[d.strftime("%Y-%m-%d") for d in df["fecha"]],
            y_hist=[float(v) for v in df["y"]],
            x_fc=[],
            y_fc=[],
            model="Fallback: MA7 (daily→monthly)",
            metrics={"note": "insufficient_history", "n_days": int(len(df))},
        )

    X_cols = [
        "t", "dow", "month", "is_weekend", "sin_doy", "cos_doy",
        "lag1", "lag7", "lag14", "lag28",
        "ma7", "ma14", "ma28"
    ]

    metrics: dict = {}

    if len(df) >= (min_train_days + test_days):
        df_train = df.iloc[:-test_days].copy()
        df_test = df.iloc[-test_days:].copy()

        future_bt = [d for d in df_test["fecha"].to_list()]

        m_bt, name_bt = _train_regressor(is_count=True)
        use_log1p_bt = ("Poisson" not in name_bt)

        y_pred_bt = _fit_predict_recursive(
            model=m_bt,
            df_hist=df_train[["fecha", "y"]],
            future_dates=future_bt,
            X_cols=X_cols,
            use_log1p=use_log1p_bt,
        )

        y_true_bt = df_test["y"].to_numpy(dtype=float)
        y_pred_bt_np = np.asarray(y_pred_bt, dtype=float)

        err = y_true_bt - y_pred_bt_np
        mae = float(np.mean(np.abs(err)))
        rmse = float(np.sqrt(np.mean(err ** 2)))
        mape = _safe_mape(y_true_bt, y_pred_bt_np)
        smape = _smape(y_true_bt, y_pred_bt_np)

        metrics = {
            "test_days": int(test_days),
            "test_from": df_test["fecha"].iloc[0].isoformat(),
            "test_to": df_test["fecha"].iloc[-1].isoformat(),
            "mae": round(mae, 3),
            "rmse": round(rmse, 3),
            "mape_safe": round(mape, 6),
            "smape": round(smape, 6),
            "use_log1p": bool(use_log1p_bt),
            "train_days": int(len(df_train)),
            "total_days": int(len(df)),
        }

    ##nm_first = _next_month_first(end_month)
    ##nm_last = _month_end(nm_first)
    ##future_days = _date_range(nm_first, nm_last)

    future_days = _future_days_for_horizon(end_month, horizon_m)
    if not future_days:
        nm_first = _next_month_first(end_month)
        future_days = _date_range(nm_first, _month_end(nm_first))

    m_fc, name_fc = _train_regressor(is_count=True)
    use_log1p_fc = ("Poisson" not in name_fc)

    y_pred_daily = _fit_predict_recursive(
        model=m_fc,
        df_hist=df[["fecha", "y"]],
        future_dates=future_days,
        X_cols=X_cols,
        use_log1p=use_log1p_fc,
    )


    if round_int_output:
        y_pred_daily = [float(int(round(v))) for v in y_pred_daily]

    monthly_fc = _aggregate_daily_to_monthly(future_days, y_pred_daily)
    month_pred = float(np.sum(np.asarray(y_pred_daily, dtype=float)))


    # next_value: el primer mes del horizonte
    first_month_total = monthly_fc[0]["total"] if monthly_fc else float(np.sum(np.asarray(y_pred_daily, dtype=float)))

    nm_first = _next_month_first(end_month)
    return ForecastResult(
        label=nm_first.strftime("%Y-%m"),
        next_value=float(first_month_total),
        x_hist=[d.strftime("%Y-%m-%d") for d in df["fecha"]],
        y_hist=[float(v) for v in df["y"]],
        x_fc=[d.strftime("%Y-%m-%d") for d in future_days],
        y_fc=[float(v) for v in y_pred_daily],
        model=name_fc + " + recursive",
        metrics={
            **metrics,
            "horizon_m": int(horizon_m),
            "monthly_fc": monthly_fc  # <-- clave para tu front (barras por mes)
        },
    )


def _predict_next_month_linear_monthly(df_m: pd.DataFrame, next_label: str) -> ForecastResult:
    if df_m.empty:
        return ForecastResult(
            label=next_label, next_value=0.0,
            x_hist=[], y_hist=[],
            x_fc=[next_label], y_fc=[0.0],
            model="Monthly: empty",
            metrics={"note": "empty_series"}
        )

    y = df_m["y"].to_list()
    x_hist = df_m["periodo"].to_list()

    if len(y) == 1:
        yhat = float(y[0])
        model = "Monthly: repeat(1)"
    else:
        x = np.arange(1, len(y) + 1, dtype=float)
        coef = np.polyfit(x, np.array(y, dtype=float), 1)
        yhat = max(0.0, float(coef[0] * (len(y) + 1) + coef[1]))
        model = f"Monthly: linear({len(y)})"

    yhat_r = float(round(yhat, 0))
    return ForecastResult(
        label=next_label,
        next_value=yhat_r,
        x_hist=x_hist,
        y_hist=[float(v) for v in y],
        x_fc=[next_label],
        y_fc=[yhat_r],
        model=model,
        metrics={"note": "simple_linear"}
    )


# =============================================================================
# Stock / riesgos (sin cambios funcionales)
# =============================================================================
def _today() -> date:
    return date.today()


def _safe_float(x, default=0.0) -> float:
    try:
        if x is None:
            return float(default)
        return float(x)
    except Exception:
        return float(default)


def _safe_int(x, default=0) -> int:
    try:
        if x is None:
            return int(default)
        return int(float(x))
    except Exception:
        return int(default)


def _days_until(d: date) -> int:
    return (d - _today()).days


def _risk_level(p: float) -> str:
    if p >= 0.75:
        return "ALTO"
    if p >= 0.40:
        return "MEDIO"
    return "BAJO"


def _fetch_biologicos_stock_rpc() -> list[dict]:
    rows = supabase.rpc("biologicos_stock_activo", {}).execute().data or []
    out: list[dict] = []
    for r in rows:
        frascos = _safe_int(r.get("frascos"), 0)
        if frascos <= 0:
            continue
        cad = None
        try:
            cad = pd.to_datetime(r.get("fecha_caducidad")).date() if r.get("fecha_caducidad") else None
        except Exception:
            cad = None
        out.append({
            "id": r.get("id_biologico"),
            "vacuna": (r.get("nombre_biologico") or "").strip(),
            "lote": (r.get("lote") or "").strip(),
            "fecha_caducidad": cad,
            "frascos": frascos,
            "dosis_por_frasco": _safe_float(r.get("dosis_por_frasco"), 0.0),
            "frascos_por_caja": _safe_int(r.get("frascos_por_caja"), 0),
            "cajas": _safe_int(r.get("cajas"), 0),
        })
    return out


def _fetch_insumos_stock_rpc() -> list[dict]:
    rows = supabase.rpc("insumos_stock_activo", {}).execute().data or []
    out: list[dict] = []
    for r in rows:
        unidades = _safe_float(r.get("unidades"), 0.0)
        if unidades <= 0:
            continue
        cad = None
        try:
            cad = pd.to_datetime(r.get("fecha_caducidad")).date() if r.get("fecha_caducidad") else None
        except Exception:
            cad = None
        out.append({
            "id": r.get("id_insumo"),
            "categoria": (r.get("categoria") or "").strip().upper(),
            "nombre_tipo": (r.get("nombre_tipo") or "").strip(),
            "lote": (r.get("lote") or "").strip(),
            "fecha_caducidad": cad,
            "unidades": unidades,
            "packs": _safe_int(r.get("packs"), 0),
        })
    return out


def _alloc_future_daily_by_share(y_fc: list[float], share: float) -> list[float]:
    s = max(0.0, float(share))
    return [max(0.0, float(v) * s) for v in (y_fc or [])]


def _sum_first_n(xs: list[float], n: int) -> float:
    if not xs or n <= 0:
        return 0.0
    return float(np.sum(np.array(xs[:n], dtype=float)))


def _calc_recomendaciones(end_month: date, r_total: ForecastResult, r_people: ForecastResult, window_start: date, window_end: date) -> dict:
    nm_first = _next_month_first(end_month)
    dias_nm = calendar.monthrange(nm_first.year, nm_first.month)[1]

    y_fc_total = list(r_total.y_fc or [])
    if not y_fc_total and (r_total.next_value is not None):
        daily = float(r_total.next_value) / float(dias_nm) if dias_nm else 0.0
        y_fc_total = [daily] * dias_nm

    y_fc_people = list(r_people.y_fc or [])
    if not y_fc_people and (r_people.next_value is not None):
        daily = float(r_people.next_value) / float(dias_nm) if dias_nm else 0.0
        y_fc_people = [daily] * dias_nm

    rows = supabase.rpc(RPC_DOSIS_VACUNA_DIA_OLD, {
        "p_fecha_desde": window_start.isoformat(),
        "p_fecha_hasta": window_end.isoformat(),
    }).execute().data or []

    by_vac: dict[str, float] = {}
    total_hist = 0.0
    for r in rows:
        vac = (r.get("vacuna") or "").strip().upper()
        d = float(r.get("dosis") or 0.0)
        if not vac:
            continue
        by_vac[vac] = by_vac.get(vac, 0.0) + d
        total_hist += d

    shares: dict[str, float] = {}
    if total_hist > 0:
        for vac, d in by_vac.items():
            shares[vac] = d / total_hist

    biologicos = _fetch_biologicos_stock_rpc()
    bio_by_vac: dict[str, list[dict]] = {}
    for b in biologicos:
        vac_u = (b["vacuna"] or "").strip().upper()
        bio_by_vac.setdefault(vac_u, []).append(b)

    bio_riesgos: list[dict] = []
    bio_pedidos: list[dict] = []

    def ss_10pct(dem30: float) -> float:
        return 0.10 * max(0.0, dem30)

    dem30_total = _sum_first_n(y_fc_total, min(30, len(y_fc_total)))

    for vac_u, lots in bio_by_vac.items():
        share = float(shares.get(vac_u, 0.0))
        y_fc_vac = _alloc_future_daily_by_share(y_fc_total, share)
        dem30 = _sum_first_n(y_fc_vac, min(30, len(y_fc_vac))) if share > 0 else 0.0

        stock_dosis = 0.0
        for b in lots:
            stock_dosis += float(b["frascos"]) * float(b["dosis_por_frasco"] or 0.0)

        if dem30 > 0:
            deficit = max(0.0, dem30 - stock_dosis)
            p_quiebre = min(1.0, deficit / dem30)
        else:
            p_quiebre = 0.0

        p_venc_max = 0.0
        lotes_det: list[dict] = []
        for b in lots:
            cad = b["fecha_caducidad"]
            if cad is None:
                continue
            dias = _days_until(cad)
            if dias <= 0:
                p_venc = 1.0
            else:
                cons_hasta = _sum_first_n(y_fc_vac, min(dias, len(y_fc_vac))) if share > 0 else 0.0
                stock_lote_dosis = float(b["frascos"]) * float(b["dosis_por_frasco"] or 0.0)
                if stock_lote_dosis <= 0:
                    p_venc = 0.0
                elif cons_hasta <= 0:
                    p_venc = 1.0
                else:
                    sobrante = max(0.0, stock_lote_dosis - cons_hasta)
                    p_venc = min(1.0, sobrante / stock_lote_dosis)

            p_venc_max = max(p_venc_max, p_venc)
            lotes_det.append({
                "lote": b["lote"],
                "fecha_caducidad": cad.isoformat() if cad else None,
                "dias_a_caducar": dias,
                "stock_frascos": int(b["frascos"]),
                "stock_dosis": float(b["frascos"]) * float(b["dosis_por_frasco"] or 0.0),
                "p_vencimiento": round(float(p_venc), 3),
                "nivel_vencimiento": _risk_level(float(p_venc)),
            })

        bio_riesgos.append({
            "vacuna": vac_u,
            "demanda_30d_est": round(float(dem30), 1),
            "stock_dosis_est": round(float(stock_dosis), 1),
            "p_quiebre_30d": round(float(p_quiebre), 3),
            "nivel_quiebre": _risk_level(float(p_quiebre)),
            "p_vencimiento": round(float(p_venc_max), 3),
            "nivel_vencimiento": _risk_level(float(p_venc_max)),
            "lotes": lotes_det,
        })

        ss = ss_10pct(dem30)
        pedido_dosis = max(0.0, (dem30 + ss) - stock_dosis)
        dosis_por_frasco = float(lots[0]["dosis_por_frasco"] or 0.0) if lots else 0.0
        pedido_frascos = int(math.ceil(pedido_dosis / dosis_por_frasco)) if dosis_por_frasco > 0 else 0

        bio_pedidos.append({
            "vacuna": vac_u,
            "pedido_dosis": round(float(pedido_dosis), 1),
            "pedido_frascos": int(pedido_frascos),
            "stock_seguridad_dosis": round(float(ss), 1),
        })

    insumos = _fetch_insumos_stock_rpc()

    total_dosis_nm = float(r_total.next_value or (np.sum(y_fc_total) if y_fc_total else 0.0))
    total_people_nm = float(r_people.next_value or (np.sum(y_fc_people) if y_fc_people else 0.0))

    demanda_ins_cat = {
        "JERINGAS": total_dosis_nm,
        "GUANTES": total_people_nm,
        "ALCOHOL": total_dosis_nm * 1.0,
        "ALGODON": float(int(math.ceil(total_dosis_nm / 350.0))) if total_dosis_nm > 0 else 0.0,
    }

    ins_riesgos: list[dict] = []
    ins_pedidos: list[dict] = []

    ins_by_cat: dict[str, list[dict]] = {}
    for it in insumos:
        ins_by_cat.setdefault(it["categoria"], []).append(it)

    dias_nm = calendar.monthrange(_next_month_first(end_month).year, _next_month_first(end_month).month)[1]

    for cat, items in ins_by_cat.items():
        dem = float(demanda_ins_cat.get(cat, 0.0))
        stock = float(np.sum([float(i["unidades"]) for i in items]))

        if dem > 0:
            deficit = max(0.0, dem - stock)
            p_quiebre = min(1.0, deficit / dem)
        else:
            p_quiebre = 0.0

        p_venc_max = 0.0
        lotes_det: list[dict] = []
        for it in items:
            cad = it["fecha_caducidad"]
            if cad is None:
                continue
            dias = _days_until(cad)
            if dias <= 0:
                p_venc = 1.0
            else:
                daily = (dem / float(dias_nm)) if dias_nm else 0.0
                cons_hasta = daily * float(min(dias, dias_nm))
                stock_lote = float(it["unidades"])
                if stock_lote <= 0:
                    p_venc = 0.0
                elif cons_hasta <= 0:
                    p_venc = 1.0
                else:
                    sobrante = max(0.0, stock_lote - cons_hasta)
                    p_venc = min(1.0, sobrante / stock_lote)

            p_venc_max = max(p_venc_max, p_venc)
            lotes_det.append({
                "lote": it["lote"],
                "fecha_caducidad": cad.isoformat() if cad else None,
                "dias_a_caducar": dias,
                "stock_unidades": float(it["unidades"]),
                "p_vencimiento": round(float(p_venc), 3),
                "nivel_vencimiento": _risk_level(float(p_venc)),
            })

        ins_riesgos.append({
            "categoria": cat,
            "demanda_nm_est": round(float(dem), 1),
            "stock_unidades": round(float(stock), 1),
            "p_quiebre_nm": round(float(p_quiebre), 3),
            "nivel_quiebre": _risk_level(float(p_quiebre)),
            "p_vencimiento": round(float(p_venc_max), 3),
            "nivel_vencimiento": _risk_level(float(p_venc_max)),
            "lotes": lotes_det,
        })

        ss = 0.10 * max(0.0, dem)
        pedido = max(0.0, (dem + ss) - stock)
        ins_pedidos.append({
            "categoria": cat,
            "pedido_unidades": round(float(pedido), 1),
            "stock_seguridad": round(float(ss), 1),
        })

    bio_riesgos.sort(key=lambda r: (r["p_quiebre_30d"], r["p_vencimiento"]), reverse=True)
    ins_riesgos.sort(key=lambda r: (r["p_quiebre_nm"], r["p_vencimiento"]), reverse=True)

    kpis = {
        "bio_riesgo_quiebre_alto": sum(1 for r in bio_riesgos if r["nivel_quiebre"] == "ALTO"),
        "bio_riesgo_venc_alto": sum(1 for r in bio_riesgos if r["nivel_vencimiento"] == "ALTO"),
        "ins_riesgo_quiebre_alto": sum(1 for r in ins_riesgos if r["nivel_quiebre"] == "ALTO"),
        "ins_riesgo_venc_alto": sum(1 for r in ins_riesgos if r["nivel_vencimiento"] == "ALTO"),
        "demanda_30d_total_est": round(float(dem30_total), 1),
        "demanda_nm_total_est": round(float(total_dosis_nm), 1),
    }

    return {
        "kpis": kpis,
        "biologicos_riesgo": bio_riesgos,
        "biologicos_pedido": bio_pedidos,
        "insumos_riesgo": ins_riesgos,
        "insumos_pedido": ins_pedidos,
        "nota": "Riesgos: stock RPC + forecast + FEFO."
    }



# =============================================================================
# Bundle INSUMOS ESTIMADOS
# =============================================================================

def insumos_estimados_bundle(periodo: str, vacuna: str | None = None) -> dict:
    end_month = _parse_ym(periodo)
    if not end_month:
        return {"ok": False, "error": "periodo inválido"}

    mes_start = end_month
    mes_end = _month_end(end_month)

    block = _calc_insumos_estimados_diario(mes_start, mes_end, vacuna=vacuna)
    return {"ok": True, "periodo": end_month.strftime("%Y-%m"), **block}


# =============================================================================
# Bundle principal PREDICCION
# =============================================================================
def predict_ml_bundle(periodo: str | None, vacuna: str | None = None, window_days: int = 180, horizon_m: int = 1) -> dict:

    end_month = _parse_ym(periodo)
    if not end_month:
        today = date.today()
        end_month = date(today.year, today.month, 1)

    end_day = _month_end(end_month)
    start_day = end_day - timedelta(days=window_days - 1)


    end_day = _month_end(end_month)
    start_day = end_day - timedelta(days=window_days - 1)

    # >>> FIX: Insumos usados diarios SOLO para el mes seleccionado <<<
    ##mes_start = end_month                 # YYYY-MM-01
    ##mes_end   = end_day                   # fin del mes

    ##insumos_estimados = _calc_insumos_estimados_diario(mes_start, mes_end, vacuna=vacuna)


    # -------------------------------------------------------------------------
    # 1) INSUMOS ESTIMADOS (histórico) -> OLD
    # -------------------------------------------------------------------------
    #insumos_estimados = _calc_insumos_estimados_diario(start_day, end_day, vacuna=vacuna)
    pie_title = f"Jeringas por tipo – {vacuna}" if (vacuna and str(vacuna).strip()) else "Jeringas por tipo (total)"

    # -------------------------------------------------------------------------
    # 2) JERINGAS forecast (doses) -> NEW (NO TOCAR)
    # -------------------------------------------------------------------------
    df_total_new = _fetch_reporte_diario_new("TOTAL_DIA", start_day, end_day)
    r_total = _rf_forecast_next_month_daily_to_monthly(
        df_total_new, end_month,
        window_days=window_days,
        test_days=50,
        max_window_days=365,
        min_train_days=60,
        round_int_output=True,
        horizon_m=int(horizon_m),
    )

    # -------------------------------------------------------------------------
    # 3) GUANTES forecast -> out.people (NEW) (NO TOCAR)
    #    Esto es lo que tu front usa para el gráfico de guantes.
    # -------------------------------------------------------------------------
    df_people_new = _fetch_reporte_diario_new("PERSONAS_UNICAS_DIA", start_day, end_day)
    r_people_guantes = _rf_forecast_next_month_daily_to_monthly(
        df_people_new, end_month,
        window_days=window_days,
        test_days=50,
        max_window_days=365,
        min_train_days=60,
        round_int_output=True,
        horizon_m=int(horizon_m),
    )

    # -------------------------------------------------------------------------
    # 4) PERSONAS plot "como antes" -> people_plot (OLD pipeline)
    #    (no afecta guantes, porque guantes sigue usando out.people)
    # -------------------------------------------------------------------------
    df_people_old = _fetch_reporte_diario_old("PERSONAS_UNICAS_DIA", start_day, end_day)
    df_people_m = _fetch_people_mensual_ultimos(end_month, max_meses=6)
    next_lbl_people = _next_month_first(end_month).strftime("%Y-%m")

    # fallback mensual por proxy si lo mensual está pobre
    if df_people_m.empty or float(df_people_m["y"].max() if not df_people_m.empty else 0.0) < 100.0:
        df_people_long = _fetch_reporte_diario_old("PERSONAS_UNICAS_DIA", end_day - timedelta(days=240), end_day)
        df_people_m_proxy = _people_monthly_proxy_from_daily(df_people_long, months_back=6)
        if (not df_people_m_proxy.empty) and (
            float(df_people_m_proxy["y"].max()) > float(df_people_m["y"].max() if not df_people_m.empty else 0.0)
        ):
            df_people_m = df_people_m_proxy

    r_people_m = _predict_next_month_linear_monthly(df_people_m, next_lbl_people)

    nm_first = _next_month_first(end_month)
    nm_last = _month_end(nm_first)

    # patrón por DOW (como antes)
    pattern_days = 56
    pattern_start = end_day - timedelta(days=pattern_days - 1)
    df_people_pattern = _fetch_reporte_diario_old("PERSONAS_UNICAS_DIA", pattern_start, end_day)
    dow_w = _dow_pattern_weights(df_people_pattern)

    # coherencia mínima con dosis (OLD para ratio + NEW para doses pred ya está)
    df_total_old = _fetch_reporte_diario_old("TOTAL_DIA", start_day, end_day)
    ratio = _ratio_doses_per_person(df_total_old, df_people_old)
    people_floor = float(r_total.next_value or 0.0) / float(ratio) if ratio > 0 else 0.0

    next_people = float(r_people_m.next_value or 0.0)
    if people_floor > 0.0:
        next_people = max(next_people, 0.6 * float(people_floor))

    y_fc_people_int = _alloc_month_total_by_dow(next_people, nm_first, nm_last, dow_w)

    r_people_plot = ForecastResult(
        label=next_lbl_people,
        next_value=float(round(next_people, 0)),
        x_hist=[d.strftime("%Y-%m-%d") for d in df_people_old["fecha"]],
        y_hist=[float(v) for v in df_people_old["y"]],
        x_fc=[d.strftime("%Y-%m-%d") for d in _date_range(nm_first, nm_last)],
        y_fc=[float(v) for v in y_fc_people_int],
        model="People(plot): monthly linear + dow pattern + coherence floor",
        metrics={
            "people_month_hist_pts": int(len(df_people_m)),
            "people_pattern_days": int(len(df_people_pattern)),
            "people_month_total_raw": float(r_people_m.next_value or 0.0),
            "people_floor_from_doses": float(people_floor),
            "doses_per_person_ratio": float(ratio),
            "people_next_final": float(round(next_people, 0)),
        }
    )

    # -------------------------------------------------------------------------
    # 5) Recomendaciones (deben basarse en forecast que gobierna guantes)
    #    => usa r_people_guantes (no el plot)
    # -------------------------------------------------------------------------
    recomendaciones = _calc_recomendaciones(
        end_month=end_month,
        r_total=r_total,
        r_people=r_people_guantes,
        window_start=start_day,
        window_end=end_day
    )

    # -------------------------------------------------------------------------
    # 6) BIO / INS (test_days=50 en los que entrenan)
    # -------------------------------------------------------------------------
    df_bio = _fetch_mov_diario("BIOLOGICO", start_day, end_day)
    r_bio = _rf_forecast_next_month_daily_to_monthly(
        df_bio, end_month,
        window_days=window_days,
        test_days=50,
        max_window_days=365,
        min_train_days=60,
        round_int_output=True,
    )

    p_from_m = (end_month - timedelta(days=185)).strftime("%Y-%m")
    p_to_m = end_month.strftime("%Y-%m")
    df_ins_m = _fetch_mov_mensual("INSUMO", p_from_m, p_to_m)
    next_lbl = _next_month_first(end_month).strftime("%Y-%m")
    r_ins = _predict_next_month_linear_monthly(df_ins_m, next_lbl)

    # Top vacunas (sin cambios)
    p_from = (end_month - timedelta(days=95)).strftime("%Y-%m")
    p_to = end_month.strftime("%Y-%m")
    rows_top = supabase.rpc("dashboard_top_vacunas_mes", {
        "p_periodo_desde": p_from,
        "p_periodo_hasta": p_to,
        "p_limit": 500
    }).execute().data or []

    df_top = pd.DataFrame(rows_top) if rows_top else pd.DataFrame(columns=["periodo", "vacuna", "valor"])
    pred_bio_top: list[dict] = []
    if not df_top.empty:
        df_top["valor"] = df_top["valor"].apply(_num_clean)
        df_top["valor"] = pd.to_numeric(df_top["valor"], errors="coerce").fillna(0.0)

        def _k(p):
            y, m = str(p).split("-")
            return int(y) * 100 + int(m)

        df_top["k"] = df_top["periodo"].apply(_k)

        for vac, g in df_top.groupby("vacuna"):
            g = g.sort_values("k")
            yv = g["valor"].to_list()[-3:]

            if len(yv) == 1:
                pv = float(yv[0])
            else:
                x = np.arange(1, len(yv) + 1, dtype=float)
                coef = np.polyfit(x, np.array(yv, dtype=float), 1)
                pv = max(0.0, float(coef[0] * (len(yv) + 1) + coef[1]))

            pred_bio_top.append({
                "vacuna": vac,
                "pred_dosis": float(round(pv, 0)),
                "hist_dosis": [float(v) for v in yv],
                "unidad": "DOSIS"
            })

        pred_bio_top.sort(key=lambda r: r["pred_dosis"], reverse=True)
        pred_bio_top = pred_bio_top[:10]


    future_months = []
    try:
        monthly_fc_doses = (r_total.metrics or {}).get("monthly_fc", []) or []
        future_months = [m.get("periodo") for m in monthly_fc_doses if m.get("periodo")]
    except Exception:
        future_months = []



    return {
        "ok": True,
        "next_label": _next_month_first(end_month).strftime("%Y-%m"),  
        "future_months": future_months,                               
        "horizon_m": int(horizon_m), 
        #"insumos_estimados": insumos_estimados,
        "jeringas_pie_title": pie_title,

        # >>> NO TOCAR (guantes usa esto) <<<
        "people": {
            "label": r_people_guantes.label,
            "next": r_people_guantes.next_value,
            "model": r_people_guantes.model,
            "metrics": r_people_guantes.metrics,
            "series": {
                "x_hist": r_people_guantes.x_hist, "y_hist": r_people_guantes.y_hist,
                "x_fc": r_people_guantes.x_fc, "y_fc": r_people_guantes.y_fc
            },
        },

        # >>> NUEVO: solo para el gráfico KPI/Personas (como antes) <<<
        "people_plot": {
            "label": r_people_plot.label,
            "next": r_people_plot.next_value,
            "model": r_people_plot.model,
            "metrics": r_people_plot.metrics,
            "series": {
                "x_hist": r_people_plot.x_hist, "y_hist": r_people_plot.y_hist,
                "x_fc": r_people_plot.x_fc, "y_fc": r_people_plot.y_fc
            },
        },

        # >>> NO TOCAR (jeringas forecast usa esto) <<<
        "doses": {
            "label": r_total.label,
            "next": r_total.next_value,
            "model": r_total.model,
            "metrics": r_total.metrics,
            "series": {
                "x_hist": r_total.x_hist, "y_hist": r_total.y_hist,
                "x_fc": r_total.x_fc, "y_fc": r_total.y_fc
            },
        },

        "bio": {
            "label": r_bio.label,
            "next": r_bio.next_value,
            "model": r_bio.model,
            "metrics": r_bio.metrics,
            "series": {
                "x_hist": r_bio.x_hist, "y_hist": r_bio.y_hist,
                "x_fc": r_bio.x_fc, "y_fc": r_bio.y_fc
            },
        },
        "ins": {
            "label": r_ins.label,
            "next": r_ins.next_value,
            "model": r_ins.model,
            "metrics": r_ins.metrics,
            "series": {
                "x_hist": r_ins.x_hist, "y_hist": r_ins.y_hist,
                "x_fc": r_ins.x_fc, "y_fc": r_ins.y_fc
            },
            "trained_until": end_month.strftime("%Y-%m"),
        },

        "pred_bio_top": pred_bio_top,
        "recomendaciones": recomendaciones,

        "meta": {
            "rpc_old_series": RPC_SERIES_DIARIA_OLD,
            "rpc_new_series": RPC_SERIES_DIARIA_NEW,
            "rpc_old_dosis_vac": RPC_DOSIS_VACUNA_DIA_OLD,
            "window_days": int(window_days),
            "test_days": 50,
        }
    }
