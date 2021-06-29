from datetime import datetime, timedelta
from typing import List
from urllib.parse import urljoin

import attr
import requests

from .file import File

_POLL_DELAY = timedelta(seconds=5)


@attr.s
class Job:
    url: str = attr.ib()
    id: str = attr.ib()
    service: str = attr.ib()
    parameters: dict = attr.ib()
    submission_time: datetime = attr.ib(
        converter=lambda ds: datetime.strptime(ds, "%Y-%m-%dT%H:%M:%S")
    )
    _completion_time: datetime = attr.ib(
        converter=attr.converters.optional(
            lambda ds: datetime.strptime(ds, "%Y-%m-%dT%H:%M:%S")
        )
    )
    _status: str = attr.ib()
    _poll_timestamp = attr.ib(init=False, factory=datetime.now)

    @property
    def completion_time(self) -> datetime:
        if self._poll_timestamp + _POLL_DELAY < datetime.now():
            self.reload()
        return self._completion_time

    @property
    def status(self) -> str:
        if self._poll_timestamp + _POLL_DELAY < datetime.now():
            self.reload()
        return self._status

    def get_results(self) -> List[File]:
        response = requests.get(self.url + '/files')
        response.raise_for_status()
        return [
            File.from_response(self.url, f)
            for f in response.json()['files']
        ]

    files = property(get_results)
    results = property(get_results)

    def reload(self):
        response = requests.get(self.url)
        response.raise_for_status()
        js = response.json()
        if js['completionTime'] is not None:
            self._completion_time = datetime.strptime(
                js['completionTime'], "%Y-%m-%dT%H:%M:%S"
            )
        self._status = js['status']
        self._poll_timestamp = datetime.now()

    @staticmethod
    def from_response(host, response):
        return Job(
            url=urljoin(host, response['@url']),
            id=response['id'],
            service=response['service'],
            parameters=response['parameters'],
            submission_time=response['submissionTime'],
            completion_time=response.get('completionTime'),
            status=response['status']
        )
