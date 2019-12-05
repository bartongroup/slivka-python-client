import abc
import collections
import enum
import io
from collections import defaultdict
from typing import *

import requests
from urllib3.util import Url, parse_url

_session = requests.Session()


class SlivkaClient:
    def __init__(self, url: Url):
        self._url = url
        self._services = None

    @classmethod
    def from_str_url(cls, url: str):
        return cls(parse_url(url))

    @classmethod
    def from_url_params(cls, **kwargs):
        return cls(Url(**kwargs))

    @property
    def url(self) -> Url:
        return self._url

    def build_url(self, path) -> Url:
        if not path.startswith('/'):
            path = self._url.path + '/' + path
        return Url(
            scheme=self._url.scheme,
            host=self._url.host,
            port=self._url.port,
            path=path
        )

    def get_services(self) -> List['Service']:
        if self._services is None:
            response = _session.get(self.build_url('api/services'))
            if response.status_code == 200:
                self._services = [
                    Service(
                        name=service['name'],
                        label=service['label'],
                        path=service['URI'],
                        classifiers=service['classifiers'],
                        client=self
                    )
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
            url=self.build_url('api/files'),
            files={'file': (title, file, mime_type)}
        )
        if response.status_code == 201:
            return RemoteFile.new_from_json(response.json(), self)
        else:
            raise HTTPException.from_response(response)

    def get_remote_file(self, file_id: str) -> 'RemoteFile':
        response = _session.get(self.build_url('api/files/%s' % file_id))
        if response.status_code == 200:
            return RemoteFile.new_from_json(response.json(), self)
        else:
            raise HTTPException.from_response(response)

    def get_job_state(self, uuid: str) -> 'JobState':
        url = self.build_url('api/tasks/%s' % uuid)
        response = _session.get(url)
        if response.status_code == 200:
            return JobState[response.json()['status'].upper()]
        else:
            raise HTTPException.from_response(response)

    def get_job_results(self, uuid: str) -> List['RemoteFile']:
        url = self.build_url('api/tasks/%s/files' % uuid)
        response = _session.get(url)
        if response.status_code == 200:
            return [RemoteFile.new_from_json(obj, self)
                    for obj in response.json()['files']]
        else:
            raise HTTPException.from_response(response)

    def __repr__(self):
        return '<SlivkaClient "%s">' % self.url


class JobState(enum.Enum):
    PENDING = 'pending'
    REJECTED = 'rejected'
    ACCEPTED = 'accepted'
    QUEUED = 'queued'
    RUNNING = 'running'
    COMPLETED = 'completed'
    INTERRUPTED = 'interrupted'
    DELETED = 'deleted'
    FAILED = 'failed'
    ERROR = 'error'
    UNKNOWN = 'unknown'

    def is_finished(self):
        return self not in (JobState.PENDING, JobState.ACCEPTED,
                            JobState.QUEUED, JobState.RUNNING)


class Service:
    def __init__(self,
                 name: str,
                 label: str,
                 path: str,
                 classifiers: List[str],
                 client: SlivkaClient):
        self._name = name
        self.label = label
        self.classifiers = classifiers
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
        self._values = defaultdict(list)

    @property
    def name(self) -> str:
        return self._name

    @property
    def url(self) -> Url:
        return self._url

    @property
    def fields(self) -> ValuesView['FormField']:
        return self._fields.values()

    def __iter__(self):
        return iter(self.fields)

    def __getitem__(self, item):
        return self._fields[item]

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

    def reset(self):
        for values_list in self._values.values():
            values_list.clear()

    def insert(self, items: dict = None, **kwargs) -> 'Form':
        items = items.copy() if items else {}
        items.update(kwargs)
        for name, value in items.items():
            if name not in self._fields:
                raise KeyError('Invalid field "%s"' % name)
            if isinstance(value, collections.abc.Collection) and not isinstance(value, str):
                self._values[name].extend(value)
            else:
                self._values[name].append(value)
        return self

    def validate(self) -> Dict[str, List[str]]:
        errors = []
        cleaned_values = {}
        for field in self.fields:
            name = field.name
            try:
                values = self._values[name]
                if len(values) == 0:
                    field.validate(None)
                cleaned_values[name] = [
                    field.validate(val) for val in self._values[name]
                ]
            except ValidationError as e:
                errors.append(e)
        if errors:
            raise FormValidationError(errors)
        else:
            return cleaned_values

    def submit(self) -> str:
        cleaned_values = self.validate()
        response = _session.post(self.url, data=cleaned_values)
        if response.status_code == 202:
            json_data = response.json()
            return json_data['uuid']
        else:
            raise HTTPException.from_response(response)

    def __repr__(self):
        return '<%sForm>' % self.name


