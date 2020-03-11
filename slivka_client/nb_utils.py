import io

import ipywidgets
from IPython.core.display import display, Markdown
from .form import (_BaseField, IntegerField, DecimalField, TextField,
                   BooleanField, ChoiceField, FileField, Form)


class NotebookForm:
    def __init__(self, form: Form):
        self._form = form
        self._widgets = list(map(_widget_factory, form))
        self._widget_box = ipywidgets.VBox(self._widgets)
        self._widget_box.layout.border = '1px solid black'
        self._submit = ipywidgets.Button(description='Submit')
        self._submit.on_click(self._on_submit)
        self.jobs = []

    def _ipython_display_(self):
        self.display()

    def display(self):
        display(self._widget_box, self._submit)

    def _on_submit(self, *args):
        self._form.clear()
        self._submit.disabled = True
        try:
            for widget in self._widgets:
                val = widget.value
                if isinstance(widget, ipywidgets.FileUpload):
                    try:
                        name, data = next(iter(val.items()))
                        val = io.BytesIO(data['content'])
                    except StopIteration:
                        val = None
                self._form[widget.field_name] = val
            job_id = self._form.submit()
            self.jobs.append(job_id)
            display(Markdown('job *%s* submitted successfully.' % job_id))
        finally:
            self._submit.disabled = False

    def get_last_job(self): return self.jobs[-1]
    last_job = property(get_last_job)


def _widget_factory(field: _BaseField):
    kwargs = {
        'description': field.label,
        'description_tooltip': field.description
    }
    if isinstance(field, IntegerField):
        widget = ipywidgets.BoundedIntText(
            value=field.default,
            min=field.min,
            max=field.max,
            **kwargs
        )
    elif isinstance(field, DecimalField):
        widget = ipywidgets.BoundedFloatText(
            value=field.default,
            min=field.min,
            max=field.max,
            **kwargs
        )
    elif isinstance(field, TextField):
        widget = ipywidgets.Text(
            placeholder=field.default,
            **kwargs
        )
    elif isinstance(field, BooleanField):
        widget = ipywidgets.Checkbox(
            value=field.default,
            **kwargs
        )
    elif isinstance(field, ChoiceField):
        kwargs.update(options=field.choices)
        if field.multiple:
            widget = ipywidgets.SelectMultiple(value=[field.default], **kwargs)
        elif len(field.choices) <= 5:
            widget = ipywidgets.RadioButtons(value=field.default, **kwargs)
        else:
            widget = ipywidgets.Dropdown(value=field.default, **kwargs)
    elif isinstance(field, FileField):
        widget = ipywidgets.FileUpload(
            accept=field.media_type or '',
            **kwargs
        )
    else:
        raise TypeError(type(field))
    widget.field_name = field.name
    return widget
