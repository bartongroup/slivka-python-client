import asyncio
import functools

import ipywidgets
from IPython.core.display import display, Markdown

from . import *


def display_form(form: Form):
    widgets = [_widget_factory(field) for field in form]
    box = ipywidgets.VBox(widgets)
    box.layout.border = '1px solid black'
    box.layout.padding = '5px'
    submit = ipywidgets.Button(description='Submit')
    submit.on_click(functools.partial(submit_event_handler, form, widgets))
    display(box, submit)


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


def submit_event_handler(form, widgets, button):
    button.disabled = True
    form.reset()
    try:
        for widget in widgets:
            value = widget.value
            field = form[widget.field_name]
            if isinstance(field, FileField):
                name, data = next(iter(value.items()))
                content = io.BytesIO(data['content'])
                value = form._client.upload_file(
                    content, name, field.media_type or 'text/plain'
                )
            form.insert({field.name: value})
        job_id = form.submit()
    except FormValidationError:
        button.disabled = False
        raise
    else:
        display('job {} submitted successfully'.format(job_id))
        task = asyncio.create_task(wait_for_result(form._client, job_id))
        def enable_button(_): button.disabled = False
        task.add_done_callback(enable_button)


async def wait_for_result(cli, job_id):
    status = JobState.QUEUED
    while status in (JobState.QUEUED, JobState.PENDING, JobState.RUNNING):
        await asyncio.sleep(1)
        status = cli.get_job_state(job_id)
    files = cli.get_job_results(job_id)
    lines = ['Output: \n']
    for file in files:
        lines.append('- [%s](%s)' % (file.label, file.url))
    display(Markdown(str.join('\n', lines)))
