import re

import isodate
import requests
from pystac import (Collection, Extent, Link, SpatialExtent,
                    TemporalExtent)
from pystac.extensions.datacube import DatacubeExtension, Dimension, Variable
from pystac.extensions.render import Render, RenderExtension
from pystac.utils import datetime_to_str

from .utils import convert_to_datetime, get_data, get_xml, transform_projection
from enum import Enum

from .WMSReader import WMSReader


class ServerType(Enum):
    Map = "Map"
    Feature = "Feature"
    Image = "Image"


class ArcReader:
    def __init__(self, server_url):
        self.server_url = server_url
        self.type, self.collection_id = self._extract_type_and_id()

    def _extract_type_and_id(self):
        pattern = (
            r"services/(?P<collection_id>.*?)/(?P<server_type>(Image|Map|Feature))Server"
        )
        re_search = re.search(pattern, self.server_url)
        type = re_search.group("server_type")

        collection_name = re_search.group("collection_id")
        # STAC API doesn't support /
        collection_id = collection_name.replace("/", "_").lower()
        return type, collection_id

    def wms_root(self):
        try:
            self.wms_url = f"""{
                    self.server_url.replace('/rest', '')
                    }/WMSServer?request=GetCapabilities&service=WMS
                """.strip()
            root = get_xml(
                self.wms_url
            )
            return root
        except (requests.exceptions.HTTPError, Exception) as err:
            # Server does not have WMS enabled
            print("Error accessing WMS.", err)
            return None

    @staticmethod
    def convert_esri_time_unit(esri_time_unit):
        return esri_time_unit.replace("esriTimeUnits", "")[:-1].lower()

    @staticmethod
    def convert_to_iso_interval(time_interval_value, time_unit):
        # Extract the first letter of the unit after removing "esriTimeUnits"
        if not time_unit.startswith("esriTimeUnits"):
            raise ValueError("Unsupported time interval unit")

        iso_duration = f"P{time_interval_value}{time_unit[13]}"
        return iso_duration

    @staticmethod
    def get_periodicity(time_info):
        if time_info:
            is_periodic, unit, interval = (
                True,
                ArcReader.convert_esri_time_unit(
                    time_info["defaultTimeIntervalUnits"]
                ),
                ArcReader.convert_to_iso_interval(
                    time_info["defaultTimeInterval"],
                    time_info["defaultTimeIntervalUnits"]
                )
            )
            return is_periodic, unit, interval
        else:
            return False, None, None

    def get_cube_info(self):
        multi_dim = get_data(
            f"{self.server_url}/multiDimensionalInfo?returnDimensionValues=always&f=pjson"
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
                                datetime_to_str(extent)
                                for extent in convert_to_datetime(dimension["extent"])
                            ],
                            "values": [
                                datetime_to_str(value)
                                for value in convert_to_datetime(dimension["values"])
                            ],
                            "hasRegularIntervals": dimension["hasRegularIntervals"],
                            "intervalUnit": dimension["intervalUnit"],
                        }
                    )
                # TODO: Handle other types
        return cube_variables, cube_dimensions

    def generate_stac(self):
        json_data = get_data(f"{self.server_url}?f=pjson")
        if json_data.get("error"):
            raise Exception(json_data)

        collection_description = json_data.get("description") \
            or self.collection_id

        spatial_ref = json_data["spatialReference"]["latestWkid"]
        xmin, ymin = (
            json_data["fullExtent"]["xmin"],
            json_data["fullExtent"]["ymin"]
        )
        xmax, ymax = (
            json_data["fullExtent"]["xmax"],
            json_data["fullExtent"]["ymax"]
        )

        collection_bbox = transform_projection(
            spatial_ref, xmin, ymin
        ) + transform_projection(spatial_ref, xmax, ymax)
        spatial_extent = SpatialExtent(bboxes=collection_bbox)

        is_timeless = False
        time_info = json_data.get("timeInfo")
        if time_info:
            collection_interval = convert_to_datetime(time_info["timeExtent"])
            is_periodic, time_density, time_interval = \
                self.get_periodicity(time_info)
        else:
            collection_interval = [[None, None]]
            is_timeless = True

        temporal_extent = TemporalExtent(intervals=collection_interval)
        collection_extent = Extent(
            spatial=spatial_extent,
            temporal=temporal_extent
        )

        collection = Collection(
            id=self.collection_id,
            title=self.collection_id.replace("_", " "),
            description=collection_description,
            extent=collection_extent,
            license=json_data.get("license", "not-applicable"),
        )
        match self.type:
            case ServerType.Map.name | ServerType.Image.name:
                if root := self.wms_root():
                    wms_reader = WMSReader(root)
                    wms_layers = wms_reader.get_layers()
                    collection.ext.add("render")
                    RenderExtension.ext(collection).apply(
                        {
                            layer_id.lower(): Render(
                                {
                                    "layers": layer_name
                                }
                            )
                            for layer_id, layer_name in wms_layers.items()
                        }
                    )

                    link = Link(
                        target=f"{self.server_url.replace('/rest', '')}WMSServer",
                        rel="wms",
                        media_type="image/png",
                        title="Visualized through a WMS",
                    )
                    link.extra_fields["wms:layers"] = list(wms_layers.values())
                    link.extra_fields["wms:styles"] = ["default"]
                    collection.add_link(link)

                # This will only be true for ImageServer,
                # so we can safely skip the imageserver check
                if json_data.get("hasMultidimensions"):
                    datacube_variables, datacube_dimensions = \
                        self.get_cube_info()

                    # Add Datacube extension to the collection
                    datacube_ext = DatacubeExtension.ext(
                        collection, add_if_missing=True
                    )
                    # Set Dimensions and Variables to Datacube extension
                    datacube_ext.variables, datacube_ext.dimensions = (
                        datacube_variables,
                        datacube_dimensions,
                    )
            case ServerType.Feature.name:
                layers = {i["id"]: i["name"] for i in json_data["layers"]}
                link = Link(
                    target=self.server_url,
                    rel="featureserver",
                    media_type="application/json",
                    title="ArcGIS FeatureServer",
                )
                link.extra_fields["featureserver:layers"] = layers
                collection.add_link(link)
            case _:
                raise Exception("Server Type is not supported.")

        # add arcgis server url to the collection links
        server_link = Link(
            target=self.server_url,
            rel="via",
            media_type="text/html",
            title="Parent ArcGIS server url",
        )
        collection.add_link(server_link)

        # Add custom extensions
        if is_timeless:
            collection.extra_fields["dashboard:is_timeless"] = True
        else:
            collection.extra_fields["dashboard:is_periodic"] = is_periodic
            collection.extra_fields["dashboard:time_density"] = time_density
            collection.extra_fields["dashboard:time_interval"] = time_interval

        return collection
