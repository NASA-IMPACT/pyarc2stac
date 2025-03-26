class WMSReader():
    def __init__(self, root):
        self.root = root

    # Find all Layer elements
    def get_layers(self):
        layers = {}
        for layer in self.root.findall(".//{http://www.opengis.net/wms}Layer"):
            name = layer.find("{http://www.opengis.net/wms}Name")
            title = layer.find("{http://www.opengis.net/wms}Title")

            if name is not None and title is not None:
                layers[title.text] = name.text
        return layers
