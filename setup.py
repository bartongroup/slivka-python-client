import os.path
from setuptools import setup, find_packages

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
    author='Mateusz Warowny',
    author_email='m.m.z.warowny@dundee.ac.uk',
    maintainer='Stuart MacGowan',
    maintainer_email='smacgowan@dundee.ac.uk',
    description='A Python client for Slivka services',
    long_description=open('README.md', encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/bartongroup/slivka-python-client',
    packages=find_packages(),
    install_requires=[
        'attrs>=19.3',
        'click>=7.0',
        'requests>=2.13.0'
    ],
    entry_points={
        'console_scripts': [
            'slivka-cli = slivka_client.__main__:main',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering :: Bio-Informatics',
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
    keywords=[
        'slivka',
        'client',
        'bioinformatics',
        'computational biology',
        'REST API'
    ],
    project_urls={
        'Documentation': 'https://github.com/bartongroup/slivka-python-client#readme',
        'Source': 'https://github.com/bartongroup/slivka-python-client',
        'Tracker': 'https://github.com/bartongroup/slivka-python-client/issues',
        'Organization': 'https://www.compbio.dundee.ac.uk/drsasp.html',
    },
)
