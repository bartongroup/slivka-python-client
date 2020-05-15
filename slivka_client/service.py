from typing import Callable, Sequence

import requests

from .form import Form, _build_form


class Service:
    """
    A class representing one of the services on the server.
    """

    def __init__(self,
                 name: str, label: str, path: str,
                 classifiers: Sequence[str],
                 url_factory: Callable[[str], str]):
        self._name = name
        self._label = label
        self._url = url_factory(path)
        self._classifiers = classifiers
        self._build_url = url_factory
        self._form = None

    name = property(lambda self: self._name)
    label = property(lambda self: self._label)
    url = property(lambda self: self._url)
    classifiers = property(lambda self: self._classifiers)

    def new_form(self) -> Form:
        if self._form is None:
            self.refresh_form()
        return self._form.copy()
    form = property(new_form)

    def refresh_form(self):
        response = requests.get(self.url)
        response.raise_for_status()
        self._form = _build_form(response.json(), self._build_url)

    def __repr__(self):
        return 'SlivkaService(%s)' % self.name
