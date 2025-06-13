import json
import subprocess as sb

input = dict()
input['job'] = dict()
input['job']['name'] = 'test123'
input['job']['ntasks'] = 1
input['job']['nodes'] = 1
input['job']['current_working_directory'] = '/home/reycheng/test'
input['job']['standard_input'] = '/dev/null'
input['job']['standard_output'] = '/home/reycheng/test/job.out'
input['job']['standard_error'] = '/home/reycheng/test/job.err'
input['job']['environment'] = dict()
input['job']['environment']['PATH'] = "/bin:/usr/bin:/usr/local/bin"
input['job']['environment']['LD_LIBRARY_PATH'] = "/lib:/lib64:/usr/local/lib"
input['job']['script'] = "#!/bin/bash\ncov-analyze --version"
with open('input.json', 'w') as outfile:
    json.dump(input, outfile, indent=2)

token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NDI4NTE4OTgsImlhdCI6MTc0MTg1MTg5OSwic3VuIjoicmV5Y2hlbmcifQ.wvB5yw7E26hpUnliF3GEwnvzzebRwOi2htqTqVtbyYw"
cmdCurl = sb.Popen(['curl', '-k', '-X', 'POST', '--url', \
                        'http://172.22.138.70:6820/slurm/v0.0.39/job/submit', \
                        '-H', 'X-SLURM-USER-NAME:reycheng', \
                        '-H', 'X-SLURM-USER-TOKEN:{}'.format(token), \
                        '-H', 'Content-Type: application/json', \
                        '-d', '@input.json', \
                        '-o', 'output.json'], stdout=sb.PIPE)
cmdCurl.wait()