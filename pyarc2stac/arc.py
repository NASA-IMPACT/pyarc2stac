import datetime
import requests
import isodate
from pystac import SpatialExtent, TemporalExtent, Collection, Extent, Summaries, Link
from pystac.extensions.datacube import DatacubeExtension, Variable, Dimension
from .utils import get_data, convert_to_datetime, transform_projection
from typing import List
import re
import xml.etree.ElementTree as ET


def get_periodicity(cube_dimensions=None):
    # TODO: the dashboard uses `dashboard:is_periodic` as a means to create the unit timestamp
    # the ImageServer has these unit timestamps already
    # so we might just set it to False always
    # but we still need to figure out the `dashboard:time_density`
    return False, "year"
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


def convert_map_server_to_collection_stac(server_url, collection_name):
    json_data = get_data(f"{server_url}?f=pjson")
    if json_data.get("error"):
        raise Exception(json_data)
    collection_id = json_data.get("name", collection_name)
    collection_title = json_data.get("name", collection_name)
    collection_description = json_data.get("serviceDescription", collection_title)
    spatial_ref = json_data["spatialReference"]["latestWkid"]
    xmin, ymin = json_data["fullExtent"]["xmin"], json_data["fullExtent"]["ymin"]
    xmax, ymax = json_data["fullExtent"]["xmax"], json_data["fullExtent"]["ymax"]
    collection_bbox = transform_projection(
        spatial_ref, xmin, ymin
    ) + transform_projection(spatial_ref, xmax, ymax)
    spatial_extent = SpatialExtent(bboxes=collection_bbox)
    collection_interval = [None, datetime.datetime.utcnow()]
    if json_data.get("timeInfo"):
        collection_interval = convert_to_datetime(json_data["timeInfo"]["timeExtent"])
    temporal_extent = TemporalExtent(intervals=collection_interval)
    collection_extent = Extent(spatial=spatial_extent, temporal=temporal_extent)
    collection = Collection(
        id=collection_id,
        title=collection_title,
        description=collection_description,
        extent=collection_extent,
        license="",
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
    ) = get_periodicity()

    return collection


def convert_image_server_to_collection_stac(server_url, collection_name):
    json_data = get_data(f"{server_url}?f=pjson")

    collection_id = json_data.get("name", collection_name)
    collection_title = json_data.get("name", collection_name)
    collection_description = json_data["serviceDescription"]
    datacube_variables, datacube_dimensions = get_cube_info(server_url)

    collection_bbox = [
        json_data["extent"]["xmin"],
        json_data["extent"]["ymin"],
        json_data["extent"]["xmax"],
        json_data["extent"]["ymax"],
    ]
    spatial_extent = SpatialExtent(bboxes=collection_bbox)
    collection_interval = convert_to_datetime(json_data["timeInfo"]["timeExtent"])
    temporal_extent = TemporalExtent(intervals=collection_interval)
    collection_extent = Extent(spatial=spatial_extent, temporal=temporal_extent)
    date_time_summary = get_datetime_summaries(datacube_dimensions)
    collection_summaries = Summaries(
        {"datetime": date_time_summary}, maxcount=len(date_time_summary) + 1
    )

    collection = Collection(
        id=collection_id,
        title=collection_title,
        description=collection_description,
        extent=collection_extent,
        license="",
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


def convert_to_collection_stac(server_url):
    switch_function = {
        "Image": convert_image_server_to_collection_stac,
        "Map": convert_map_server_to_collection_stac,
    }

    # use pystac to create a STAC collection
    pattern = r"services/(?P<collection_id>.*?)/(?P<server_type>(Image|Map))Server"
    re_search = re.search(pattern, server_url)
    collection_name = re_search.group("collection_id")
    server_type = re_search.group("server_type")
    collection = switch_function[server_type](
        server_url=server_url, collection_name=collection_name
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
