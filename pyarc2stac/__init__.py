# isort: skip_file
"""
Pyarc2stac is a library used as proxy to convert ARC files to STAC items
"""

__all__ = [
    "__version__",
    "fetch_timeseries",
    "get_legend",
    "ArcReader",
    "WMSReader",
]

from pyarc2stac.version import __version__

from pyarc2stac.ArcReader import ArcReader
from pyarc2stac.WMSReader import WMSReader

from pyarc2stac.timeseries import fetch_timeseries
