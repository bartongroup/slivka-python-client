from slivka_client import SlivkaClient


slivka_server_url = 'https://www.compbio.dundee.ac.uk/dev/slivka/'
client = SlivkaClient(slivka_server_url)

for service in client.services:
    print(f"Service name: {service.name}, ID: {service.url}")
    
# ClustalO test
service = client['clustalo']
print(f"Selected service: {service.name} (ID: {service.id})")
    
# Define parameters for the job
data = {
    'iterations': 1,
    'max-guidetree-iterations': 1,
    'max-hmm-iterations': 1,
}

# Specify the input file path
input_file_path = 'data/fam83b-pandda-chains-for-align-test.fa'

# Submit the job with the input file
with open(input_file_path, 'rb') as file_object:
    files = {'input': file_object}
    job = service.submit_job(data=data, files=files)
    print(f"Job submitted with ID: {job.id}")


# Colabfold test
service = client['colabfold']
print(f"Selected service: {service.name} (ID: {service.id})")

# Define parameters for the job
data = {}

# Specify the input file path
input_file_path = 'data/andr_human.fa'

# Submit the job with the input file
with open(input_file_path, 'rb') as file_object:
    files = {'input': file_object}
    job = service.submit_job(data=data, files=files)
    print(f"Job submitted with ID: {job.id}")