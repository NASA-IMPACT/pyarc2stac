import isodate
from pystac import SpatialExtent, TemporalExtent, Collection, Extent, Summaries, Link
from pystac.extensions.datacube import DatacubeExtension, Variable, Dimension
from .utils import get_data, convert_to_datetime
from typing import List
import re

def get_periodicity(cube_dimensions):
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


def convert_to_collection_stac(image_service_url):
    json_data = get_data(f"{image_service_url}?f=pjson")
    datacube_variables, datacube_dimensions = get_cube_info(image_service_url)
    # use pystac to create a STAC collection
    pattern = r'services/(?P<collection_id>.*?)/(Image|Map)Server'
    collection_name = re.search(pattern, image_service_url).group('collection_id')
    collection_id = json_data.get("name", collection_name)
    collection_title = json_data.get("name", collection_name)
    collection_description = json_data["serviceDescription"]
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
            "href": f"{image_service_url}/WMSServer",
            "rel": "wms",
            "type": "image/png",
            "title": "Visualized through a WMS",
            "wms:layers": [*datacube_variables],
            "wms:styles": ["default"],
        }
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
    datacube_ext.variables, datacube_ext.dimensions = get_cube_info(image_service_url)
    # Add custom extensions
    (
        collection.extra_fields["dashboard:is_periodic"],
        collection.extra_fields["dashboard:time_density"],
    ) = get_periodicity(datacube_dimensions)
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
