import abc
import io
import threading
import xml.etree.ElementTree as ElementTree
from typing import Dict, List, Union, Type, NamedTuple, Callable, Optional
from warnings import warn

import requests
from urllib3.util import Url

_session = requests.Session()


class SlivkaClient:
    def __init__(self, host: str, port: int = 8000):
        self._url = Url(scheme='http', host=host, port=port)
        self._services = None

    @property
    def url(self) -> Url:
        return self._url

    def build_url(self, path) -> Url:
        return Url(
            scheme=self._url.scheme,
            host=self._url.host,
            port=self._url.port,
            path=path
        )

    def get_services(self) -> List['Service']:
        if self._services is None:
            response = _session.get(self.build_url('/api/services'))
            if response.status_code == 200:
                self._services = [
                    Service(name=service['name'], path=service['URI'], client=self)
                    for service in response.json()['services']
                ]
            else:
                raise HTTPException.from_response(response)
        return self._services

    def get_service(self, service_name) -> 'Service':
        return next(service for service in self.get_services()
                    if service.name == service_name)

    def upload_file(self,
                    file: Union[str, io.BufferedIOBase],
                    title: str,
                    mime_type: str = 'text/plain') -> 'RemoteFile':
        if isinstance(file, str):
            file = open(file, 'rb')
        elif not isinstance(file, io.BufferedIOBase):
            raise TypeError('"%s" is not valid path or stream' % repr(type(file)))
        response = _session.post(
            url=self.build_url('/files'),
            files={'file': (title, file, mime_type)}
        )
        if response.status_code == 201:
            json_data = response.json()
            return RemoteFile(
                file_uuid=json_data['uuid'],
                title=json_data['title'],
                mime_type=json_data['mimetype'],
                content_path=json_data['contentURI'],
                client=self
            )
        else:
            raise HTTPException.from_response(response)

    def get_remote_file(self, file_id: str) -> 'RemoteFile':
        response = _session.get(self.build_url('/api/files/%s' % file_id))
        if response.status_code == 200:
            json_data = response.json()
            return RemoteFile(
                file_uuid=json_data['uuid'],
                title=json_data['title'],
                mime_type=json_data['mimetype'],
                content_path=json_data['contentURI'],
                client=self
            )
        else:
            raise HTTPException.from_response(response)

    def get_task(self, uuid) -> 'Task':
        url_path = '/api/tasks/%s' % uuid
        response = _session.get(self.build_url(url_path))
        if response.status_code == 200:
            return Task(uuid, url_path, self)
        else:
            raise HTTPException.from_response(response)

    def dump_tasks(self, tasks, fname) -> None:
        root = ElementTree.Element('SlivkaClient')
        ElementTree.SubElement(root, 'host').text = self._url.host
        ElementTree.SubElement(root, 'port').text = str(self._url.port)
        tasks_element = ElementTree.SubElement(root, 'tasks')
        for task in tasks:
            te = ElementTree.SubElement(tasks_element, 'Task')
            ElementTree.SubElement(te, 'uuid').text = task.uuid
            ElementTree.SubElement(te, 'path').text = task.url.path
        ElementTree.ElementTree(root).write(fname, xml_declaration=True)

    def load_tasks(self, fname) -> List['Task']:
        tree = ElementTree.parse(fname)
        host = tree.find('host').text
        port = int(tree.find('port').text)
        if not (self._url.host == host and self._url.port == port):
            warn('Loaded tasks did not originate from this server.')
        return [
            Task(el.find('uuid').text, el.find('path'), self)
            for el in tree.findall('tasks/Task')
        ]

    def __repr__(self):
        return '<SlivkaClient "%s">' % self.url


class Service:
    def __init__(self, name, path, client: SlivkaClient):
        self._name = name
        self._client = client
        self._url = client.build_url(path)
        self._form = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def url(self) -> Url:
        return self._url

    def get_form(self) -> 'Form':
        if self._form is None:
            response = _session.get(self.url)
            if response.status_code == 200:
                self._form = Form.from_json(response.json(), self._client)
            else:
                raise HTTPException.from_response(response)
        return self._form.copy()

    def __repr__(self):
        return '<Service %s>' % self.name


