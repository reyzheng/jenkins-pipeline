import json
import sys, getopt
import os, logging
import utils

def uploadBDIO(configs):
    cmdEnv = dict(os.environ)

    curlCommand = ['curl', '-k', '-X', 'POST', '{}/api/tokens/authenticate'.format(configs['blackduck_url']), \
                    '-H', 'Authorization: token {}'.format(os.getenv('BD_TOKEN')), \
                    '-H', 'cache-control: no-cache']
    ret = utils.popenReturnStdout(curlCommand, cmdEnv)
    try:
        jsonObjBearerToken = json.loads(ret['lines'][0])
        bearerToken = jsonObjBearerToken['bearerToken']
    except:
        utils.heavyLogging('uploadBDIO: retrieve bearer token failed')
        sys.exit(-1)

    for scanfile in configs['scanfiles']:
        if scanfile.startswith('artifacts:'):
            # in morefiles
            pass
        else:
            curlCommand = ['curl', '-k', '-X', 'POST', '{}/api/scan/data'.format(configs['blackduck_url']), \
                           '-F', 'file=@{}'.format(scanfile), 
                           '-H', 'Authorization: Bearer {}'.format(bearerToken)]
            utils.popenWithStdout(curlCommand, cmdEnv)
    if 'morefiles' in configs:
        for morefile in configs['morefiles']:
            curlCommand = ['curl', '-k', '-X', 'POST', '{}/api/scan/data'.format(configs['blackduck_url']), \
                            '-F', 'file=@{}'.format(os.path.join(configs['WORK_DIR'], morefile)), \
                            '-H', 'Authorization: Bearer {}'.format(bearerToken)]
            utils.popenWithStdout(curlCommand, cmdEnv)

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
        elif name in ('-w', '--work_dir'):
            if os.path.isdir(value) == False:
                os.makedirs(value)
            workDir = value
        elif name in ('-c', '--command'):
            command = value

    logging.basicConfig(filename=os.path.join(workDir, '{}.log'.format(os.path.basename(__file__))), \
                            format='%(asctime)s %(levelname)-8s %(message)s', level=logging.DEBUG, filemode='w')
    if skipTranslate == False:
        utils.translateConfig(configFile)
    configs = utils.loadConfigs(configFile)

    if configs['enable'] == False:
        utils.heavyLogging('Stage {} cancelled manually'.format(configs['stageName']))
        sys.exit(0)
    configs['WORK_DIR'] = workDir
    uploadBDIO(configs)

if __name__ == '__main__':
    main(sys.argv)