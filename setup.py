from setuptools import setup

setup(
    name='slivka-client',
    version='1.0',
    py_modules=['slivka_client'],
    install_requires=[
        'Click',
    ],
    entry_points={
        'console_scripts': [
            'slivka=cli:main'
        ]
    }
)
