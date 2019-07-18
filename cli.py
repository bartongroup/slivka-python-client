import json
import os
import sys
from fnmatch import fnmatch

import click
from click import ClickException

from slivka_client import SlivkaClient, IntegerField, DecimalField, BooleanField, FileField

HOST = 'gjb-www-1.cluster.lifesci.dundee.ac.uk'
PORT = 3203


class ConfigLoader:
    GLOBAL = 'global'
    LOCAL = 'local'
    ANY = 'any'

    def __init__(self, location=ANY):
        self._path = self.find_file_path(location)
        self._dirty = False
        with open(self._path) as fp:
            self._json_data = json.load(fp)
        if 'config' not in self._json_data:
            self._json_data['config'] = {}
        if 'tasks' not in self._json_data:
            self._json_data['tasks'] = []

    @property
    def path(self):
        return self._path

    def __getitem__(self, item):
        return self._json_data['config'][item]

    def __setitem__(self, key, value):
        self._dirty = True
        self._json_data['config'][key] = value

    def __iter__(self):
        return iter(self._json_data['config'].items())

    def find_file_path(self, location):
        fname = 'slivka.json'
        global_path = os.path.join(click.get_app_dir('slivka-client'), fname)
        local_path = os.path.join(os.path.curdir, fname)
        if location == self.GLOBAL:
            path = global_path
        elif location == self.LOCAL:
            path = local_path
        elif location == self.ANY:
            path = (global_path
                    if os.path.isfile(global_path) and not os.path.isfile(local_path)
                    else local_path)
        else:
            raise ValueError
        if not os.path.isfile(path):
            with open(path, 'a') as fp:
                json.dump({}, fp)
        return path

    def all_tasks(self):
        return [(item['name'], item['uuid']) for item in self._json_data['tasks']]

    def get_task_by_name(self, name):
        return [
            (item['name'], item['uuid']) for item in self._json_data['tasks']
            if fnmatch(item['name'], name)
        ]

    def get_task_by_uuid(self, uuid):
        return next(
            ((item['name'], item['uuid'])
             for item in self._json_data['tasks'] if uuid == item['uuid']),
            ('untitled', uuid)
        )

    def add_task(self, task, name):
        self._dirty = True
        self._json_data['tasks'].append({
            "name": name,
            "uuid": task.uuid,
            "url": str(task.url)
        })

    def save(self):
        if self._dirty:
            with open(self._path, 'w') as fp:
                json.dump(self._json_data, fp, indent=2)


def print_version(ctx, param, value):
    if value:
        click.echo('Slivka Client version 1.0')
        ctx.exit()


@click.group()
@click.version_option('1.0', prog_name='slivka-client')
def main():
    pass


@click.command('config')
@click.option('--dump', type=click.File('w'))
@click.option('--show', '--list', '-l', 'show', is_flag=True)
@click.option('--set', 'new_values', nargs=2, metavar='KEY VAL', multiple=True)
@click.option('--local', 'conf_location', flag_value='local', default=True)
@click.option('--global', 'conf_location', flag_value='global')
def config(show, dump, new_values, conf_location):
    conf = ConfigLoader(conf_location)
    for key, value in new_values:
        conf[key] = value
    conf.save()
    if dump:
        dump.write(open(conf.path).read())
    if show:
        for key, value in conf:
            click.echo('{}: {}'.format(key, value))


@click.group('service')
def service():
    pass


@click.command('list')
@click.option('--all', '-a', 'show_all', is_flag=True)
@click.option('--name', '-n')
@click.option('--fields', '-f', 'show_fields', is_flag=True)
def service_list(show_all, name, show_fields):
    conf = ConfigLoader()
    try:
        cli = SlivkaClient(conf['host'], int(conf['port']))
    except KeyError as e:
        raise ClickException(
            "You must set \"{}\" in configuration.".format(e.args[0])
        )
    if show_all:
        for service in cli.get_services():
            click.echo(service.name)
    elif name:
        service = cli.get_service(name)
        click.echo(service.name)
        if show_fields:
            form = service.get_form()
            for name, field in form.fields.items():
                click.echo('{}: {}'.format(name, field))


@click.command('submit')
@click.option('--service', '-s', required=True)
@click.option('--name', '-n', default='untitled')
@click.argument('values', nargs=-1)
def service_submit(service, name, values):
    conf = ConfigLoader()
    try:
        cli = SlivkaClient(conf['host'], int(conf['port']))
    except KeyError as e:
        raise ClickException(
            "You must set \"{}\" in configuration.".format(e.args[0])
        )
    service = cli.get_service(service)
    form = service.get_form()
    for arg in values:
        k, v = arg.split('=', 1)
        field = form.fields.get(k)
        if isinstance(field, IntegerField):
            v = int(v)
        elif isinstance(field, DecimalField):
            v = float(v)
        elif isinstance(field, BooleanField):
            v = v.lower() not in {'no', 'false', '0', 'null', 'n', 'f'}
        elif isinstance(field, FileField):
            v = cli.get_remote_file(v)
        form.insert({k: v})
    task = form.submit()
    conf.add_task(task, name )
    conf.save()
    click.echo('Task {} submitted successfully.'.format(task.uuid))


@click.command('task')
@click.option('--all', '-a', 'show_all', is_flag=True)
@click.option('--name', '-n', 'task_name')
@click.option('--uuid', '-u', 'task_uuid', type=click.UUID)
def task(show_all, task_name, task_uuid):
    conf = ConfigLoader()
    try:
        cli = SlivkaClient(conf['host'], int(conf['port']))
    except KeyError as e:
        raise ClickException(
            "You must set \"{}\" in configuration.".format(e.args[0])
        )
    if task_name:
        for name, uuid in conf.get_task_by_name(task_name):
            task = cli.get_task(uuid)
            status = task.get_status()
            click.echo('{} [{}]: {}'.format(name, uuid, status.status))
    elif task_uuid:
        name, uuid = conf.get_task_by_uuid(task_uuid.hex)
        task = cli.get_task(uuid)
        status = task.get_status()
        click.echo('{} [{}]: {}'.format(name, uuid, status.status))
    elif show_all:
        for name, uuid in conf.all_tasks():
            task = cli.get_task(uuid)
            status = task.get_status()
            click.echo('{} [{}]: {}'.format(name, uuid, status.status))


@click.command('file')
@click.option('--uuid', '-u', type=click.UUID, required=True)
@click.option('--output', '-o', type=click.File('wb', lazy=False))
def file(uuid, output):
    conf = ConfigLoader()
    try:
        cli = SlivkaClient(conf['host'], int(conf['port']))
    except KeyError as e:
        raise ClickException(
            "You must set \"{}\" in configuration.".format(e.args[0])
        )
    remote_file = cli.get_remote_file(uuid.hex)
    remote_file.dump(output or sys.stdout)


main.add_command(config)
main.add_command(service)
service.add_command(service_list)
service.add_command(service_submit)
main.add_command(task)
main.add_command(file)
