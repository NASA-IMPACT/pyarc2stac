# Pyarc2stac

A reverse proxy that dataset metadata from ESRI data services (ImageServer, MapServer, FeatureServer, SomethingServer) as [STAC](https://stacspec.org/), 
so they can become discoverable alongside other STAC-indexed resources.

## Supported ESRI services

| Service | Supported |
|---|---|
| ImageServer | ✅ |
| MapServer | ✅ |
| FeatureServer | WIP |

## To install
```shell
pip install git+https://github.com/NASA-IMPACT/pyarc2stac.git@main#egg=pyarc2stac
```
## Examples
Please refer to the [examples](./examples) folder for sample usage
