from datetime import datetime
from typing import List, Any, Dict
from urllib.parse import urljoin

import attr
import requests

from .job import Job


@attr.s(frozen=True)
class Service:
    @attr.s(frozen=True)
    class Preset:
        id: str = attr.ib()
        name: str = attr.ib()
        description: str = attr.ib()
        values: Dict[str, Any] = attr.ib()

    @attr.s(frozen=False)
    class Status:
        status: str = attr.ib()
        message: str = attr.ib()
        timestamp: datetime = attr.ib(
            converter=lambda ds: datetime.strptime(ds, "%Y-%m-%dT%H:%M:%S")
        )

    url: str = attr.ib()
    id: str = attr.ib()
    name: str = attr.ib()
    description: str = attr.ib()
    author: str = attr.ib()
    version: str = attr.ib()
    license: str = attr.ib()
    classifiers: List[str] = attr.ib()
    parameters: List['_BaseParameter'] = attr.ib()
    presets: List[Preset] = attr.ib()
    status: Status = attr.ib()

    def submit_job(self, data=None, files=None):
        response = requests.post(self.url + '/jobs', data=data, files=files)
        if response.status_code == 422:
            response = response.json()
            raise SubmissionError([
                ParameterValueError(e['parameter'], e['message'], e['errorCode'])
                for e in response['errors']
            ])
        response.raise_for_status()
        return Job.from_response(self.url, response.json())

    @staticmethod
    def from_response(host, response):
        return Service(
            url=urljoin(host, response['@url']),
            id=response['id'],
            name=response['name'],
            description=response.get('description', ''),
            author=response.get('author', ''),
            version=response.get('version'),
            license=response.get('license'),
            classifiers=response.get('classifiers', []),
            parameters=list(map(_create_parameter, response['parameters'])),
            presets=[Service.Preset(**kw) for kw in response.get('presets', [])],
            status=Service.Status(
                status=response['status']['status'],
                message=response['status']['errorMessage'],
                timestamp=response['status']['timestamp']
            )
        )


class ParameterValueError(ValueError):
    def __init__(self, parameter, message, code):
        ValueError.__init__(self, f"Invalid value for '{parameter}': {message}")
        self.parameter = parameter
        self.message = message
        self.code = code


class SubmissionError(ValueError):
    def __init__(self, errors):
        Exception.__init__(self, ', '.join(map(str, errors)))
        self.errors = errors


@attr.s(slots=True, frozen=True)
class _BaseParameter:
    """
    The base for other fields.
    This class is never instantiated directly but provides common
    attributes for deriving types.
    """
    id = attr.ib(type=str)
    type = attr.ib(type=str, repr=False)
    name = attr.ib(type=str)
    description = attr.ib(type=str, default="", repr=False)
    required = attr.ib(type=bool, default=True)
    array = attr.ib(type=bool, default=False)
    default = attr.ib(default=None)


@attr.s(slots=True, frozen=True)
class UndefinedParameter(_BaseParameter):
    """
    Class for undefined fields.
    """
    type = attr.ib(default='undefined', init=False, repr=False)


@attr.s(slots=True, frozen=True)
class CustomParameter(_BaseParameter):
    type = attr.ib(default='unknown', repr=True)
    attributes = attr.ib(type=dict, factory=dict)
    "dictionary of field parameters as provided by the server"

    def __getitem__(self, key):
        return self.attributes[key]


@attr.s(slots=True, frozen=True)
class IntegerParameter(_BaseParameter):
    type = attr.ib(default='integer', init=False, repr=False)
    min = attr.ib(type=int, default=None)
    "minimum value constraint"
    max = attr.ib(type=int, default=None)
    "maximum value constraint"


@attr.s(slots=True, frozen=True)
class DecimalParameter(_BaseParameter):
    type = attr.ib(default='decimal', init=False, repr=False)
    min = attr.ib(type=float, default=None)
    "minimum value constraint"
    max = attr.ib(type=float, default=None)
    "maximum value constraint"
    min_exclusive = attr.ib(type=bool, default=False)
    "whether the minimum value is excluded"
    max_exclusive = attr.ib(type=bool, default=False)
    "whether the maximum value is excluded"


@attr.s(slots=True, frozen=True)
class TextParameter(_BaseParameter):
    type = attr.ib(default='text', init=False, repr=False)
    min_length = attr.ib(type=int, default=None)
    "minimum length of the text"
    max_length = attr.ib(type=int, default=None)
    "maximum length of the text"


@attr.s(slots=True, frozen=True)
class FlagParameter(_BaseParameter):
    type = attr.ib(default='flag', init=False, repr=False)


@attr.s(slots=True, frozen=True)
class ChoiceParameter(_BaseParameter):
    type = attr.ib(default='choice', init=False, repr=False)
    choices = attr.ib(type=list, default=())
    "list of available choices"


@attr.s(slots=True, frozen=True)
class FileParameter(_BaseParameter):
    type = attr.ib(default='file', init=False, repr=False)
    media_type = attr.ib(type=str, default=None)
    "media type of the file"
    media_type_parameters = attr.ib(type=dict, factory=dict)
    "additional annotations regarding file content"


def _create_parameter(data_dict):
    field_type = data_dict['type']
    kwargs = {
        'id': data_dict['id'],
        'name': data_dict['name'],
        'description': data_dict.get('description', ''),
        'required': data_dict.get('required', True),
        'array': data_dict.get('array', False),
        'default': data_dict.get('default'),
    }
    if field_type == "integer":
        return IntegerParameter(
            **kwargs,
            min=data_dict.get('min'),
            max=data_dict.get('max')
        )
    elif field_type == "decimal":
        return DecimalParameter(
            **kwargs,
            min=data_dict.get('min'),
            max=data_dict.get('max'),
            min_exclusive=data_dict.get('minExclusive', False),
            max_exclusive=data_dict.get('maxExclusive', False)
        )
    elif field_type == "text":
        return TextParameter(
            **kwargs,
            min_length=data_dict.get('minLength'),
            max_length=data_dict.get('maxLength')
        )
    elif field_type == "flag":
        return FlagParameter(**kwargs)
    elif field_type == "choice":
        return ChoiceParameter(
            **kwargs, choices=data_dict['choices']
        )
    elif field_type == "file":
        return FileParameter(
            **kwargs,
            media_type=data_dict.get('mediaType'),
            media_type_parameters=data_dict.get('mediaTypeParameters', {})
        )
    elif field_type == "undefined":
        return UndefinedParameter(**kwargs)
    else:
        return CustomParameter(
            **kwargs,
            type=field_type,
            attributes=data_dict
        )
