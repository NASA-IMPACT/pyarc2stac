import json
from collections import defaultdict

import numpy as np
import requests

from .utils import convert_to_datetime


def _convert_to_esri_polygon_geometry(aoi):
    # aoi is a FeatureCollection from pydantic_geoson
    aoi_geometry = {
        "rings": aoi.features[0].geometry.coordinates,
        "spatialReference": {"wkid": 4326},
    }
    return aoi_geometry


def convert_to_milliseconds(dt):
    """Converts a date-time string in 'YYYY-MM-DD HH:MM:SS' format to milliseconds since epoch."""
    milliseconds_since_epoch = int(dt.timestamp() * 1000)
    return milliseconds_since_epoch


# Function to fetch time series data
def fetch_timeseries(image_service_url, variable_name, datetime_range, aoi):
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
    # Extract values and StdTime
    extracted_data = defaultdict(list)

    for item in samples:
        value = float(item["value"])
        std_time = item["attributes"]["StdTime"]
        extracted_data[std_time].append(value)

    # Calculate statistics
    timeseries = {}

    for std_time, values in extracted_data.items():
        values_array = np.array(values)
        stats = {
            "mean": np.mean(values_array),
            "min": np.min(values_array),
            "max": np.max(values_array),
            "std": np.std(values_array),
            "median": np.median(values_array),
            "sum": np.sum(values_array),
        }
        date_time_format = convert_to_datetime([std_time])[0]
        date_time_iso = f"{date_time_format.isoformat()}Z"
        timeseries[date_time_iso] = stats

    return timeseries
    # else:
    #     # raise exception
    #     raise Exception("Failed getSamples", response)