class Form:
    def __init__(self, name: str, fields: dict, path: str, client: SlivkaClient):
        self._name = name
        self._fields = fields
        self._url = client.build_url(path)
        self._client = client
        self._template = True
        self._values = {}

    @property
    def name(self) -> str:
        return self._name

    @property
    def url(self) -> Url:
        return self._url

    @property
    def fields(self) -> Dict[str, 'FormField']:
        return self._fields

    @classmethod
    def from_json(cls: Type['Form'], json_data: dict, client: SlivkaClient) -> 'Form':
        return cls(
            name=json_data['name'],
            fields={
                field['name']: FormField.make_field(field)
                for field in json_data['fields']
            },
            path=json_data['URI'],
            client=client
        )

    def copy(self) -> 'Form':
        return Form(self._name, self._fields, self._url.path, self._client)

    def insert(self, items: dict = None, **kwargs) -> 'Form':
        items = items.copy() if items else {}
        items.update(kwargs)
        for name, value in items.items():
            if name not in self.fields.keys():
                raise KeyError('Invalid field "%s"' % name)
            self._values[name] = value
        return self

    def validate(self) -> Dict[str, str]:
        errors = []
        cleaned_values = {}
        for name, field in self.fields.items():
            try:
                cleaned_values[name] = field.validate(self._values.get(name))
            except ValidationError as e:
                errors.append(e)
        if errors:
            raise FormValidationError(errors)
        else:
            return cleaned_values

    def submit(self) -> 'Task':
        cleaned_values = self.validate()
        response = _session.post(self.url, data=cleaned_values)
        if response.status_code == 202:
            json_data = response.json()
            return Task(task_uuid=json_data['uuid'],
                        path=json_data['URI'],
                        client=self._client)
        else:
            raise HTTPException.from_response(response)

    def __repr__(self):
        return '<%sForm>' % self.name


class RemoteFile:
    def __init__(self,
                 file_uuid: str,
                 title: str,
                 mime_type: str,
                 content_path: str,
                 client: SlivkaClient):
        self._file_uuid = file_uuid
        self._title = title
        self._mime_type = mime_type
        self._content_url = client.build_url(content_path)
        self._client = client

    @property
    def uuid(self) -> str:
        return self._file_uuid

    @property
    def title(self) -> str:
        return self._title

    @property
    def mime_type(self) -> str:
        return self._mime_type

    @property
    def url(self) -> Url:
        return self._content_url

    def dump(self, fp) -> None:
        response = _session.get(self._content_url)
        if response.status_code == 200:
            if isinstance(fp, str):
                with open(fp, 'wb') as f:
                    f.write(response.content)
            elif isinstance(fp, io.TextIOBase):
                fp.write(response.text)
            elif isinstance(fp, (io.BufferedIOBase, io.RawIOBase)):
                fp.write(response.content)
            else:
                raise TypeError(type(fp))
        else:
            raise HTTPException.from_response(response)

    def __repr__(self):
        return '<File %s>' % self._file_uuid


class Task:
    Status = NamedTuple(
        'Status',
        [('status', str), ('ready', bool), ('files_url', str)]
    )

    def __init__(self, task_uuid: str, path: str, client: SlivkaClient):
        self._uuid = task_uuid
        self._url = client.build_url(path)
        self._client = client
        self._cached_status = None

    @property
    def url(self) -> Url:
        return self._url

    @property
    def uuid(self):
        return self._uuid

    def get_status(self) -> Status:
        if self._cached_status is not None:
            return self._cached_status
        response = _session.get(self.url)
        if response.status_code == 200:
            json_data = response.json()
            status = Task.Status(
                status=json_data['status'],
                ready=json_data['ready'],
                files_url=self._client.build_url(json_data['filesURI'])
            )
            if status.ready:
                self._cached_status = status
            return status
        else:
            raise HTTPException.from_response(response)

    def get_files(self) -> List[RemoteFile]:
        status = self.get_status()
        if not status.ready:
            warn("Job hasn't finished yet. The result may be incomplete.")
        response = _session.get(status.files_url)
        if response.status_code == 200:
            return [
                RemoteFile(
                    file_uuid=file['uuid'],
                    title=file['title'],
                    mime_type=file['mimetype'],
                    content_path=file['contentURI'],
                    client=self._client
                )
                for file in response.json()['files']
            ]
        else:
            raise HTTPException.from_response(response)

    def __repr__(self):
        return '<Task %s>' % self.uuid


class TaskWatcher(threading.Thread):
    def __init__(self, task: Task):
        super().__init__()
        self._task = task
        self._listeners = set()
        self._interrupt_event = threading.Event()

    @property
    def task(self):
        return self._task

    def get_status(self) -> Task.Status:
        return self._task.get_status()

    def add_completion_listener(self, func: Callable[[Task], None]):
        self._listeners.add(func)

    def run(self):
        self._interrupt_event.clear()
        while True:
            status = self._task.get_status()
            if status.ready:
                self._interrupt_event.set()
            self._interrupt_event.wait(1)
            if self._interrupt_event.is_set():
                break
        if status.ready:
            for listener in self._listeners:
                listener(self._task)

    def interrupt(self):
        self._interrupt_event.set()

    def wait(self, timeout):
        return self._interrupt_event.wait(timeout)


