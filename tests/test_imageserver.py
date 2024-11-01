from pyarc2stac import convert_to_collection_stac
import pytest

imageserver_urls = [
    "https://gis.earthdata.nasa.gov/image/rest/services/POWER/POWER_901_MONTHLY_RADIATION_UTC/ImageServer",
    "https://apps.fs.usda.gov/fsgisx01/rest/services/RDW_Wildfire/RMRS_WRC_HousingUnitDensity/ImageServer",
    "https://gis.nnvl.noaa.gov/arcgis/rest/services/REEF/REEF_current/ImageServer",
    "https://gis.nnvl.noaa.gov/arcgis/rest/services/CDHW/CDHW_yearly/ImageServer"
]

@pytest.mark.parametrize("url", imageserver_urls)
def test_imageserver(url: str):
    collection = convert_to_collection_stac(server_url=url)
    collection.validate()
