import StringIO
import gzip


def ungzip(content):
    fio = StringIO.StringIO(content)
    with gzip.GzipFile(fileobj=fio) as f:
        decompress_content = f.read()
    return decompress_content
