from pyarc2stac.ArcReader import ArcReader
import pytest

featuresever_urls = [
    "https://services3.arcgis.com/0Fs3HcaFfvzXvm7w/ArcGIS/rest/services/Climate_Mapping_Resilience_and_Adaptation_(CMRA)_Climate_and_Coastal_Inundation_Projections/FeatureServer",
    "https://services2.arcgis.com/FiaPA4ga0iQKduv3/ArcGIS/rest/services/IBTrACS_ALL_list_v04r00_lines_1/FeatureServer",
    "https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/National_Risk_Index_Counties/FeatureServer",
    "https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/National_Risk_Index_Census_Tracts/FeatureServer",
    "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/USA_Flood_Hazard_Reduced_Set_gdb/FeatureServer",
    "https://services9.arcgis.com/RHVPKKiFTONKtxq3/arcgis/rest/services/Active_Hurricanes_v1/FeatureServer",
]


@pytest.mark.parametrize("url", featuresever_urls)
def test_featureserver(url: str):
    arc = ArcReader(server_url=url)
    collection = arc.generate_stac()
    collection.validate()
