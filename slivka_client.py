import io
import re
import threading
from typing import Dict, Callable, List, Union
from collections import namedtuple

import requests

from form_fields import FormField, ValidationError

_session = requests.Session()


class SlivkaClient:
    def __init__(self, host: str, port: int):
        if not re.match('https?://', host):
            host = 'http://' + host
        self._host = '{}:{}'.format(host.rstrip(' /'), port)
        self._services = None

    def services(self) -> List['Service']:
        if self._services is None:
            response = _session.get(self._host + '/services')
            if response.status_code == 200:
                self._services = [
                    Service(name=service['name'],
                            form_uri=service['submitURI'],
                            host=self._host)
                    for service in response.json()['services']
                ]
            else:
                raise HTTPException.from_response(response)
        return self._services

    def upload_file(self,
                    file: Union[str, io.BufferedIOBase],
                    title: str) -> 'FileHandler':
        if isinstance(file, str):
            file = open(file, 'rb')
        elif not isinstance(file, io.BufferedIOBase):
            raise TypeError('"%s" is not valid path or stream' % repr(type(file)))
        response = _session.post(
            url=self._host + '/file',
            data={'mimetype': 'text/plain'},
            files={'file': (title, file)}
        )
        if response.status_code == 201:
            json = response.json()
            return FileHandler(
                file_id=json['id'],
                title=json['title'],
                mimetype=json['mimetype'],
                download_url=self._host + json['downloadURI']
            )
        else:
            raise HTTPException.from_response(response)

    def get_file(self, file_id: str) -> 'FileHandler':
        response = _session.get(self._host + '/file/%s' % file_id)
        if response.status_code == 200:
            json = response.json()
            return FileHandler(
                file_id=json['id'],
                title=json['title'],
                mimetype=json['mimetype'],
                download_url=self._host + json['downloadURI']
            )
        else:
            raise HTTPException.from_response(response)

    def __repr__(self):
        return '<SlivkaClient "%s">' % self._host


class Service:
    def __init__(self, name, form_uri, host):
        self._name = name
        self._form_uri = form_uri
        self._form = None
        self._host = host

    @property
    def name(self) -> str:
        return self._name

    @property
    def form_url(self) -> str:
        return self._host + self._form_uri

    def form(self) -> 'Form':
        if self._form is None:
            response = _session.get(self.form_url)
            if response.status_code == 200:
                self._form = Form.from_json(response.json(), self._host)
            else:
                raise HTTPException.from_response(response)
        return self._form

    def __repr__(self):
        return '<Service %s>' % self.name


class Form:
    def __init__(self, name: str, fields: dict, submit_uri: str, host: str):
        self._name = name
        self._fields = fields
        self._submit_uri = submit_uri
        self._host = host

    @property
    def name(self) -> str:
        return self._name

    @property
    def fields(self) -> Dict[str, FormField]:
        return self._fields

    @property
    def host(self) -> str:
        return self._host

    @property
    def submit_url(self) -> str:
        return self._host + self._submit_uri

    @staticmethod
    def from_json(json, host: str) -> 'Form':
        return Form(
            name=json['form'],
            fields={
                field['name']: None
                for field in json['fields']
            },
            submit_uri=json['submitURI'],
            host=host
        )

    def init(self) -> 'FormProxy':
        return FormProxy(self)

    def insert(self, items: dict = None, **kwargs) -> 'FormProxy':
        return FormProxy(self).insert(items, **kwargs)

    def __repr__(self):
        return '<%s>' % self.name


class FormProxy:
    def __init__(self, form: Form):
        self._values = {}
        self._form = form

    @property
    def fields(self) -> Dict[str, FormField]:
        return self._form.fields

    def insert(self, items: dict = None, **kwargs) -> 'FormProxy':
        items = items or {}
        items.update(kwargs)
        for name, value in items.items():
            if name not in self._form.fields.keys():
                raise KeyError('Invalid field "%s"' % name)
            self._values[name] = value
        return self

    def validate(self):
        errors = []
        for name, field in self._form.fields.items():
            try:
                self._values[name] = field.validate(self._values[name])
            except ValidationError as e:
                errors.append(e)
        if errors:
            raise FormValidationError(errors)

    def submit(self) -> 'TaskHandler':
        response = _session.post(self._form.submit_url, data=self._values)
        if response.status_code == 202:
            return TaskHandler(task_id=response.json()['taskId'],
                               status_uri=response.json()['checkStatusURI'],
                               host=self._form.host)
        else:
            raise HTTPException.from_response(response)

    def __repr__(self):
        return '<%sProxy>' % self._form.name


