import ConfigParser


class Config(object):
    def __init__(self):
        self.parser = ConfigParser.SafeConfigParser()
        self.parser.read("application.cfg")

    def prop(self, catalog, key):
        return self.parser.get(catalog, key)
