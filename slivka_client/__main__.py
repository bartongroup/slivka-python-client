import collections
import os
import textwrap

import attr
import click

from slivka_client import Service
from .client import SlivkaClient


@click.group()
@click.version_option("1.2", prog_name='slivka-cli')
@click.option("--host", metavar="URL", help="Slivka server url.",
              default="https://www.compbio.dundee.ac.uk/slivka/")
@click.pass_context
def main(ctx: click.Context, host):
    obj = ctx.ensure_object(dict)
    obj['client'] = SlivkaClient(host)


@main.command()
@click.option("--name", help="Show one service by name.", metavar="NAME")
@click.option("--terse", is_flag=True, help="Short output.")
@click.pass_obj
def services(obj, name, terse):
    client: SlivkaClient = obj['client']
    if name:
        service = client.get_service(name)
        _print_service(service, terse)
    else:
        for service in client.services:
            _print_service(service, terse)


def _print_service(service, terse=False):
    if terse:
        click.echo(service.name)
    else:
        click.echo(f"{service.id}: {service.name}")
        click.echo("classifiers:")
        text = textwrap.indent('\n'.join(service.classifiers), ' - ')
        click.echo(text)
        click.echo("fields:")
        lines = []
        for param in service.parameters:
            attrs = attr.asdict(param, filter=lambda _, val: val is not None,
                                dict_factory=collections.OrderedDict)
            line = f"{attrs.pop('name')}: {attrs.pop('type')}; "
            line += ", ".join(
                f"{key.replace('_', '-')}={val}"
                for key, val in attrs.items()
            )
            lines.append(line)
        text = textwrap.indent('\n'.join(lines), ' - ')
        click.echo(text)


@main.command()
@click.option("--terse", is_flag=True, help="Short output.")
@click.argument("service")
@click.argument("values", nargs=-1, metavar="KEY=VALUE...")
@click.pass_obj
def submit(obj, service, values, terse):
    client: SlivkaClient = obj['client']
    service: Service = client.get_service(service)
    data = []
    files = []
    for arg in values:
        k, v = arg.split('=', 1)
        if v.startswith('@'):
            files.append((k, open(v[1:], 'rb')))
        else:
            data.append((k, v))
    jid = service.submit_job(data, files)
    if terse:
        click.echo(jid)
    else:
        click.echo(f"Job {jid} submitted successfully.")


@main.command()
@click.option("--terse", is_flag=True, help="Short output.")
@click.argument("job-id")
@click.pass_obj
def status(obj, job_id, terse):
    client: SlivkaClient = obj['client']
    job = client.get_job(job_id)
    if terse:
        click.echo(job.status)
    else:
        click.echo(f"The job status is: {job.status}")


@main.command()
@click.option("--download/--no-download", is_flag=True, default=False,
              help="Choose whether to download files.", show_default=True)
@click.option("--directory", type=click.Path(file_okay=False, dir_okay=True),
              default=os.curdir, help="Change download directory.")
@click.option("--overwrite", default="prompt", show_default=True,
              type=click.Choice(["yes", "no", "prompt"], case_sensitive=False),
              help="Set overwriting behaviour for existing files.")
@click.argument("job-id")
@click.pass_obj
def files(obj, job_id, download, directory, overwrite):
    client: SlivkaClient = obj['client']
    job = client.get_job(job_id)
    for file in job.files:
        click.echo(f"{file.id}: {file.label}; "
                   f"content-type={file.media_type}")
        if download:
            if not os.path.exists(directory):
                os.makedirs(directory)
            fp = os.path.join(directory, file.path)
            if os.path.dirname(file.path):
                os.makedirs(os.path.dirname(fp), exist_ok=True)
            if os.path.exists(fp):
                if overwrite == "prompt":
                    if not click.confirm(f"File {fp} exists. Overwrite?"):
                        click.echo("Skipping.")
                        continue
                elif overwrite == "no":
                    click.echo(f"File {fp} exists. Skipping.")
            file.dump(fp)


if __name__ == '__main__':
    main()