class RemoteFile:
    def __init__(self,
                 file_uuid: str,
                 title: str,
                 label: str,
                 media_type: str,
                 content_path: str,
                 client: SlivkaClient):
        self._file_uuid = file_uuid
        self._title = title
        self._label = label
        self._mime_type = media_type
        self._content_url = client.build_url(content_path)
        self._client = client

    @classmethod
    def new_from_json(cls, json_obj: dict, client: SlivkaClient):
        return cls(
            file_uuid=json_obj['uuid'],
            title=json_obj['title'],
            label=json_obj['label'],
            media_type=json_obj['mimetype'],
            content_path=json_obj['contentURI'],
            client=client
        )

    @property
    def uuid(self) -> str:
        return self._file_uuid

    @property
    def title(self) -> str:
        return self._title

    @property
    def label(self) -> str:
        return self._label

    @property
    def media_type(self) -> str:
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
        return '<File %s [%s]>' % (self.label, self.uuid)


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

class FieldType(enum.Enum):
    INTEGER = 'integer'
    INT = 'integer'
    DECIMAL = 'decimal'
    FLOAT = 'decimal'
    BOOLEAN = 'boolean'
    FLAG = 'flag'
    TEXT = 'text'
    FILE = 'file'
    CHOICE = 'choice'


class FormField(metaclass=abc.ABCMeta):
    type = None

    def __init__(self, name, required, default, label, description, multiple):
        self._name = name
        self._required = required
        self._default = default
        self._label = label
        self._description = description
        self._multiple = multiple

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

    @property
    def multiple(self):
        return self._multiple

    @abc.abstractmethod
    def validate(self, value):
        pass

    @classmethod
    def make_field(cls, json_obj) -> 'FormField':
        field_type = FieldType[json_obj['type'].upper()]
        kwargs = {
            'name': json_obj['name'],
            'required': json_obj['required'],
            'default': json_obj.get('default'),
            'label': json_obj['label'],
            'description': json_obj.get('description', ''),
            'multiple': json_obj.get('multiple', False)
        }
        if field_type == FieldType.INTEGER:
            return IntegerField(
                **kwargs,
                min=json_obj.get('min'),
                max=json_obj.get('max')
            )
        elif field_type == FieldType.DECIMAL:
            return DecimalField(
                **kwargs,
                min=json_obj.get('min'),
                max=json_obj.get('max'),
                min_exclusive=json_obj.get('minExclusive', False),
                max_exclusive=json_obj.get('maxExclusive', False)
            )
        elif field_type == FieldType.BOOLEAN:
            return BooleanField(**kwargs)
        elif field_type == FieldType.TEXT:
            return TextField(
                **kwargs,
                min_length=json_obj.get('minLength'),
                max_length=json_obj.get('maxLength')
            )
        elif field_type == FieldType.CHOICE:
            return ChoiceField(**kwargs, choices=json_obj['choices'])
        elif field_type == FieldType.FILE:
            return FileField(
                **kwargs,
                media_type=json_obj.get('mimetype'),
                extension=json_obj.get('extension'),
                max_size=json_obj.get('maxSize')
            )


class IntegerField(FormField):
    type = FieldType.INTEGER

    def __init__(self, *, min, max, **kwargs):
        super().__init__(**kwargs)
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

    def __repr__(self):
        return (
            "IntegerField(name={}, required={}, default={}, min={}, max={})"
            .format(self.name, self.required, self.default, self.min, self.max)
        )


class DecimalField(FormField):
    type = FieldType.DECIMAL

    def __init__(self, *, min, min_exclusive, max, max_exclusive, **kwargs):
        super().__init__(**kwargs)
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

    def __repr__(self):
        return (
            "DecimalField(name={}, required={}, default={}, min={}, max={}, min_exc={}, max_exc={})"
            .format(self.name, self.required, self.default, self.min, self.max,
                    self.min_exclusive, self.max_exclusive)
        )


class TextField(FormField):
    type = FieldType.TEXT

    def __init__(self, *, min_length, max_length, **kwargs):
        super().__init__(**kwargs)
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

    def __repr__(self):
        return (
            "TextField(name={}, required={}, default={}, min_length={}, max_length={})"
            .format(self.name, self.required, self.default, self.min_length, self.max_length)
        )


class BooleanField(FormField):
    type = FieldType.BOOLEAN

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

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

    def __repr__(self):
        return (
            "BooleanField(name={}, required={}, default={})"
            .format(self.name, self.required, self.default)
        )


class ChoiceField(FormField):
    type = FieldType.CHOICE

    def __init__(self, *, choices, **kwargs):
        super().__init__(**kwargs)
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

    def __repr__(self):
        return (
            "ChoiceField(name={}, required={}, default={}, choices={})"
            .format(self.name, self.required, self.default, self.choices)
        )


class FileField(FormField):
    type = FieldType.FILE

    def __init__(self, *, media_type, extension, max_size, **kwargs):
        super().__init__(**kwargs)
        self._media_type = media_type
        self._extension = extension
        self._max_size = max_size

    @property
    def max_size(self):
        return self._max_size

    @property
    def extension(self):
        return self._extension

    @property
    def media_type(self):
        return self._media_type

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

    def __repr__(self):
        return (
            "FileField(name={}, required={}, default={}, mime_type={})"
            .format(self.name, self.required, self.default, self.media_type)
        )