# --- Exceptions --- #

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


class ValidationError(Exception):
    def __init__(self, field, code, message):
        super().__init__('{}: {}'.format(field.name, message))
        self.field = field
        self.code = code


class FormValidationError(Exception):
    def __init__(self, errors: List[ValidationError]):
        self.errors = errors


# --- Form fields --- #

class FormField(metaclass=abc.ABCMeta):
    _type_map = {}

    def __init__(self, name, required, default, label, description):
        self._name = name
        self._required = required
        self._default = default
        self._label = label
        self._description = description

    @property
    def name(self):
        return self._name

    @property
    def required(self):
        return self._required

    @property
    def default(self):
        return self._default

    @property
    def label(self):
        return self._label

    @property
    def description(self):
        return self._description

    @abc.abstractmethod
    def validate(self, value):
        pass

    @classmethod
    @abc.abstractmethod
    def from_json(cls, json_data):
        pass

    @classmethod
    def make_field(cls, json_data):
        field_class = cls._type_map[json_data['type']]
        return field_class.from_json(json_data)


class IntegerField(FormField):
    def __init__(self, name, required, default, label, description, min, max):
        super().__init__(name, required, default, label, description)
        self._min = min
        self._max = max

    @property
    def min(self) -> Optional[int]:
        return self._min

    @property
    def max(self) -> Optional[int]:
        return self._max

    def validate(self, value):
        value = self.default if value is None else value
        if value is None:
            if self.required:
                raise ValidationError(self, 'required', 'Field is required')
            else:
                return None
        if not isinstance(value, int):
            raise ValidationError(self, 'value', '%s is not an integer' % repr(value))
        if self.max is not None and value > self.max:
            raise ValidationError(self, 'max', 'Value is too large')
        if self.min is not None and value < self.min:
            raise ValidationError(self, 'min', 'Value is too small')
        return value

    @classmethod
    def from_json(cls, json_data):
        return IntegerField(
            name=json_data['name'],
            required=json_data['required'],
            default=json_data['default'],
            label=json_data['label'],
            description=json_data['description'],
            min=json_data.get('min'),
            max=json_data.get('max')
        )

    def __repr__(self):
        return (
            "IntegerField(name={}, required={}, default={}, min={}, max={})"
            .format(self.name, self.required, self.default, self.min, self.max)
        )


class DecimalField(FormField):
    def __init__(self, name, required, default, label, description,
                 min, min_exclusive, max, max_exclusive):
        super().__init__(name, required, default, label, description)
        self._min = min
        self._max = max
        self._min_exc = min_exclusive if min_exclusive is not None else False
        self._max_exc = max_exclusive if max_exclusive is not None else False

    @property
    def min(self):
        return self._min

    @property
    def min_exclusive(self):
        return self._min_exc

    @property
    def max(self):
        return self._max

    @property
    def max_exclusive(self):
        return self._max_exc

    def validate(self, value):
        value = self.default if value is None else value
        if value is None:
            if self.required:
                raise ValidationError(self, 'required', 'Field is required')
            else:
                return None
        if not isinstance(value, float):
            raise ValidationError(self, 'value', '%s is not a float' % repr(value))
        if self._max is not None:
            if not self._max_exc and value > self._max:
                raise ValidationError(self, 'max', '%f > %f' % (value, self._max))
            elif self._max_exc and value >= self._max:
                raise ValidationError(self, 'max', '%f >= %f' % (value, self._max))
        if self._min is not None:
            if not self._min_exc and value < self._min:
                raise ValidationError(self, 'min', '%f < %f' % (value, self._min))
            elif self._min_exc and value <= self._min:
                raise ValidationError(self, 'min', '%f <= %f' % (value, self._min))
        return value

    @classmethod
    def from_json(cls, json_data):
        return DecimalField(
            name=json_data['name'],
            required=json_data['required'],
            default=json_data['default'],
            label=json_data['label'],
            description=json_data['description'],
            min=json_data.get('min'),
            max=json_data.get('max'),
            min_exclusive=json_data.get('minExclusive', False),
            max_exclusive=json_data.get('maxExclusive', False)
        )

    def __repr__(self):
        return (
            "DecimalField(name={}, required={}, default={}, min={}, max={}, min_exc={}, max_exc={})"
            .format(self.name, self.required, self.default, self.min, self.max,
                    self.min_exclusive, self.max_exclusive)
        )


