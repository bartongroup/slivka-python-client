
# Slivka Python Client

[![PyPI version](https://badge.fury.io/py/slivka-client.svg)](https://badge.fury.io/py/slivka-client)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

Slivka Python client is a convenience wrapper around the popular [requests](https://requests.readthedocs.io/en/latest/) library. It provides an interface for communicating with the Slivka REST API using Python.

## Features

- Programmatic access to Slivka API with simple objects.
- Command-line interface.
- Interactive widgets for Jupyter notebooks.

---

## Installation

The easiest way to install the Slivka client is via `pip` from PyPI:

```bash
pip install slivka-client
```

Alternatively, if you prefer to use the conda package manager, you can install it from the Slivka channel:

```bash
conda install -c slivka slivka-client
```

To install it from the source code, clone the Git repository to your machine and run:

```bash
python setup.py install
```

---

## Getting Started

After installing the Slivka client, you can begin by importing it and connecting to a Slivka server:

```python
import slivka_client

# Replace with your actual server URL
client = slivka_client.SlivkaClient("https://your-slivka-server-url/")
```

You can verify the connection by checking the server version:

```python
print(client.version)
```

---

## Usage

### Accessing Services

To retrieve the list of available services from the Slivka server:

```python
services = client.services
```

Each element in the list is a `Service` object containing details such as the service's `id`, `name`, and `description`.

To access a specific service by its ID, use:

```python
service = client.get_service('example_service_id')
# Or
service = client['example_service_id']
```

---

### Starting Jobs

Once you've selected the desired service, you can submit jobs using the `submit_job()` method. This requires providing parameters in the form of dictionaries.

Here’s an example of submitting a job:

```python
data = {
    'param0': 13,
    'param1': 'foobar'
}

files = {
    'input0': open("input-file.txt", "rb"),
    'input1': b"data data data data\n"
}

job = service.submit_job(data=data, files=files)
```

This method returns a `Job` object that allows you to monitor the status and retrieve results.

### Polling Jobs and Retrieving Results

You can check the status of a submitted job using:

```python
print(job.status)
```

To retrieve the results:

```python
for result in job.results:
    result.dump("output_file.txt")
```

### File Handling

The `File` object provides a convenient way to download results:

```python
result = job.results[0]
result.dump("output_file.txt")
```

The `File` object properties include:

- **url**: Location of the resource.
- **content_url**: Location of the file content.
- **id**: Identifier of the file (can be used as input for other jobs).
- **job_id**: ID of the job this file is a result of.
- **path**: Real path and name of the file.
- **label**: Name describing the file.
- **media_type**: Media type of the file.

---

## Command-Line Interface (CLI)

The `slivka-cli` command-line tool allows for interaction with the Slivka API without writing Python scripts.

To get started:

```bash
slivka-cli --help
```

This will provide you with usage instructions and available commands.

---

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

---

## Support

If you have any questions or need assistance, please open an issue on our [GitHub repository](https://github.com/bartongroup/slivka-python-client/issues).
