import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests
from pyproj import Transformer
from bs4 import BeautifulSoup


def strip_html(html_text):
    #Clean html text for description.
    soup = BeautifulSoup(html_text, "html.parser")
    return soup.get_text(separator=" ", strip=True)


def get_data(url):
    r = requests.get(url)
    data = r.json()
    return data


def get_xml(url) -> ET:
    r = requests.get(url)
    r.raise_for_status()
    if b"<ServiceExceptionReport" in r.content:
        error_response = ET.fromstring(r.content)
        service_exception = error_response.find("ServiceException")
        raise Exception(f"""
            ServiceException detected in response content: \n code: {service_exception.attrib.get("code")} \n message: {service_exception.text}
        """)
    return ET.fromstring(r.content)


def convert_to_datetime(times_extent):
    return [
       datetime.fromtimestamp((time_extent/1000.0), timezone.utc) for time_extent in times_extent
    ]


def transform_projection(wkid_source_proj, x, y):
    """Converts coordinates from EPSG:3857 to EPSG:4326.

    Args:
        wkid_source_proj : The projection source
        x (float): The x coordinate (longitude) in EPSG:3857.
        y (float): The y coordinate (latitude) in EPSG:3857.

    Returns:
        tuple: A tuple containing the converted coordinates (longitude, latitude) in EPSG:4326.
    """
    wkid_destination_proj = "4326"
    if wkid_source_proj == wkid_destination_proj:
        return x, y

    transformer = Transformer.from_crs(
        f"EPSG:{wkid_source_proj}", f"EPSG:{wkid_destination_proj}", always_xy=True
    )

    # Perform the transformation
    lon, lat = transformer.transform(x, y)

    return [lon, lat]
