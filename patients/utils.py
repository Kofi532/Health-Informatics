import numpy as np
import pandas as pd
from .models import GlucoseLog, PatientProfile


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

    df = pd.DataFrame.from_records(logs)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp')
    df = df.set_index('timestamp')

    rolling = df['glucose_level'].rolling('7D', min_periods=1)
    df['rolling_average'] = rolling.mean()
    df['rolling_std'] = rolling.std().fillna(0)

    df['anomaly'] = np.abs(df['glucose_level'] - df['rolling_average']) > (2 * df['rolling_std'])

    cleaned_data = []
    anomalies = []

    for timestamp, row in df.reset_index().iterrows():
        entry = {
            'id': int(row['id']),
            'timestamp': row['timestamp'].isoformat(),
            'glucose_level': int(row['glucose_level']),
            'meal_context': row['meal_context'],
            'rolling_average': float(round(row['rolling_average'], 2)),
            'rolling_std': float(round(row['rolling_std'], 2)),
            'anomaly': bool(row['anomaly']),
        }
        cleaned_data.append(entry)
        if entry['anomaly']:
            anomalies.append(entry)

    return cleaned_data, anomalies
