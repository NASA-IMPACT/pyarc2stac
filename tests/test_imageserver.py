from pyarc2stac import convert_to_collection_stac
import pytest
from contextlib import nullcontext
from requests.exceptions import HTTPError

power_dataset_validation = [
    "https://schemas.stacspec.org/v1.0.0/collection-spec/json-schema/collection.json",
    "https://stac-extensions.github.io/web-map-links/v1.2.0/schema.json",
    "https://stac-extensions.github.io/datacube/v2.2.0/schema.json",
]

imageserver_urls = [
    (
        "https://gis.earthdata.nasa.gov/image/rest/services/POWER/POWER_901_MONTHLY_RADIATION_UTC/ImageServer",
        nullcontext(power_dataset_validation),
    ),
    (
        "https://apps.fs.usda.gov/fsgisx01/rest/services/RDW_Wildfire/RMRS_WRC_HousingUnitDensity/ImageServer",
        pytest.raises(RuntimeError),
    ),
    (
        "https://gis.nnvl.noaa.gov/arcgis/rest/services/REEF/REEF_current/ImageServer",
        pytest.raises(RuntimeError),
    ),
    (
        "https://gis.nnvl.noaa.gov/arcgis/rest/services/CDHW/CDHW_yearly/ImageServer",
        pytest.raises(RuntimeError),
    ),
]


@pytest.mark.parametrize("url, expectation", imageserver_urls)
def test_imageserver(url: str, expectation):
    collection = convert_to_collection_stac(server_url=url)
    with expectation as e:
        assert collection.validate() == e
