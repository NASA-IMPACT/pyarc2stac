from datetime import datetime

import requests


def get_data(url):
    r = requests.get(url)
    data = r.json()
    return data


def convert_to_datetime(times_extent):
    return [
        datetime.utcfromtimestamp(time_extent / 1000.0) for time_extent in times_extent
    ]
