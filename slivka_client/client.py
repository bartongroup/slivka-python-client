import io
from functools import partial
from typing import overload, Iterable, Union
from urllib.parse import urljoin

import requests
from urllib3.util import Url, parse_url

from .file import File, _build_file
from .service import Service
from .state import JobState


class SlivkaClient:
    @overload
    def __init__(self, url: str): ...

    @overload
    def __init__(self, url: Url): ...

    @overload
    def __init__(self, scheme: str, auth: str, host: str, port: int, path: str): ...

    def __init__(self, url=None, **kwargs):
        if url is None:
            self._url = Url(**kwargs)
        elif isinstance(url, Url):
            self._url = url
        else:
            self._url = parse_url(url)
        self._services = None
        self.build_url = partial(urljoin, self._url.url)

    def get_url(self): return self._url
    url = property(get_url)

    def get_services(self) -> Iterable['Service']:
        if self._services is None:
            self.refresh_services()
        return self._services
    services = property(get_services)

    def refresh_services(self):
        response = requests.get(self.build_url('api/services'))
        if response.status_code == 200:
            self._services = [
                Service(
                    name=service['name'],
                    label=service['label'],
                    path=service['URI'],
                    classifiers=service['classifiers'],
                    url_factory=self.build_url
                )
                for service in response.json()['services']
            ]
        else:
            response.raise_for_status()

    def upload_file(self,
                    file: Union[str, io.BufferedIOBase],
                    title: str = None):
        if isinstance(file, str):
            file = open(file, 'rb')
        response = requests.post(
            url=self.build_url('api/files'),
            files={'file': (title or "", file)}
        )
        response.raise_for_status()

    def get_file(self, id: str) -> 'File':
        response = requests.get(self.build_url('api/files/%s' % id))
        response.raise_for_status()
        return _build_file(response.json(), self)

    def get_job_state(self, uuid: str) -> JobState:
        response = requests.get(self.build_url('api/tasks/%s' % uuid))
        response.raise_for_status()
        return JobState[response.json()['status'].upper()]

    def get_job_results(self, uuid: str):
        response = requests.get(self.build_url('api/tasks/%s/files' % uuid))
        response.raise_for_status()
        return [_build_file(obj, self.build_url)
                for obj in response.json()['files']]

    def __repr__(self):
        return 'SlivkaClient(%s)' % self._url.url
