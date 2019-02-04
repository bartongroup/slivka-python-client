import abc
from typing import Any

import slivka_client


class FormField(metaclass=abc.ABCMeta):
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
    def from_json(cls, json):
        pass

    @staticmethod
    def build_field(json):
        cls = _type_map[json['type']]
        return cls.from_json(json)


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
    def from_json(cls, json):
        constraints = {
            item['name']: item['value']
            for item in json['constraints']
        }
        return IntegerField(
            required=json['required'],
            default=json['default'],
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
    def from_json(cls, json):
        constraints = {
            item['name']: item['value']
            for item in json['constraints']
        }
        return DecimalField(
            required=json['required'],
            default=json['default'],
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
    def from_json(cls, json):
        constraints = {
            item['name']: item['value']
            for item in json['constraints']
        }
        return TextField(
            required=json['required'],
            default=json['default'],
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
    def from_json(cls, json):
        return BooleanField(
            required=json['required'],
            default=json['default'],
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
    def from_json(cls, json):
        constraints = {
            item['name']: item['value']
            for item in json['constraints']
        }
        return ChoiceField(
            required=json['required'],
            default=json['default'],
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
        if not isinstance(value, slivka_client.FileHandler):
            raise ValidationError(self, 'value', 'Not a FileHandler')
        return value.id

    @classmethod
    def from_json(cls, json):
        constraints = {
            item['name']: item['value']
            for item in json['constraints']
        }
        return FileField(
            required=json['required'],
            default=json['default'],
            mimetype=constraints.get('mimetype'),
            extension=constraints.get('extension'),
            max_size=constraints.get('maxSize')
        )


class ValidationError(Exception):
    def __init__(self, field, code, message):
        super().__init__(message)
        self.field = field
        self.code = code


_type_map = {
    'integer': IntegerField,
    'decimal': DecimalField,
    'choice': ChoiceField,
    'text': TextField,
    'boolean': BooleanField,
    'file': FileField
}
