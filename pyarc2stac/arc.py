import isodate
from pystac import SpatialExtent, TemporalExtent, Collection, Extent, Summaries
from pystac.extensions.datacube import DatacubeExtension, Variable, Dimension
from .utils import get_data, convert_to_datetime


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
    collection_id = json_data['name']
    collection_title = json_data['name']
    collection_description = json_data['serviceDescription']
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
    collection_summaries = Summaries({"datetime": get_datetime_summaries(datacube_dimensions)})

    collection = Collection(
        id=collection_id,
        title=collection_title,
        description=collection_description,
        extent=collection_extent,
        license="",
        summaries=collection_summaries,
    )
    # Add Datacube extension to the collection
    datacube_ext = DatacubeExtension.ext(collection, add_if_missing=True)
    # Set eDimensions and Variables to Datacube extension
    datacube_ext.variables, datacube_ext.dimensions = get_cube_info(image_service_url)
    # Add custom extensions
    collection.extra_fields["dashboard:is_periodic"] = False
    collection.extra_fields["dashboard:time_density"] = "year"  # Todo implement a function to return this properly

    return collection


def get_datetime_summaries(cube_dimensions):
    for dim in cube_dimensions.values():
        dim_dict = dim.to_dict()
        if dim_dict["type"] == "temporal":
            return dim_dict["values"]


def get_cube_info(img_url):
    multi_dim = get_data(
        f"{img_url}/multiDimensionalInfo?returnDimensionValues=always&f=pjson"
    )
    variables = multi_dim["multidimensionalInfo"]["variables"]
    cube_variables = {}
    cube_dimensions = {}

    for index, variable in enumerate(variables):
        cube_variables[variable["name"]] = Variable({
            "type": "data",
            "attrs": variable["attributes"],
            "statistics": variable["statistics"],
            "histograms": variable["histograms"],
            "unit": variable["unit"],
            "dimensions": [dimension["name"] for dimension in variable["dimensions"]],
        })
        if index != 0:
            continue
        for dimension in variable["dimensions"]:
            dim_id = dimension["name"]
            if "Time" in dim_id:
                cube_type = "temporal"
                cube_dimensions[dim_id] = Dimension({
                    "type": cube_type,
                    "step": isodate.duration_isoformat(
                        isodate.Duration(
                            **{dimension["intervalUnit"].lower(): dimension["interval"]}
                        )
                    ),
                    "extent": [f"{extent.isoformat()}Z" for extent in convert_to_datetime(dimension["extent"])],
                    "values": [f"{value.isoformat()}Z" for value in convert_to_datetime(dimension["values"])],
                    "hasRegularIntervals": dimension["hasRegularIntervals"],
                    "intervalUnit": dimension["intervalUnit"],
                })
            # TODO: Handle other types
    return cube_variables, cube_dimensions
