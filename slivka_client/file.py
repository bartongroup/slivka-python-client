import io

import requests


class File(str):
    def __new__(cls, uuid, *args, **kwargs):
        return super().__new__(cls, uuid)

    def __init__(self, uuid: str, title: str,
                 label: str, media_type: str, url: str):
        super().__init__()
        self._uuid = uuid
        self._title = title
        self._label = label
        self._media_type = media_type
        self._content_url = url

    uuid = property(lambda self: self._uuid)
    title = property(lambda self: self._title)
    label = property(lambda self: self._label)
    media_type = property(lambda self: self._media_type)
    url = property(lambda self: self._content_url)

    def dump(self, fp):
        response = requests.get(self._content_url)
        response.raise_for_status()
        if isinstance(fp, str):
            with open(fp, 'wb') as f:
                f.write(response.content)
        elif isinstance(fp, io.TextIOBase):
            fp.write(response.text)
        else:
            fp.write(response.content)

    def __repr__(self):
        return 'File(%s [%s])' % (self._label, self._uuid)


def _build_file(data_dict, url_factory):
    return File(
        uuid=data_dict['uuid'],
        title=data_dict.get('title', ''),
        label=data_dict.get('label', ''),
        media_type=data_dict.get('mimetype', ''),
        url=url_factory(data_dict['contentURI'])
    )
