import json
import sys, getopt
import os, logging
import subprocess as sb
import utils

def getGroupId(apiKey, groupName):
    cmdCurl = sb.Popen(['curl', '-s', '-k', '-X', 'GET', '--url', \
                        'https://bdba.rtkbf.com/api/groups/', \
                        '-H', 'Authorization: Bearer {}'.format(apiKey), \
                        '-H', 'Accept: application/json', '-o', 'bdbaGroups.json'], stdout=sb.PIPE)
    cmdCurl.wait()

    fpJSON = open('bdbaGroups.json')
    bdbaGroups = json.load(fpJSON)
    fpJSON.close()

    for group in bdbaGroups['groups']:
       if group['name'] == groupName:
           return group['id']

    return 0

def uploadFile(apiKey, groupId, file):
    cmdCurl = sb.Popen(['curl', '-s', '-k', '-X', 'PUT', \
                        '-T', file, '--url', 'https://bdba.rtkbf.com/api/upload/', \
                        '-H', 'Authorization: Bearer {}'.format(apiKey), \
                        '-H', 'Group: {}'.format(groupId), '-o', 'bdbaUpload-{}.json'.format(os.path.basename(file))], stdout=sb.PIPE)
    cmdCurl.wait()

    fpJSON = open('bdbaUpload-{}.json'.format(os.path.basename(file)))
    bdbaUpload = json.load(fpJSON)
    fpJSON.close()

    if bdbaUpload['meta']['code'] == 200:
        utils.heavyLogging('uploadFile: file {} uploaded to group {} success'.format(file, groupId))
    else:
        utils.heavyLogging('uploadFile: file {} uploaded to group {} failed'.format(file, groupId))

def bdbaScan(configs):
    pwd = os.getcwd()
    os.chdir(configs['WORK_DIR'])
    groupId = getGroupId(os.getenv('BDBA_TOKEN'), configs['group'])
    if groupId == 0:
        utils.heavyLogging('bdbaScan: invalid group name {}'.format(configs['group']))
        return
    else:
        for file in configs['files']:
            os.chdir(pwd)
            file = os.path.abspath(file)
            print('bdbaScan: upload {} to group {}({})'.format(file, configs['group'], groupId))
            os.chdir(configs['WORK_DIR'])
            uploadFile(os.getenv('BDBA_TOKEN'), groupId, file)

def main(argv):
    if "BDBA_TOKEN" not in os.environ:
        sys.exit("Environment variable BDBA_TOKEN not defined")

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

    logging.basicConfig(filename=os.path.join(workDir, 'bdba.log'), level=logging.DEBUG, filemode='w')
    # TODO: check utils.loadConfigs
    configs = utils.loadConfigs(configFile)
    if configs['enabled'] == False:
        print('Skip')
        sys.exit(0)
    configs['WORK_DIR'] = workDir
    bdbaScan(configs)

if __name__ == '__main__':
    main(sys.argv)