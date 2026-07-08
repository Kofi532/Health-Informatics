from datetime import timedelta
from django.utils import timezone
from .models import GlucoseLog, GlucosePrediction, PatientProfile
from .utils import calculate_linear_regression


def generate_and_save_prediction(profile, horizon_hours=12):
    """Generate a point prediction for the next time window and save it.

    Uses a simple linear trend when enough data exists; otherwise falls back to
    a moving average.
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
    levels = [float(value) for value, _ in values]

    predicted_for = timezone.now() + timedelta(hours=horizon_hours)

    if len(levels) >= 2:
        first_ts = timestamps[0]
        hour_offsets = [
            (timestamp - first_ts).total_seconds() / 3600.0
            for timestamp in timestamps
        ]
        slope, intercept = calculate_linear_regression(hour_offsets, levels)
    else:
        slope, intercept = None, None

    if slope is not None and intercept is not None:
        future_hours = hour_offsets[-1] + horizon_hours
        pred = slope * future_hours + intercept
        used_model = 'linear_trend'
    else:
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
