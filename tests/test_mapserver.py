from pyarc2stac.ArcReader import ArcReader
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
    arc = ArcReader(server_url=url)
    collection = arc.generate_stac()
    collection.validate()
