import json, re
import sys, getopt
import os, logging
import subprocess as sb
import utils

def copyArtifacts(configs):
    if configs['enable'] == False:
        print('skip')
        return

    if configs['remote_jenkins_url'] != '':
        if "JENKINS_TOKEN" not in os.environ:
            sys.exit("Environment variable JENKINS_TOKEN not defined")
        # copy from remote
        job = configs['upstream_job'].strip('/')
        job = job.replace('/', '/job/')
        jobUrl = '{}/job/{}/{}'.format(configs['remote_jenkins_url'], job, configs['upstream_buildnumber'])
        utils.heavyLogging('copyArtifacts: jobUrl {}'.format(jobUrl))
        cmdCurl = sb.Popen(['curl', '-s', '-k', '-X', 'GET', \
                            '--url', '{}/api/json'.format(jobUrl), \
                            '-u', '{}:{}'.format(configs['remote_jenkins_user'], os.getenv('JENKINS_TOKEN')), \
                            '-o', os.path.join(configs['WORK_DIR'], 'artifacts.json')], stdout=sb.PIPE)
        cmdCurl.wait()
        fpJSON = open(os.path.join(configs['WORK_DIR'], 'artifacts.json'))
        jsonArtifacts = json.load(fpJSON)
        fpJSON.close()

        for artifact in jsonArtifacts['artifacts']:
            filename = artifact['fileName']
            relativePath = artifact['relativePath']
            utils.heavyLogging('copyArtifacts: found {}({})'.format(filename, relativePath))
            match = re.search(configs['artifacts'], filename)
            if match == None:
                print("Not match")
            else:
                os.makedirs(configs['dst'], exist_ok=True)
                cmdCurl = sb.Popen(['curl', '-s', '-k', '-X', 'GET', \
                                    '--url', '{}/artifact/{}'.format(jobUrl, relativePath), \
                                    '-u', '{}:{}'.format(configs['remote_jenkins_user'], os.getenv('JENKINS_TOKEN')), \
                                    '-o', os.path.join(configs['dst'], filename)], stdout=sb.PIPE)
                cmdCurl.wait()
                utils.heavyLogging('copyArtifacts: got {}'.format(filename))
    else:
        pass

def main(argv):
    workDir = ''
    configFile = ''
    try:
        opts, args = getopt.getopt(argv[1:], 'w:f:vs', ["work_dir=", "config=", "version", "skip_translate"])
    except getopt.GetoptError:
        sys.exit()
    for name, value in opts:
        if name in ('-v', '--version'):
            print("0.1")
            sys.exit(0)
        elif name in ('-s', '--skip_translate'):
            skipTranslate = True
        elif name in ('-f', '--config'):
            configFile = value
        elif name in ('-w', '--work_dir'):
            if os.path.isdir(value) == False:
                os.makedirs(value)
            workDir = value

    logging.basicConfig(filename=os.path.join(workDir, 'copyartifacts.log'), level=logging.DEBUG, filemode='w')
    # TODO: check utils.loadConfigs
    configs = utils.loadConfigs(configFile)
    if configs['enable'] == False:
        print('Skip')
        sys.exit(0)
    configs['WORK_DIR'] = workDir
    copyArtifacts(configs)

if __name__ == '__main__':
    main(sys.argv)