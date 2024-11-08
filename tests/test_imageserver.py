from pyarc2stac import convert_to_collection_stac
import pytest
from requests.exceptions import HTTPError

imageserver_urls_succeed = [
    "https://gis.earthdata.nasa.gov/image/rest/services/POWER/POWER_901_MONTHLY_RADIATION_UTC/ImageServer"
]

imageserver_urls_fails = [
    (
        "https://apps.fs.usda.gov/fsgisx01/rest/services/RDW_Wildfire/RMRS_WRC_HousingUnitDensity/ImageServer",
        pytest.raises(HTTPError),
    ),
    (
        "https://gis.nnvl.noaa.gov/arcgis/rest/services/REEF/REEF_current/ImageServer",
        pytest.raises(HTTPError),
    ),
    (
        "https://gis.nnvl.noaa.gov/arcgis/rest/services/CDHW/CDHW_yearly/ImageServer",
        pytest.raises(HTTPError),
    ),
]


@pytest.mark.parametrize("url, expectation", imageserver_urls_fails)
def test_imageserver_fails(url: str, expectation):
    with expectation as e:
        assert convert_to_collection_stac(server_url=url) == e


@pytest.mark.parametrize("url", imageserver_urls_succeed)
def test_imageserver_succeeds(url: str):
    collection = convert_to_collection_stac(server_url=url)
    collection.validate()
