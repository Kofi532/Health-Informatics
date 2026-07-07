from datetime import timedelta
from django.utils import timezone
from .models import GlucoseLog, GlucosePrediction, PatientProfile


def generate_and_save_prediction(profile, horizon_hours=12):
    """Generate a point prediction for the next time window and save it.

    Attempts to use statsmodels AutoReg; falls back to simple moving average.
    Args:
        profile: PatientProfile instance
        horizon_hours: how many hours ahead to predict (used to set predicted_for)
    Returns:
        GlucosePrediction instance or None on failure
    """
    qs = GlucoseLog.objects.filter(profile=profile).order_by('timestamp')
    values = list(qs.values_list('glucose_level', 'timestamp'))
    if not values:
        return None

    # prepare time series arrays
    timestamps = [ts for _, ts in values]
    levels = [float(v) for v, _ in values] if False else [float(v) for v, _ in [(v, t) for v, t in values]]

    predicted_for = timezone.now() + timedelta(hours=horizon_hours)

    # try using statsmodels AutoReg
    try:
        import numpy as np
        from statsmodels.tsa.ar_model import AutoReg
        arr = np.array(levels, dtype=float)
        if len(arr) >= 5:
            model = AutoReg(arr, lags=3, old_names=False).fit()
            pred = model.predict(start=len(arr), end=len(arr))[0]
            used_model = 'auto_reg'
        else:
            pred = float(arr.mean())
            used_model = 'moving_average'
    except Exception:
        # fallback: simple moving average of last 3 values
        recent = levels[-3:]
        pred = float(sum(recent) / len(recent))
        used_model = 'moving_average_fallback'

    # save prediction
    pred_obj = GlucosePrediction.objects.create(
        profile=profile,
        target_timestamp=predicted_for,
        predicted_value=int(round(pred)),
        model=used_model,
    )

    return pred_obj
