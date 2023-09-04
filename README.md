Introduction
============

Slivka python client is a convenience wrapper around the popular [requests](https://requests.readthedocs.io/en/latest/) library for Python.
It is designed to provide an interface for communicating with the slivka REST API using Python.

It includes:

- Programmatic access to slivka API with simple objects
- Command-line interface
- Interactive widgets for Jupyter notebooks

Installation
============

The easiest way to install the slivka client is through the conda package manager.
Install it from the *slivka* channel using

```
conda install -c slivka slivka-client 
```

Alternatively, you can install it from sources. Clone the git repository to your
machine and run

```
python setup.py install
```

After the installation has completed successfully, you can import slivka_client
from Python or run `slivka-cli` command line tool.

Usage
=====

To begin, import `slivka_client` library and create a `SlivkaClient` instance using the server URL. 

```python
import slivka_client

client = slivka_client.SlivkaClient("http://www.example.org/slivka/")
```

> [!IMPORTANT]
> Remember that locations typically end with a slash. Missing trailing slash may result
> in resources not being located properly.

In order to verify the server was found successfully, you may query the version of slivka from the server.

```python
>>> client.version
Version(client='1.2.1b1', server='0.8.1', API='1.1')
```

The version displays the current client version, server version and
API compatibility version.

If you see an `HTTPError: 404` exception, check the URL the client tries to access and
make sure the server is available under that address. The error may be caused by a missing
trailing slash in the URL.

Services
--------

A list of all available services can be retrieved using the `services` property of the `SlivkaClient` object. 

```python
>>> client.services
[Service(...), Service(...), Service(...), ...]
```

Each element of that list represents a single service. It contains its id, name, description, parameters, etc.
The list is retrieved from the server only once and is cached to improve performance on subsequent access to the services.
If you expect the services list to change on the server side you can force reloading them with the `reload_services()` method.

```python
client.reload_services()
```

For convenience, you can get a particular service by its id using the `get_service(id)` method or
by a dictionary item access on a client object.

```python
>>> client.get_service('example')
Service(id='example', name='Example', ...)

>>> client['example']
Service(id='example', name='Example', ...)
```

The `Service` objects provide the following read-only properties:

<dl>
<dt>id</dt>
<dd>identifier of the service</dd>

<dt>url</dt>
<dd>location of the service resource</dd>

<dt>name</dt>
<dd>name of the service</dd>

<dt>description</dt>
<dd>long description of the service</dd>

<dt>author</dt>
<dd>one or more authors of the service</dd>

<dt>version</dt>
<dd>version of the service</dd>

<dt>license</dt>
<dd>license of the service<dd>

<dt>classifiers</dt>
<dd>list of classifiers, tags or categories that help identify or group services</dd>

<dt>parameters</dt>
<dd>list of service parameters represented as <code>Parameter</code> objects (explained below)</dd>

<dt>presets</dt>
<dd>
list of parameter presets offered for this service

<dl>
<dt>Preset.id</dt>
<dd>preset identifier</dd>
<dt>Preset.name</dt>
<dd>name of the preset</dd>
<dt>Preset.description</dt>
<dd>long description of the preset</dd>
<dt>Preset.values</dt>
<dd>dictionary of parameter value <code>Dict[str, Any]</code></dd>
</dl>
</dd>

<dt>status</dt>
<dd>
service operation status
<dl>
<dt>Status.status</dt>
<dd>status name; one of: <em>OK</em>, <em>WARNING</em>, <em>DOWN</em></dd>
<dt>Status.message</dt>
<dd>error message</dd>
<dt>Status.timestamp</dt>
<dd>the time the status was last updated</dd>
</dl>
</dd>
</dl>

### Parameters

Each object in the *parameters* list describes a parameter that can be provided
for the service. For each parameter present in the list, you can provide one
(sometimes multiple) value when submitting the job.
All parameter objects offer the following read-only properties:

<dl>
<dt>id</dt>
<dd>parameter identifier; use it as a key in the data dictionary when submitting jobs.</dd>
<dt>type</dt>
<dd>
parameter type; one of: <em>integer</em>, <em>decimal</em>, <em>text</em>, <em>flag</em>, <em>choice</em>, <em>file</em>, <em>undefined</em>, <em>unknown</em>
</dd>
<dt>name</dt>
<dd>human-friendly name of the parameter</dd>
<dt>description</dt>
<dd>longer description of the parameter</dd>
<dt>required</dt>
<dd>if the parameter is required</dd>
<dt>array</dt>
<dd>if multiple values are allowed for the parameter</dd>
<dt>default</dt>
<dd>default value for the parameter that is used if none is provided</dd>
</dl>

More specialised data structures exist for each type and provide additional properties
specific to that type.

Starting jobs
-------------

New jobs are submitted to the server using `submit_job()` method of the *Service*
object. The method takes two arguments *data* and *files* which are both
dictionaries containing parameter ids and corresponding values.
The values are properly encoded and sent as a POST request to the server.
Values for the parameters that require a file as an input need to be provided
through the *files* argument to ensure the HTTP request includes the contents
of the file.

Values provided in the *data* dictionary are converted to strings automatically.
Values provided in the *files* dictionary can be open files or streams,
in which case the content of the stream is sent to the server, or bytes, which are sent directly.

> [!IMPORTANT]
> Files and streams should be opened in binary mode to avoid potential issues with
> non-ascii characters.

On successful job submission the method returns a *Job* object containing
submission data. This object is used to check job status and retrieve
results.
If the input parameter are not valid, the method throws a *SubmissionError*
containing a list of errors encountered during input processing. 

Example:

```python
>>> service = client['example']
>>> job = service.submit_job(
...   data={
...     'param0': 13,
...     'param1': 'foobar'
...   },
...   files={
...     'input0': open("input-file.txt", "rb"),
...     'input1': b"data data data data\n"
...   }
... )
```

Polling jobs and retrieving results
-----------------------------------

The *Job* object returned by the `submit_job()` method provides the capability
to inspect submission data and poll the status of the submitted job and
retrieve result files from the server.

The 'id' property of the job object holds a server-generated identifier, uniquely denoting the job within the server's context.
The job additionally holds *service*, *parameters* and *submission_time* information.

The current job status can be obtained using a *status* property which gets updated
from the server every time it is accessed but no more frequently than once every five seconds.

The result files can be accessed with a *results* property. Just like *status*, the *results*
is updated from the server every time it is accessed. It returns a list of *slivka_client.File*
objects which can be used to inspect file metadata and download their content.

> [!NOTE]
> If you lose the *Job* object either by deleting a variable or restarting
> the Python interpreter, you can re-create that object using *Client.get_job()*
> method providing it with the job id.

### File

The file objects you receive from the slivka client are not actual files you could
read from. Instead, they are referencing the resources located on the server and can
be dumped to actual files or streams instead using `dump()` method.
The argument to the `dump()` method can be a stream or a file opened in either
text or binary mode, or a file name. In case of streams or files, the result
is downloaded from the server and appended to the stream. If a file name is
provided, a new file is created, replacing the existing one if exists, and
the content is written to that file.

Example:

```python
>>> result = job.results[0]

>>> # dumping to open file
>>> result.dump(open("out.txt", "w"))

>>> # dumping to in-memory stream
>>> input_stream = io.BytesIO()
>>> result.dump(input_stream)

>>> # creating new file
>>> result.dump("out.txt")
```

Additionally, the *File* object provides the following properties:

| Property      | Description                                                      |
|---------------|------------------------------------------------------------------|
| *url*         | Location of the resource                                         |
| *content_url* | Location of the file content                                     |
| *id*          | Identifier of the file which can be used as input for other jobs |
| *job_id*      | Id of the job this file is a result of                           |
| *path*        | Real path and name of the file                                   |
| *label*       | Name describing the file                                         |
| *media_type*  | Media type of the file                                           |

