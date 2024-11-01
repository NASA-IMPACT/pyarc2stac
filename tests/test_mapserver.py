from pyarc2stac import convert_to_collection_stac
import pytest

mapserver_urls = [
    "https://gis1.servirglobal.net/arcgis/rest/services/Global/ESI_4WK/MapServer",
    "https://www.sciencebase.gov/arcgis/rest/services/bcb/amphibian_richness_habitat30m/MapServer",
    "https://www.sciencebase.gov/arcgis/rest/services/bcb/bird_richness_habitat30m/MapServer",
    "https://www.sciencebase.gov/arcgis/rest/services/bcb/mammel_richness_habitat30m/MapServer",
    "https://www.sciencebase.gov/arcgis/rest/services/bcb/reptile_richness_habitat30m/MapServer",
]


@pytest.mark.parametrize("url", mapserver_urls)
def test_mapserver(url: str):
    collection = convert_to_collection_stac(server_url=url)
    collection.validate()
