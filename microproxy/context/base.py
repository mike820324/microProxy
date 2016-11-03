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

    def __str__(self):
        return "{0}{1}".format(type(self).__name__, self.__dict__)

    def __repr__(self):
        return "{0}{1}".format(type(self).__name__, self.__dict__)


def try_deserialize(data, target_type):
    if isinstance(data, target_type):
        return data
    elif isinstance(data, dict):
        return target_type(**data)
    elif data:
        raise ValueError("incorrect type: {0}, expected is {1}".format(
            type(data).__name__, target_type.__name__))
    else:
        return None


def parse_version(version):
    versions = re.split(r"\.|-", version)
    return (
        int(versions[0]),
        int(versions[1]),
        int(versions[2]),
    )
