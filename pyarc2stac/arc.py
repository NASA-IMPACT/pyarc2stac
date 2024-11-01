import datetime
import requests
import isodate
from dateutil.relativedelta import relativedelta
from pystac import SpatialExtent, TemporalExtent, Collection, Extent, Summaries, Link
from pystac.extensions.datacube import DatacubeExtension, Variable, Dimension
from .utils import get_data, convert_to_datetime, transform_projection
from typing import List
import re
import xml.etree.ElementTree as ET
from pyproj import Transformer


def get_periodicity(cube_dimensions=None, time_periods="year"):
    # TODO: the dashboard uses `dashboard:is_periodic` as a means to create the unit timestamp
    # the ImageServer has these unit timestamps already
    # so we might just set it to False always
    # but we still need to figure out the `dashboard:time_density`
    return False, time_periods
    # for dimension in cube_dimensions.values():
    #     if dimension["type"] == "temporal":
    #         return (
    #             dimension["hasRegularIntervals"],
    #             dimension["intervalUnit"].lower()[:-1],
    #         )


def get_map_server_layers_rest(map_server_url):
    multi_dim = get_data(
        f"{map_server_url}/multiDimensionalInfo?returnDimensionValues=always&f=pjson"
    )
    return [layer_name["name"] for layer_name in multi_dim["layers"]]


def get_map_server_layers_wms(map_server_url):
    service_url = map_server_url.replace("/rest", "")
    url = f"{service_url}/WMSServer?request=GetCapabilities&service=WMS"
    response = requests.get(url)
    response.raise_for_status()
    xml_content = response.content

    # Parse XML content
    root = ET.fromstring(xml_content)

    # Find all Layer elements
    layers = []
    for layer in root.findall(".//{http://www.opengis.net/wms}Layer"):
        name = layer.find("{http://www.opengis.net/wms}Name")
        title = layer.find("{http://www.opengis.net/wms}Title")

        if name is not None and title is not None:
            layers.append(title.text)

    return layers


def get_mapserver_datetime_summary(collection_interval, time_interval_value, time_interval_units: str):
    """
    """

    # Convert timestamps to datetime objects
    start_date, end_date = collection_interval
    # Parse the time_interval string

    if time_interval_units == "esriTimeUnitsDays":
        iso_duration = f"{time_interval_value}d"
    elif time_interval_units == "esriTimeUnitsWeeks":
        iso_duration = f"{time_interval_value}w"
    elif time_interval_units == "esriTimeUnitsMonths":
        iso_duration = f"{time_interval_value}m"
    elif time_interval_units == "esriTimeUnitsYears":
        iso_duration = f"{time_interval_value}y"
    else:
        raise ValueError("Unsupported time interval unit")
    match = re.match(r'(\d+)([dwmy])', iso_duration)
    if not match:
        raise ValueError("Invalid time interval format. Use format like '7d', '3w', '2m', or '1y'.")

    interval_number = int(match.group(1))
    interval_type = match.group(2)
    lookup = {
        "d": "days",
        "m": "months",
        "y": "years"
    }
    if not lookup.get(interval_type):
        raise ValueError(
            "Unsupported time interval type. Use 'd' for days, 'w' for weeks, 'm' for months, 'y' for years.")

    time_periods = lookup[interval_type]
    delta = relativedelta(**{time_periods: interval_number})

    # Generate the list of datetime objects
    datetime_list = []
    current_date = start_date
    while current_date <= end_date:
        formatted_date = current_date.strftime("%Y-%m-%dT00:00:00Z")
        datetime_list.append(formatted_date)
        current_date += delta
    return time_periods.rstrip('s'), datetime_list


def get_time_interval(service_url):
    response = requests.get(service_url, params={"f": "json"})
    response.raise_for_status()
    metadata = response.json()

    time_interval_value = metadata["timeInfo"]["timeInterval"]
    time_interval_units = metadata["timeInfo"]["timeIntervalUnits"]

    # Convert the time interval to ISO 8601 format
    if time_interval_units == "esriTimeUnitsDays":
        iso_duration = f"{time_interval_value}d"
    elif time_interval_units == "esriTimeUnitsWeeks":
        iso_duration = f"{time_interval_value}w"
    elif time_interval_units == "esriTimeUnitsMonths":
        iso_duration = f"{time_interval_value}m"
    elif time_interval_units == "esriTimeUnitsYears":
        iso_duration = f"{time_interval_value}y"
    else:
        raise ValueError("Unsupported time interval unit")

    return iso_duration


