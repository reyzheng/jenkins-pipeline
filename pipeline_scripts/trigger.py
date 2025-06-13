import json
import sys, getopt
import os, logging
import utils

def triggerRemote(configs):
    cmdEnv = dict(os.environ)

    parametersText = ''
    parameters = dict()
    if configs['parameters'].strip() != '':
        parameters = json.loads(configs['parameters'])
        for key in parameters:
            parametersText += '&{}={}'.format(key, parameters[key])

    jenkinsURL = ''
    jenkinsJob = ''
    jenkinsBuild = ''
    if 'JENKINS_URL' in os.environ:
        jenkinsURL = os.getenv('JENKINS_URL')
    if 'JOB_NAME' in os.environ:
        jenkinsJob = os.getenv('JOB_NAME')
    if 'BUILD_NUMBER' in os.environ:
        jenkinsBuild = os.getenv('BUILD_NUMBER')

    if configs['remote_url'].endswith('/') == False:
        configs['remote_url'] = configs['remote_url'] + '/'
    curlURL = '{}buildByToken/buildWithParameters?job={}&token={}&UPSTREAM_URL={}&UPSTREAM_JOB_NAME={}&UPSTREAM_BUILD_NUMBER={}{}'.format(configs['remote_url'], \
                configs['remote_job'], configs['remote_job_token'], jenkinsURL, jenkinsJob, jenkinsBuild, parametersText)
    cmd = ['curl', '-k', '-w', '%{http_code}', curlURL, '-o', 'trigger.output']
    ret = utils.popenReturnStdout(cmd, cmdEnv)
    utils.heavyLogging('triggerRemote: result {}'.format(ret))
    if 'lines' in ret:
        http_code = bytes.decode(ret['lines'][0], 'utf-8')
        if http_code != '201':
            curlURL = '{}buildByToken/build?job={}&token={}'.format(configs['remote_url'], \
                        configs['remote_job'], configs['remote_job_token'])
            cmd = ['curl', '-k', '-w', '%{http_code}', curlURL, '-o', 'trigger.output']
            ret = utils.popenReturnStdout(cmd, cmdEnv)
            utils.heavyLogging('triggerRemote: trigger again, result {}'.format(ret))

def main(argv):
    workDir = ''
    configFile = ''
    skipTranslate = False
    try:
        opts, args = getopt.getopt(argv[1:], 'c:w:f:vs', ["command=", "work_dir=", "config=", "version", "skip_translate"])
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
        elif name in ('-c', '--command'):
            COMMAND = value
        elif name in ('-w', '--work_dir'):
            if os.path.isdir(value) == False:
                os.makedirs(value)
            workDir = value
        elif name in ('-c', '--command'):
            command = value

    logging.basicConfig(filename=os.path.join(workDir, '{}.log'.format(os.path.basename(__file__))), \
                            format='%(asctime)s %(levelname)-8s %(message)s', level=logging.DEBUG, filemode='w')

    configs = utils.loadConfigs(configFile)
    if COMMAND == "NORMALIZE_CONFIG":
        paramsObj = json.loads(configs['parameters'])
        configs['parameters'] = paramsObj
        with open(configFile, 'w') as outfile:
            json.dump(configs, outfile, indent=2)
    elif COMMAND == "TRANSLATE_CONFIG":
        utils.translateConfig(configFile)
        pass
    elif COMMAND == "TRIGGER_REMOTE":
        if configs['enable'] == False:
            utils.heavyLogging('Stage {} cancelled manually'.format(configs['stageName']))
            sys.exit(0)
        triggerRemote(configs)

if __name__ == '__main__':
    main(sys.argv)