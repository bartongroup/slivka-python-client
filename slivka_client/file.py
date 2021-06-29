import io
import os
from urllib.parse import urljoin

import attr
import requests


@attr.s()
class File(str):
    def __new__(cls, *args, **kwargs):
        # grab id from the third position or 'id' kwarg
        val = args[2] if len(args) >= 3 else kwargs['id']
        return super().__new__(cls, val)

    url: str = attr.ib(repr=False)
    content_url: str = attr.ib(repr=False)
    id: str = attr.ib()
    job_id: str = attr.ib(repr=False)
    path: str = attr.ib(repr=False)
    label: str = attr.ib()
    media_type: str = attr.ib(repr=False)

    def dump(self, fp):
        response = requests.get(self.content_url)
        response.raise_for_status()
        if isinstance(fp, io.TextIOBase):
            fp.write(response.text)
        elif isinstance(fp, io.IOBase):
            fp.write(response.content)
        else:
            with open(os.fspath(fp), 'wb') as f:
                f.write(response.content)

    @staticmethod
    def from_response(host, response):
        return File(
            url=urljoin(host, response['@url']),
            content_url=urljoin(host, response['@content']),
            id=response['id'],
            job_id=response['jobId'],
            path=response['path'],
            label=response['label'],
            media_type=response['mediaType']
        )
