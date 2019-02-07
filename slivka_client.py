import abc
import io
import json
import re
import threading
from typing import Dict, Callable, List, Union, Any
from collections import namedtuple

import requests


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
                    title: str,
                    mimetype: str = 'text/plain') -> 'FileHandler':
        if isinstance(file, str):
            file = open(file, 'rb')
        elif not isinstance(file, io.BufferedIOBase):
            raise TypeError('"%s" is not valid path or stream' % repr(type(file)))
        response = _session.post(
            url=self._host + '/file',
            files={'file': (title, file, mimetype)}
        )
        if response.status_code == 201:
            jobj = response.json()
            return FileHandler(
                file_id=jobj['id'],
                title=jobj['title'],
                mimetype=jobj['mimetype'],
                download_url=self._host + jobj['downloadURI']
            )
        else:
            raise HTTPException.from_response(response)

    def get_file(self, file_id: str) -> 'FileHandler':
        response = _session.get(self._host + '/file/%s' % file_id)
        if response.status_code == 200:
            jobj = response.json()
            return FileHandler(
                file_id=jobj['id'],
                title=jobj['title'],
                mimetype=jobj['mimetype'],
                download_url=self._host + jobj['downloadURI']
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
        self._template = True
        self._values = {}

    @property
    def name(self) -> str:
        return self._name

    @property
    def fields(self) -> Dict[str, 'FormField']:
        return self._fields

    @property
    def host(self) -> str:
        return self._host

    @property
    def submit_url(self) -> str:
        return self._host + self._submit_uri

    @staticmethod
    def from_json(jobj, host: str) -> 'Form':
        return Form(
            name=jobj['form'],
            fields={
                field['name']: FormField.build_field(field)
                for field in jobj['fields']
            },
            submit_uri=jobj['submitURI'],
            host=host
        )

    def _clone(self) -> 'Form':
        form = Form(self._name, self._fields, self._submit_uri, self._host)
        form._template = False
        return form

    def insert(self, items: dict = None, **kwargs) -> 'Form':
        form = self._clone() if self._template else self
        items = items or {}
        items.update(kwargs)
        for name, value in items.items():
            if name not in form.fields.keys():
                raise KeyError('Invalid field "%s"' % name)
            form._values[name] = value
        return form

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

    def submit(self) -> 'TaskHandler':
        cleaned_values = self.validate()
        response = _session.post(self.submit_url, data=cleaned_values)
        if response.status_code == 202:
            return TaskHandler(task_id=response.json()['taskId'],
                               status_uri=response.json()['checkStatusURI'],
                               host=self.host)
        else:
            raise HTTPException.from_response(response)

    def __repr__(self):
        return '<%s>' % self.name


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

    def dump(self, fp):
        json.dump(
            {"task_id": self._task_id,
             "status_uri": self._status_uri,
             "host": self._host},
            fp
        )

    @classmethod
    def load(cls, fp):
        return cls(**json.load(fp))

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
        super().__init__(message)
        self.field = field
        self.code = code


class FormValidationError(Exception):
    def __init__(self, errors: List[ValidationError]):
        self.errors = errors


class ImproveYourPatience(Exception):
    pass


# --- Form fields --- #

class FormField(metaclass=abc.ABCMeta):

    _type_map = {}

    def __init__(self, required, default):
        self._required = required
        self._default = default

    @property
    def required(self):
        return self._required

    @property
    def default(self):
        return self._default

    @abc.abstractmethod
    def validate(self, value):
        pass

    @classmethod
    @abc.abstractmethod
    def from_json(cls, jobj):
        pass

    @classmethod
    def build_field(cls, jobj):
        klass = cls._type_map[jobj['type']]
        return klass.from_json(jobj)


class IntegerField(FormField):
    def __init__(self, required, default, min, max):
        super().__init__(required, default)
        self._min = min
        self._max = max

    @property
    def min(self) -> int:
        return self._min

    @property
    def max(self) -> int:
        return self._max

    def validate(self, value):
        if value is None:
            value = self.default
        if value is None and self.required:
            raise ValidationError(self, 'required', 'Field is required')
        if not isinstance(value, int):
            raise ValidationError(self, 'value', '"%s" is not an integer' % repr(value))
        if self.max is not None and value > self.max:
            raise ValidationError(self, 'max', 'Value is too large')
        if self.min is not None and value < self.min:
            raise ValidationError(self, 'min', 'Value is too small')
        return value

    @classmethod
    def from_json(cls, jobj):
        constraints = {
            item['name']: item['value']
            for item in jobj['constraints']
        }
        return IntegerField(
            required=jobj['required'],
            default=jobj['default'],
            min=constraints.get('min'),
            max=constraints.get('max')
        )


class DecimalField(FormField):
    def __init__(self, required: bool, default: float,
                 min: float, min_exclusive: bool,
                 max: float, max_exclusive: bool):
        super().__init__(required, default)
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
        if value is None:
            value = self.default
        if value is None and self.required:
            raise ValidationError(self, 'required', 'Field is required')
        if not isinstance(value, float):
            raise ValidationError(self, 'value', '"%s" is not a float' % repr(value))
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
    def from_json(cls, jobj):
        constraints = {
            item['name']: item['value']
            for item in jobj['constraints']
        }
        return DecimalField(
            required=jobj['required'],
            default=jobj['default'],
            min=constraints.get('min'),
            max=constraints.get('max'),
            min_exclusive=constraints.get('minExclusive', False),
            max_exclusive=constraints.get('maxExclusive', False)
        )


class TextField(FormField):
    def __init__(self, required: bool, default: str,
                 min_length: int, max_length: int):
        super().__init__(required, default)
        self._min_length = min_length
        self._max_length = max_length

    @property
    def min_length(self):
        return self._min_length

    @property
    def max_length(self):
        return self._max_length

    def validate(self, value):
        if value is None:
            value = self.default
        if value is None and self.required:
            raise ValidationError(self, 'required', 'Field is required')
        if not isinstance(value, str):
            raise ValidationError(self, 'value', '"%s" is not a string' % repr(value))
        if self._max_length is not None and len(value) > self._max_length:
            raise ValidationError(self, 'max_length', 'String is too long')
        if self._min_length is not None and len(value) < self._min_length:
            raise ValidationError(self, 'min_length', 'String is too short')
        return value

    @classmethod
    def from_json(cls, jobj):
        constraints = {
            item['name']: item['value']
            for item in jobj['constraints']
        }
        return TextField(
            required=jobj['required'],
            default=jobj['default'],
            min_length=constraints.get('minLength'),
            max_length=constraints.get('maxLength')
        )


class BooleanField(FormField):
    def __init__(self, required: bool, default: bool):
        super().__init__(required, default)

    def validate(self, value):
        if value is None:
            value = self.default
        if (value is None or value is False) and self.required:
            raise ValidationError(self, 'required', 'Field is required')
        if not isinstance(value, bool):
            raise ValidationError(self, 'value', '"%s" is not a boolean' % repr(value))
        return value

    @classmethod
    def from_json(cls, jobj):
        return BooleanField(
            required=jobj['required'],
            default=jobj['default'],
        )


class ChoiceField(FormField):
    def __init__(self, required: bool, default: str, choices: list):
        super().__init__(required, default)
        self._choices = choices

    @property
    def choices(self):
        return self._choices

    def validate(self, value):
        if value is None:
            value = self.default
        if value is None and self.required:
            raise ValidationError(self, 'required', 'Field is required')
        if value not in self._choices:
            raise ValidationError(self, 'choice', 'Invalid choice "%s"' % value)

    @classmethod
    def from_json(cls, jobj):
        constraints = {
            item['name']: item['value']
            for item in jobj['constraints']
        }
        return ChoiceField(
            required=jobj['required'],
            default=jobj['default'],
            choices=constraints['choices']
        )


class FileField(FormField):
    def __init__(self, required: bool, default: Any,
                 mimetype: str, extension: str, max_size: int):
        super().__init__(required, default)
        self._mimetype = mimetype
        self._extension = extension
        self._max_size = max_size

    @property
    def max_size(self):
        return self._max_size

    @property
    def extension(self):
        return self._extension

    @property
    def mimetype(self):
        return self._mimetype

    def validate(self, value):
        if value is None:
            value = self.default
        if value is None and self.required:
            raise ValidationError(self, 'required', 'Field is required')
        if not isinstance(value, FileHandler):
            raise ValidationError(self, 'value', 'Not a FileHandler')
        return value.id

    @classmethod
    def from_json(cls, jobj):
        constraints = {
            item['name']: item['value']
            for item in jobj['constraints']
        }
        return FileField(
            required=jobj['required'],
            default=jobj['default'],
            mimetype=constraints.get('mimetype'),
            extension=constraints.get('extension'),
            max_size=constraints.get('maxSize')
        )


FormField._type_map = {
    'integer': IntegerField,
    'decimal': DecimalField,
    'choice': ChoiceField,
    'text': TextField,
    'boolean': BooleanField,
    'file': FileField
}
