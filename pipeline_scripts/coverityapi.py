import os, utils
import urllib.parse

def triageCoverityIssues(username, key, url, triageStore, input):
    utils.popenWithStdout(['curl', '-s', '-X', 'PUT', '--url', \
                '{}/api/v2/issues/triage?locale=en_us&triageStoreName={}'.format(url, triageStore), \
                '-H', 'Content-Type: application/json', '-H', 'Accept: application/json', \
                '--user', '{}:{}'.format(username, key), '-d', '@{}'.format(input)], dict(os.environ), verbose=False)

def queryCoveritySnapshot(username, key, url, snapshotid, output):
    utils.popenWithStdout(['curl', '-s', '-u', '{}:{}'.format(username, key), \
                            '--url', '{}/api/v2/snapshots/{}'.format(url, snapshotid), \
                            '-H', 'Content-Type: application/json', \
                            '-H', 'Accept: application/json', \
                            '-o', output], dict(os.environ), verbose=False)

def queryCoverityIssues(username, key, url, offset, input, output):
    utils.popenWithStdout(['curl', '-s', '-X', 'POST', '-u', '{}:{}'.format(username, key), \
                            '--url', '{}/api/v2/issues/search?offset={}&includeColumnLabels=true&locale=en_us&queryType=bySnapshot&rowCount=200'.format(url, offset), \
                            '-H', 'Content-Type: application/json', \
                            '-H', 'Accept: application/json', \
                            '-o', output, \
                            '-d', '@{}'.format(input)], dict(os.environ), verbose=False)

def createCoverityProjects(username, key, url, input):
    utils.popenWithStdout(['curl', '-s', '-k', '-X', 'POST', '--url', \
                            '{}/api/v2/projects?locale=en_us'.format(url), \
                            '--user', '{}:{}'.format(username, key), \
                            '-H', 'Content-type: application/json', \
                            '-H', 'Accept: application/json', '-d', '@{}'.format(input)], dict(os.environ), verbose=False)

def queryCoverityProjects(username, key, url, project, output):
    utils.popenWithStdout(['curl', '-s', '-k', '-X', 'GET', '--url', \
                            '{}/api/v2/projects/{}?includeChildren=true&includeStreams=true&locale=en_us'.format(url, project), \
                            '--user', '{}:{}'.format(username, key), \
                            '-H', 'Accept: application/json', '-o', output], dict(os.environ), verbose=False)

def createCoverityStream(username, key, url, input):
    utils.popenWithStdout(['curl', '-s', '-w', '%{http_code}', '-k', '-X', 'POST', '--url', \
                            '{}/api/v2/streams?locale=en_us'.format(url), \
                            '--user', '{}:{}'.format(username, key), \
                            '-H', 'Content-type: application/json', \
                            '-H', 'Accept: application/json', '-d', '@{}'.format(input)], dict(os.environ), verbose=False)

def queryCoverityStream(username, key, url, stream, output):
    utils.popenWithStdout(['curl', '-s', '-X', 'GET', '-u', '{}:{}'.format(username, key), \
                            '--url', '{}/api/v2/streams/{}?locale=en_us'.format(url, stream), \
                            '-H', 'Content-Type: application/json', \
                            '-H', 'Accept: application/json', \
                            '-o', output], dict(os.environ), verbose=False)

def queryCoverityStreamSnapshots(username, key, url, stream, output):
    utils.popenWithStdout(['curl', '-s', '-u', '{}:{}'.format(username, key), \
                            '--url', '{}/api/v2/streams/stream/snapshots?idType=byName&name={}'.format(url, stream), \
                            '-H', 'Content-Type: application/json', \
                            '-H', 'Accept: application/json', \
                            '-o', output], dict(os.environ), verbose=False)
    
def queryCoverityStreamSnapshotsBefore(username, key, url, stream, day, output):
    utils.popenWithStdout(['curl', '-s', '-u', '{}:{}'.format(username, key), \
                            '--url', '{}/api/v2/streams/stream/snapshots?idType=byName&name={}&lastBeforeCodeVersionDate={}T00%3A00%3A00Z&locale=en_us'.format(url, urllib.parse.quote(stream), day), \
                            '-H', 'Content-Type: application/json', \
                            '-H', 'Accept: application/json', \
                            '-o', output], dict(os.environ), verbose=False)