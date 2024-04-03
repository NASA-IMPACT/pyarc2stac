import json
from datetime import datetime

import requests

from .utils import convert_to_iso_time


def _convert_to_esri_polygon_geometry(aoi):
    aoi_geometry = {
        "rings": aoi["features"][0]["geometry"]["coordinates"],
        "spatialReference": {"wkid": 4326},
    }
    return aoi_geometry


def convert_to_milliseconds(date_time_str):
    """Converts a date-time string in 'YYYY-MM-DD HH:MM:SS' format to milliseconds since epoch."""
    dt = datetime.strptime(date_time_str, "%Y-%m-%dT%H:%M:%SZ")
    milliseconds_since_epoch = int(dt.timestamp() * 1000)
    return milliseconds_since_epoch


# Function to fetch time series data
def fetch_timeseries(image_service_url, variable_name, datetime_range, aoi):
    datetime_range = datetime_range.split(",")
    # Construct the request parameters
    params = {
        "geometry": json.dumps(_convert_to_esri_polygon_geometry(aoi)).replace(" ", ""),
        "geometryType": "esriGeometryPolygon",
        "mosaicRule": f'{{"multidimensionalDefinition":[{{"variableName":"{variable_name}"}}]}}',
        "time": f"{convert_to_milliseconds(datetime_range[0])},{convert_to_milliseconds(datetime_range[1])}",
        "interpolation": "RSP_BilinearInterpolation",
        "returnFirstValueOnly": "false",
        "sampleDistance": "",
        "sampleCount": "",
        "pixelSize": "",
        "outFields": "",
        "sliceId": "",
        "f": "pjson",
    }

    # Send a GET request to the image service
    response = requests.get(f"{image_service_url}/getSamples", params=params)
    # Check if the request was successful
    # if response.status_code == 200:
    # Extract the time series of data from the response
    data = response.json()
    samples = data["samples"]
    lookup = dict()
    counter = dict()
    for sample in samples:
        attributes = sample["attributes"]
        date_time = attributes["StdTime"]
        date_time_iso = convert_to_iso_time([date_time])[0]
        counter[date_time_iso] = counter.get(date_time_iso, 0) + 1
        lookup[date_time_iso] = lookup.get(date_time_iso, 0) + (
            (float(sample["value"]) - lookup.get(date_time_iso, 0))
            / counter[date_time_iso]
        )

    time_series = list()

    for key, val in lookup.items():
        time_series.append({"date": key, "mean": val})

    return time_series
    # else:
    #     # raise exception
    #     raise Exception("Failed getSamples", response)
