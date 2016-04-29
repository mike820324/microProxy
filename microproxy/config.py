import ConfigParser


class _Config(object):
    def __init__(self):
        self.parser = ConfigParser.SafeConfigParser()
        self.parser.read("application.cfg")

    def __getitem__(self, key):
        return {k: v for k, v in self.parser.items(key)}

config = _Config()
