import asyncio
from collections import OrderedDict

import ipywidgets
from IPython.core.display import display, Markdown

from . import *


class NotebookForm:
    def __init__(self, form):
        self.form = form
        self.client = form._client
        self.widgets = list(map(_widget_factory, form))
        self._widget_box = ipywidgets.VBox(self.widgets)
        self._widget_box.layout.border = '1px solid black'
        self._submit = ipywidgets.Button(description='Submit')
        self._submit.on_click(self.on_submit)
        self.jobs = OrderedDict()

    def _ipython_display_(self):
        self.display()

    def display(self):
        display(self._widget_box, self._submit)

    def on_submit(self, button):
        self._submit.disabled = True
        self.form.reset()
        try:
            for widget in self.widgets:
                value = widget.value
                field = self.form[widget.field_name]
                if isinstance(field, FileField):
                    try:
                        name, data = next(iter(value.items()))
                    except StopIteration:
                        value = None
                    else:
                        value = self.client.upload_file(
                            io.BytesIO(data['content']),
                            name,
                            field.media_type or 'text/plain'
                        )
                self.form.insert({field.name: value})
            cleaned_data = self.form.validate()
            job_id = self.form.submit()
        except FormValidationError:
            raise
        else:
            self.jobs[job_id] = {
                'inputs': cleaned_data,
                'state': JobState.PENDING,
                'id': job_id,
                'results': []
            }
            display(Markdown(f'job *{job_id}* submitted successfully.'))
            asyncio.create_task(self.monitor_job_state(job_id))
        finally:
            self._submit.disabled = False

    async def monitor_job_state(self, job_id):
        job = self.jobs[job_id]
        job['state'] = self.client.get_job_state(job_id)
        while not job['state'].is_finished():
            await asyncio.sleep(1)
            job['state'] = self.client.get_job_state(job_id)
        job['results'] = self.client.get_job_results(job_id)
        display(Markdown(f'Job *{job_id}* finished with state {job["state"].name}.'))

    @property
    def job(self):
        return next(reversed(self.jobs.values()), None)

    @property
    def all_jobs(self):
        return self.jobs.values()


def _widget_factory(field: FormField):
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
            accept=field.media_type or field.extension,
            **kwargs
        )
    else:
        raise TypeError(type(field))
    widget.field_name = field.name
    return widget
