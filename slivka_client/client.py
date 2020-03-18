import io
from functools import partial
from typing import overload, Union, List, Optional
from urllib.parse import urljoin

import requests
from urllib3.util import Url, parse_url

from .file import File, _build_file
from .service import Service
from .state import JobState


class SlivkaClient:
    """
    A Client class which will connect to the specified address.
    You can provide a single argument *url* either a string or an
    instance of ``urllib3.util.url.Url`` of you can specify individual
    arguments that will be passed to the ``urllib3.util.url.Url``. This
    method does not check the validity of the URL, its up to the user to
    make sure that URL is correct and points to an existing server.
    """

    @overload
    def __init__(self, url: str):
        ...

    @overload
    def __init__(self, url: Url):
        ...

    @overload
    def __init__(self, *, scheme: str, auth: Optional[str],
                 host: str, port: int, path: str):
        ...

    def __init__(self,
                 url: Union[str, Url] = None,
                 *,
                 scheme: str = 'http',
                 auth: Optional[str] = None,
                 host: str = None,
                 port: int = None,
                 path: str = '/'):
        if not (url or host):
            raise ValueError("either url or host must be specified")
        if url is None:
            self._url = Url(scheme, auth, host, port, path)
        elif isinstance(url, Url):
            self._url = url
        else:
            self._url = parse_url(url)
        self._services = None
        self._build_url = partial(urljoin, self._url.url)

    def get_url(self) -> Url:
        """Get the URL the client will connect to.

        :rtype: urllib3.util.url.Url
        """
        return self._url
    url = property(get_url)

    def get_services(self) -> List['Service']:
        """Return the list of services.

        :rtype: list[slivka_client.Service]
        """
        if self._services is None:
            self.refresh_services()
        return self._services

    services = property(get_services)

    def get_service(self, name):
        try:
            return next(s for s in self.services if s.name == name)
        except StopIteration:
            raise KeyError(name)

    __getitem__ = get_service

    def refresh_services(self):
        """Force reloading the services list from the server."""
        response = requests.get(self._build_url('api/services'))
        if response.status_code == 200:
            self._services = [
                Service(
                    name=service['name'],
                    label=service['label'],
                    path=service['URI'],
                    classifiers=service['classifiers'],
                    url_factory=self._build_url
                )
                for service in response.json()['services']
            ]
        else:
            response.raise_for_status()

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
        if isinstance(file, str):
            file = open(file, 'rb')
        response = requests.post(
            url=self._build_url('api/files'),
            files={'file': (title, file)}
        )
        response.raise_for_status()
        return _build_file(response.json(), self._build_url)

    def get_file(self, id: str) -> File:
        """Fetch the file handler using file id."""
        response = requests.get(self._build_url('api/files/%s' % id))
        response.raise_for_status()
        return _build_file(response.json(), self._build_url)

    def get_job_state(self, uuid: str) -> JobState:
        """Check the state of the job.

        :param uuid: job uuid assigned on submission
        """
        response = requests.get(self._build_url('api/tasks/%s' % uuid))
        response.raise_for_status()
        return JobState[response.json()['status'].upper()]

    def get_job_results(self, uuid: str) -> List[File]:
        """Fetch the output files of the job

        :param uuid: job uuid
        :return: list of the output files
        :rtype: list[slivka_client.File]
        """
        response = requests.get(self._build_url('api/tasks/%s/files' % uuid))
        response.raise_for_status()
        return [_build_file(obj, self._build_url)
                for obj in response.json()['files']]

    def __repr__(self):
        return 'SlivkaClient(%s)' % self._url.url
