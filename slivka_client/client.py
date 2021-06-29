import io
import os
import re
from collections import namedtuple
from typing import Union, List
from urllib.parse import urljoin, urlsplit

import requests

from .file import File
from .job import Job
from .service import Service

Version = namedtuple('Version', ['client', 'server', 'API'])


class SlivkaClient:
    """
    A Client class which will connect to the specified address.
    You can provide a single argument *url* either a string or an
    instance of ``urllib3.util.url.Url`` of you can specify individual
    arguments that will be passed to the ``urllib3.util.url.Url``. This
    method does not check the validity of the URL, its up to the user to
    make sure that URL is correct and points to an existing server.
    """

    def __init__(self, url: str):
        if not re.match(r'(\w+:)?//', url):
            url = 'http://' + url
        self._url = urlsplit(url, scheme='http').geturl()
        self._services = None

    def get_url(self) -> str:
        """Get the URL the client will connect to.

        :rtype: urllib3.util.url.Url
        """
        return self._url

    url = property(get_url)

    def get_version(self) -> Version:
        from . import __version__
        response = requests.get(urljoin(self.url, 'api/version'))
        response.raise_for_status()
        resp_json = response.json()
        return Version(
            client=__version__,
            server=resp_json['slivkaVersion'],
            API=resp_json['APIVersion']
        )

    version = property(get_version)

    def get_services(self) -> List['Service']:
        """Return the list of services.

        :rtype: list[slivka_client.Service]
        """
        if self._services is None:
            self.reload_services()
        return self._services

    services = property(get_services)

    def get_service(self, name):
        try:
            return next(s for s in self.services if s.id == name)
        except StopIteration:
            raise KeyError(name)

    __getitem__ = get_service

    def reload_services(self):
        """Force reloading the services list from the server."""
        response = requests.get(urljoin(self.url, 'api/services'))
        response.raise_for_status()
        self._services = [
            Service.from_response(self.url, service)
            for service in response.json()['services']
        ]

    def upload_file(self,
                    file: Union[str, io.BufferedIOBase],
                    title: str = "") -> File:
        """Upload the file to the server and obtain its handler.

        *file* can be either a stream open for reading or a path.
        If path is provided, the file will be opened in binary mode.
        Optionally, the file title can be specified.

        :return: handler to the file on the server.
        :rtype: slivka_client.File
        """
        if isinstance(file, (str, bytes, os.PathLike)):
            file = open(file, 'rb')
        response = requests.post(
            url=urljoin(self.url, 'api/files'),
            files={'file': (title, file)}
        )
        response.raise_for_status()
        return File.from_response(self.url, response.json())

    def get_file(self, file_id: str) -> File:
        """Create a file handler from file id."""
        parts = file_id.split('/', 1)
        if len(parts) > 1:
            path = f"api/jobs/{parts[0]}/files/{parts[1]}"
        else:
            path = f"api/files/{parts[0]}"
        response = requests.get(urljoin(self.url, path))
        response.raise_for_status()
        return File.from_response(self.url, response.json())

    def get_job(self, job_id: str) -> Job:
        """Create a job handler from job id """
        response = requests.get(urljoin(self.url, f"api/jobs/{job_id}"))
        response.raise_for_status()
        return Job.from_response(self.url, response.json())

    def __repr__(self):
        return 'SlivkaClient(%s)' % self._url
