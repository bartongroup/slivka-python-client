from setuptools import setup

setup(
    name='slivka-client',
    version='1.0',
    py_modules=['slivka_client'],
    install_requires=[
        'click>=7.0',
        'requests>=2.13.0',
        'urllib3>=1.12'
    ],
    entry_points={
        'console_scripts': [
            'slivka=cli:main'
        ]
    }
)