def convert_map_server_to_collection_stac(server_url, collection_id, collection_title):
    json_data = get_data(f"{server_url}?f=pjson")
    if json_data.get("error"):
        raise Exception(json_data)
    collection_description = json_data.get("description") or collection_title
    spatial_ref = json_data["spatialReference"]["latestWkid"]
    xmin, ymin = json_data["fullExtent"]["xmin"], json_data["fullExtent"]["ymin"]
    xmax, ymax = json_data["fullExtent"]["xmax"], json_data["fullExtent"]["ymax"]

    collection_bbox = transform_projection(
        spatial_ref, xmin, ymin
    ) + transform_projection(spatial_ref, xmax, ymax)
    spatial_extent = SpatialExtent(bboxes=collection_bbox)
    collection_interval = [None, None]
    collection_summaries_dates = []
    time_periods = "year"
    if json_data.get("timeInfo"):
        collection_interval = convert_to_datetime(json_data["timeInfo"]["timeExtent"])
        time_interval_value = json_data["timeInfo"]["defaultTimeInterval"]
        time_interval_units = json_data["timeInfo"]["defaultTimeIntervalUnits"]
        time_periods, collection_summaries_dates = get_mapserver_datetime_summary(
            collection_interval=collection_interval,
            time_interval_value=time_interval_value,
            time_interval_units=time_interval_units)


    temporal_extent = TemporalExtent(intervals=collection_interval)
    collection_extent = Extent(spatial=spatial_extent, temporal=temporal_extent)

    collection = Collection(
        id=collection_id,
        title=collection_title,
        description=collection_description,
        extent=collection_extent,
        license=json_data.get('license', "not-applicable"),
        summaries=Summaries(
            {"datetime": collection_summaries_dates}, maxcount=len(collection_summaries_dates) + 1
        ) if collection_summaries_dates else None
    )
    try:
        # User WMS
        layers_names = get_map_server_layers_wms(map_server_url=server_url)
    except:
        # If WMS is not active
        layers_names = get_map_server_layers_rest(map_server_url=server_url)
    links = [
        {
            "href": f"{server_url.replace('/rest', '')}/WMSServer",
            "rel": "wms",
            "type": "image/png",
            "title": "Visualized through a WMS",
            "wms:layers": [*layers_names],
            "wms:styles": ["default"],
        },
    ]
    for link_data in links:
        link = Link(
            target=link_data["href"],
            rel=link_data["rel"],
            media_type=link_data["type"],
            title=link_data["title"],
        )
        if "wms:layers" in link_data:
            link.extra_fields["wms:layers"] = link_data["wms:layers"]
        if "wms:styles" in link_data:
            link.extra_fields["wms:styles"] = link_data["wms:styles"]
        collection.add_link(link)

    # Add custom extensions
    (
        collection.extra_fields["dashboard:is_periodic"],
        collection.extra_fields["dashboard:time_density"],
    ) = get_periodicity(time_periods=time_periods)

    if not collection_summaries_dates:
        collection.extra_fields["dashboard:is_timeless"] = True
    return collection


def convert_image_server_to_collection_stac(server_url, collection_id, collection_title):
    json_data = get_data(f"{server_url}?f=pjson")
    collection_description = json_data.get("description") or collection_title
    datacube_variables, datacube_dimensions = get_cube_info(server_url)

    collection_bbox = [
        json_data["extent"]["xmin"],
        json_data["extent"]["ymin"],
        json_data["extent"]["xmax"],
        json_data["extent"]["ymax"],
    ]
    spatial_extent = SpatialExtent(bboxes=collection_bbox)
    collection_interval = [None, None]
    
    time_info = json_data.get("timeInfo")
    if time_info:
        collection_interval = convert_to_datetime(time_info["timeExtent"])
    
    temporal_extent = TemporalExtent(intervals=collection_interval)    
    collection_extent = Extent(spatial=spatial_extent, temporal=temporal_extent)
    date_time_summary = get_datetime_summaries(datacube_dimensions)
    collection_summaries = Summaries(
        {"datetime": date_time_summary}, maxcount=len(date_time_summary) + 1
    ) if date_time_summary else None

    collection = Collection(
        id=collection_id,
        title=collection_title,
        description=collection_description,
        extent=collection_extent,
        license=json_data.get('license', "not-applicable"),
        summaries=collection_summaries,
    )

    # Add links to the collection
    links = [
        {
            "href": f"{server_url.replace('/rest', '')}/WMSServer",
            "rel": "wms",
            "type": "image/png",
            "title": "Visualized through a WMS",
            "wms:layers": [*datacube_variables],
            "wms:styles": ["default"],
        },
    ]
    for link_data in links:
        link = Link(
            target=link_data["href"],
            rel=link_data["rel"],
            media_type=link_data["type"],
            title=link_data["title"],
        )
        if "wms:layers" in link_data:
            link.extra_fields["wms:layers"] = link_data["wms:layers"]
        if "wms:styles" in link_data:
            link.extra_fields["wms:styles"] = link_data["wms:styles"]
        collection.add_link(link)
    # Add Datacube extension to the collection
    datacube_ext = DatacubeExtension.ext(collection, add_if_missing=True)
    # Set eDimensions and Variables to Datacube extension
    datacube_ext.variables, datacube_ext.dimensions = (
        datacube_variables,
        datacube_dimensions,
    )
    # Add custom extensions
    (
        collection.extra_fields["dashboard:is_periodic"],
        collection.extra_fields["dashboard:time_density"],
    ) = get_periodicity(datacube_dimensions)
    return collection

