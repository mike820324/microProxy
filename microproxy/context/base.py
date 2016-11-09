import re


class Serializable(object):
    def serialize(self):
        data = {}
        for k, v in self.__dict__.items():
            if isinstance(v, Serializable):
                data[k] = v.serialize()
            else:
                data[k] = v
        return data

    @classmethod
    def deserialize(cls, data):
        if isinstance(data, cls):
            return data
        elif isinstance(data, dict):
            return cls(**data)
        elif data:
            raise ValueError("cannot deserialize to {0} with {1}".format(
                type(data).__name__, cls.__name__))
        else:
            return None

    def __str__(self):
        return "{0}{1}".format(type(self).__name__, self.__dict__)

    def __repr__(self):
        return "{0}{1}".format(type(self).__name__, self.__dict__)

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __neq__(self, other):
        return not self.__eq__(other)


def parse_version(version):
    versions = re.split(r"\.|-|\+", version)
    return (
        int(versions[0]),
        int(versions[1]),
        int(versions[2]),
    )