class FileHandler:
    def __init__(self,
                 file_id: str,
                 title: str,
                 mimetype: str,
                 download_url: str):
        self._file_id = file_id
        self._title = title
        self._mimetype = mimetype
        self._download_url = download_url

    @property
    def id(self) -> str:
        return self._file_id

    @property
    def title(self) -> str:
        return self._title

    @property
    def mimetype(self) -> str:
        return self._mimetype

    @property
    def download_url(self) -> str:
        return self._download_url

    def download(self) -> str:
        response = _session.get(self.download_url)
        if response.status_code == 200:
            return response.text
        else:
            raise HTTPException.from_response(response)

    def __repr__(self):
        return '<File %s>' % self._file_id


class TaskHandler:
    TaskStatus = namedtuple('Status', 'execution, ready, result_uri')

    def __init__(self, task_id: str, status_uri: str, host: str):
        self._task_id = task_id
        self._status_uri = status_uri
        self._host = host
        self._observer = self.TaskObserver(self)
        self._cached_status = None

    @property
    def status_url(self) -> str:
        return self._host + self._status_uri

    @property
    def observer(self) -> 'TaskHandler.TaskObserver':
        return self._observer

    def status(self) -> TaskStatus:
        if self._cached_status is not None:
            return self._cached_status
        response = _session.get(self.status_url)
        if response.status_code == 200:
            status = self.TaskStatus(
                execution=response.json()['execution'],
                ready=response.json()['ready'],
                result_uri=response.json()['resultURI']
            )
            if status.ready:
                self._cached_status = status
            return status
        else:
            raise HTTPException.from_response(response)

    def result(self) -> List[FileHandler]:
        status = self.status()
        if not status.ready:
            raise ImproveYourPatience('Result is not ready yet')
        response = _session.get(self._host + self.status().result_uri)
        if response.status_code == 200:
            return [
                FileHandler(
                    file_id=file['id'],
                    title=file['title'],
                    mimetype=file['mimetype'],
                    download_url=self._host + file['downloadURI']
                )
                for file in response.json()['files']
            ]
        else:
            raise HTTPException.from_response(response)

    def __repr__(self):
        return '<Task %s>' % self._task_id

    class TaskObserver(threading.Thread):
        def __init__(self, handler: 'TaskHandler'):
            super().__init__()
            self._handler = handler
            self._listeners = set()
            self._interrupt_event = threading.Event()
            self._cached_status = None  # type: TaskHandler.TaskStatus

        @property
        def status(self) -> 'TaskHandler.TaskStatus':
            if self._cached_status is None:
                return self._handler.status()
            else:
                return self._cached_status

        def add_ready_listener(self, func: Callable[['TaskHandler'], None]):
            self._listeners.add(func)

        def run(self):
            self._interrupt_event.clear()
            while not self._interrupt_event.is_set():
                self._cached_status = self._handler.status()
                if self._cached_status.ready:
                    self._interrupt_event.set()
                self._interrupt_event.wait(0.5)
            for listener in self._listeners:
                listener(self._handler)

        def interrupt(self):
            self._interrupt_event.set()

        def wait(self, timeout):
            return self._interrupt_event.wait(timeout)


class HTTPException(Exception):
    def __init__(self, status: int, description: str, content: str):
        self.status = status
        self.description = description
        self.content = content
        super().__init__('%d %s' % (status, description))

    @classmethod
    def from_response(cls, response: requests.Response) -> 'HTTPException':
        return HTTPException(
            status=response.status_code,
            description=response.json()['error'],
            content=response.text
        )


class FormValidationError(Exception):
    def __init__(self, errors: List[ValidationError]):
        self.errors = errors


class ImproveYourPatience(Exception):
    pass