class TextField(FormField):
    def __init__(self, name, required, default, label, description, min_length, max_length):
        super().__init__(name, required, default, label, description)
        self._min_length = min_length
        self._max_length = max_length

    @property
    def min_length(self):
        return self._min_length

    @property
    def max_length(self):
        return self._max_length

    def validate(self, value):
        value = self.default if value is None else value
        if value is None:
            if self.required:
                raise ValidationError(self, 'required', 'Field is required')
            else:
                return None
        if not isinstance(value, str):
            raise ValidationError(self, 'value', '%s is not a string' % repr(value))
        if self._max_length is not None and len(value) > self._max_length:
            raise ValidationError(self, 'max_length', 'String is too long')
        if self._min_length is not None and len(value) < self._min_length:
            raise ValidationError(self, 'min_length', 'String is too short')
        return value

    @classmethod
    def from_json(cls, json_data):
        return TextField(
            name=json_data['name'],
            required=json_data['required'],
            default=json_data['default'],
            label=json_data['label'],
            description=json_data['description'],
            min_length=json_data.get('minLength'),
            max_length=json_data.get('maxLength')
        )

    def __repr__(self):
        return (
            "TextField(name={}, required={}, default={}, min_length={}, max_length={})"
            .format(self.name, self.required, self.default, self.min_length, self.max_length)
        )


class BooleanField(FormField):
    def __init__(self, name, required, default, label, description):
        super().__init__(name, required, default, label, description)

    def validate(self, value):
        value = self.default if value is None else value
        if value is None or value is False:
            if self.required:
                raise ValidationError(self, 'required', 'Field is required')
            else:
                return None
        if not isinstance(value, bool):
            raise ValidationError(self, 'value', '%s is not a boolean' % repr(value))
        return value

    @classmethod
    def from_json(cls, json_data):
        return BooleanField(
            name=json_data['name'],
            required=json_data['required'],
            default=json_data['default'],
            label=json_data['label'],
            description=json_data['description'],
        )

    def __repr__(self):
        return (
            "BooleanField(name={}, required={}, default={})"
            .format(self.name, self.required, self.default)
        )


class ChoiceField(FormField):
    def __init__(self, name, required, default, label, description, choices):
        super().__init__(name, required, default, label, description)
        self._choices = choices

    @property
    def choices(self):
        return self._choices

    def validate(self, value):
        value = self.default if value is None else value
        if value is None:
            if self.required:
                raise ValidationError(self, 'required', 'Field is required')
            else:
                return None
        if value not in self._choices:
            raise ValidationError(self, 'choice', 'Invalid choice "%s"' % value)

    @classmethod
    def from_json(cls, json_data):
        return ChoiceField(
            name=json_data['name'],
            required=json_data['required'],
            default=json_data['default'],
            label=json_data['label'],
            description=json_data['description'],
            choices=json_data['choices']
        )

    def __repr__(self):
        return (
            "ChoiceField(name={}, required={}, default={}, choices={})"
            .format(self.name, self.required, self.default, self.choices)
        )


class FileField(FormField):
    def __init__(self, name, required, default, label, description,
                 mime_type, extension, max_size):
        super().__init__(name, required, default, label, description)
        self._mime_type = mime_type
        self._extension = extension
        self._max_size = max_size

    @property
    def max_size(self):
        return self._max_size

    @property
    def extension(self):
        return self._extension

    @property
    def mime_type(self):
        return self._mime_type

    def validate(self, value):
        value = self.default if value is None else value
        if value is None:
            if self.required:
                raise ValidationError(self, 'required', 'Field is required')
            else:
                return None
        if not isinstance(value, RemoteFile):
            raise ValidationError(self, 'value', 'Not a RemoteFile')
        return value.uuid

    @classmethod
    def from_json(cls, json_data):
        return FileField(
            name=json_data['name'],
            required=json_data['required'],
            default=json_data['default'],
            label=json_data['label'],
            description=json_data['description'],
            mime_type=json_data.get('mimetype'),
            extension=json_data.get('extension'),
            max_size=json_data.get('maxSize')
        )

    def __repr__(self):
        return (
            "FileField(name={}, required={}, default={}, mime_type={})"
            .format(self.name, self.required, self.default, self.mime_type)
        )


FormField._type_map = {
    'integer': IntegerField,
    'decimal': DecimalField,
    'choice': ChoiceField,
    'text': TextField,
    'boolean': BooleanField,
    'file': FileField
}
