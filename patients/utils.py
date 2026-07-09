from datetime import timedelta
from math import sqrt
from .models import GlucoseLog, PatientProfile


def compute_population_stats(values):
    if not values:
        return None, None

    mean = float(sum(values)) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return mean, sqrt(variance)


def calculate_linear_regression(x_values, y_values):
    if len(x_values) != len(y_values) or len(x_values) < 2:
        return None, None

    x_mean = float(sum(x_values)) / len(x_values)
    y_mean = float(sum(y_values)) / len(y_values)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values))
    denominator = sum((x - x_mean) ** 2 for x in x_values)

    if denominator == 0:
        return None, None

    slope = numerator / denominator
    intercept = y_mean - (slope * x_mean)
    return slope, intercept


def compute_patient_glucose_stats(user):
    """Return glucose log data and anomaly flags for a patient.

    Args:
        user: Django User instance.

    Returns:
        tuple: (cleaned_data, anomalies)
            cleaned_data: list of dicts ordered by timestamp with rolling average and std
            anomalies: list of dicts for entries flagged as anomalies
    """
    try:
        profile = user.patient_profile
    except PatientProfile.DoesNotExist:
        return [], []

    logs = (
        GlucoseLog.objects.filter(profile=profile)
        .order_by('timestamp')
        .values('id', 'timestamp', 'glucose_level', 'meal_context')
    )

    if not logs:
        return [], []

    cleaned_data = []
    anomalies = []

    ordered_logs = list(logs)
    window_start = 0

    for index, row in enumerate(ordered_logs):
        timestamp = row['timestamp']
        while ordered_logs[window_start]['timestamp'] < timestamp - timedelta(days=7):
            window_start += 1

        window_values = [
            float(log['glucose_level'])
            for log in ordered_logs[window_start:index + 1]
        ]
        rolling_average, rolling_std = compute_population_stats(window_values)
        anomaly = False
        if rolling_average is not None and rolling_std is not None and rolling_std > 0:
            anomaly = abs(float(row['glucose_level']) - rolling_average) > (2 * rolling_std)

        entry = {
            'id': int(row['id']),
            'timestamp': timestamp.isoformat(),
            'timestamp_display': timestamp.strftime('%Y-%m-%d %H:%M'),
            'glucose_level': int(row['glucose_level']),
            'meal_context': row['meal_context'],
            'rolling_average': float(round(rolling_average or 0, 2)),
            'rolling_std': float(round(rolling_std or 0, 2)),
            'anomaly': anomaly,
        }
        cleaned_data.append(entry)
        if entry['anomaly']:
            anomalies.append(entry)

    return cleaned_data, anomalies
