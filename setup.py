import os.path

from setuptools import setup


def get_version(path):
    here = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(here, path)) as fp:
        for line in fp:
            if line.startswith('__version__'):
                delim = '"' if '"' in line else '\''
                return line.split(delim)[1]
        else:
            raise RuntimeError("Unable to find version string.")


setup(
    name='slivka-client',
    version=get_version('slivka_client/__init__.py'),
    packages=['slivka_client'],
    install_requires=[
        'attrs>=19.0',
        'click>=7.1.2',
        'requests>=2.13.0'
    ],
    entry_points={
        'console_scripts': [
            "slivka-cli = slivka_client.__main__:main"
        ]
    }
)
