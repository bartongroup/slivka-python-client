from setuptools import setup

setup(
    name='slivka-client',
    version='1.1',
    packages=['slivka_client'],
    install_requires=[
        'requests>=2.13.0',
        'urllib3>=1.12',
        'attrs>=19.0',
        'click>=7.1.2'
    ],
    entry_points={
        'console_scripts': [
            "slivka-cli = slivka_client.__main__:main"
        ]
    }
)
