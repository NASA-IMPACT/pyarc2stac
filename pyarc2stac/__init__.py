# isort: skip_file
"""
Pyarc2stac is a library used as proxy to convert ARC files to STAC items
"""
__all__ = [
    "__version__",
    "convert_to_collection_stac",
    "fetch_timeseries",
    "get_legend",
]

from pyarc2stac.version import __version__

from pyarc2stac.arc import convert_to_collection_stac, get_legend

from pyarc2stac.timeseries import fetch_timeseries