def convert_feature_server_to_collection_stac(
    server_url, collection_id, collection_title
):
    json_data = get_data(f"{server_url}?f=pjson")
    collection_description = json_data.get("description") or collection_title
    collection_bbox = [
        json_data["fullExtent"]["xmin"],
        json_data["fullExtent"]["ymin"],
        json_data["fullExtent"]["xmax"],
        json_data["fullExtent"]["ymax"],
    ]

    srid = json_data["fullExtent"]["spatialReference"]["latestWkid"]
    transformer = Transformer.from_crs(srid, "EPSG:4326")

    spatial_extent = SpatialExtent(
        bboxes=list(transformer.transform_bounds(*collection_bbox))
    )
    temporal_extent = TemporalExtent(intervals=[[None, None]])
    collection_extent = Extent(spatial=spatial_extent, temporal=temporal_extent)

    layers = {i["id"]: i["name"] for i in json_data["layers"]}

    collection = Collection(
        id=collection_id,
        title=collection_title,
        description=collection_description,
        extent=collection_extent,
        license=json_data.get("license", "not-applicable"),
    )

    # Add links to the collection
    link = Link(
        target=server_url,
        rel="featureserver",
        media_type="image/json",
        title="ArcGIS FeatureServer",
    )
    link.extra_fields["featureserver:layers"] = layers

    collection.add_link(link)

    return collection

def convert_to_collection_stac(server_url):
    switch_function = {
        "Image": convert_image_server_to_collection_stac,
        "Map": convert_map_server_to_collection_stac,
        "Feature":convert_feature_server_to_collection_stac,
    }

    # use pystac to create a STAC collection
    pattern = r"services/(?P<collection_id>.*?)/(?P<server_type>(Image|Map|Feature))Server"
    re_search = re.search(pattern, server_url)
    collection_name = re_search.group("collection_id")
    # STAC API doesn't support /
    collection_id = collection_name.replace('/', '_').lower()
    server_type = re_search.group("server_type")
    collection = switch_function[server_type](
        server_url=server_url, collection_id=collection_id, collection_title=collection_name
    )
    # add arcgis server url to the collection links
    server_link = Link(
        target=server_url,
        rel="via",
        media_type="text/html",
        title="Parent ArcGIS server url",
    )
    collection.add_link(server_link)
    return collection


def get_legend(
        img_url, band_ids: List | None = None, variable_name=None, rendering_rule=None
):
    band_ids_list = ",".join(band_ids) if band_ids else ""
    params = f"bandIds={band_ids_list}&variable={variable_name}&renderingRule={rendering_rule}&f=pjson"
    return get_data(f"{img_url}/legend?{params}")


def get_datetime_summaries(cube_dimensions):
    for dim in cube_dimensions.values():
        dim_dict = dim.to_dict()
        if dim_dict["type"] == "temporal":
            return dim_dict["values"]


def get_cube_mapserver_info(mapserver_url, layer_id):
    url = f"{mapserver_url}/{layer_id}?f=pjson"
    cube_data = get_data(url)
    pass


def get_cube_info(img_url):
    multi_dim = get_data(
        f"{img_url}/multiDimensionalInfo?returnDimensionValues=always&f=pjson"
    )
    variables = multi_dim.get("multidimensionalInfo", {}).get("variables", [])
    cube_variables = {}
    cube_dimensions = {}

    for index, variable in enumerate(variables):
        cube_variables[variable["name"]] = Variable(
            {
                "type": "data",
                "attrs": variable.get("attributes", {}),
                "statistics": variable["statistics"],
                "histograms": variable["histograms"],
                "unit": variable["unit"],
                "dimensions": [
                    dimension["name"] for dimension in variable["dimensions"]
                ],
            }
        )
        if index != 0:
            continue
        for dimension in variable["dimensions"]:
            dim_id = dimension["name"]
            if "Time" in dim_id:
                cube_type = "temporal"
                cube_dimensions[dim_id] = Dimension(
                    {
                        "type": cube_type,
                        "step": isodate.duration_isoformat(
                            isodate.Duration(
                                **{
                                    dimension["intervalUnit"].lower(): dimension[
                                        "interval"
                                    ]
                                }
                            )
                        ),
                        "extent": [
                            f"{extent.isoformat()}Z"
                            for extent in convert_to_datetime(dimension["extent"])
                        ],
                        "values": [
                            f"{value.isoformat()}Z"
                            for value in convert_to_datetime(dimension["values"])
                        ],
                        "hasRegularIntervals": dimension["hasRegularIntervals"],
                        "intervalUnit": dimension["intervalUnit"],
                    }
                )
            # TODO: Handle other types
    return cube_variables, cube_dimensions
