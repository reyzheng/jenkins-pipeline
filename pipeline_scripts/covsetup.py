import json
import sys, getopt
import os, logging
import utils, coverityapi

def checkProjectExistence(configs):
    projectExists = False

    if configs["project"].strip() == '':
        projectExists = True
    else:
        fpCovKey = open(os.getenv('COV_AUTH_KEY'))
        secret = json.load(fpCovKey)
        fpCovKey.close()
        output = os.path.join(configs['WORK_DIR'], 'checkProjectExistence.json')
        #utils.heavyLogging("debug coverityapi 17 reviewed")
        coverityapi.queryCoverityProjects(secret['username'], secret['key'], configs['url'], configs['project'], output)

        fpResponse = open(output)
        response = json.load(fpResponse)
        fpResponse.close()
        if 'projects' in response:
            projectExists = True
        # Not exists: {"projects":null,"code":1302,"message":"No project found for name CTCSOC_Test."}

    return projectExists

def checkStreamExistence(configs):
    streamExists = False

    if configs['stream'].strip() == '':
        streamExists = True
    else:
        fpCovKey = open(os.getenv('COV_AUTH_KEY'))
        secret = json.load(fpCovKey)
        fpCovKey.close()
        output = os.path.join(configs['WORK_DIR'], 'checkStreamExistence.json')
        #utils.heavyLogging("debug coverityapi 39 reviewed")
        coverityapi.queryCoverityStream(secret['username'], secret['key'], configs['url'], configs['stream'], output)
        fpResponse = open(output)
        response = json.load(fpResponse)
        fpResponse.close()
        if 'streams' in response:
            streamExists = True
        # Not exists: {"streams":null,"code":1300,"message":"Stream \"CTCSOC_ttest_test\" does not exist or you do not have permission to access it."}

    return streamExists

def createProject(configs):
    payload = dict()
    payload['name'] = configs['project']
    payload['description'] = 'This is a {} project'.format(configs['project'])
    payload['roleAssignments'] = []
    roleAssignment = dict()
    roleAssignment['roleAssignmentType'] = 'user'
    roleAssignment['roleName'] = 'projectOwner'
    roleAssignment['scope'] = 'project'
    roleAssignment['username'] = configs['admin_account']
    payload['roleAssignments'].append(roleAssignment)
    roleAssignment = dict()
    roleAssignment['roleAssignmentType'] = 'group'
    roleAssignment['roleName'] = 'noAccess'
    roleAssignment['scope'] = 'project'
    roleAssignment['group'] = dict()
    roleAssignment['group']['name'] = 'Users'
    payload['roleAssignments'].append(roleAssignment)
    with open(os.path.join(configs['WORK_DIR'], 'payloadProject.json'), 'w') as outfile:
        json.dump(payload, outfile, indent=2)

    fpCovKey = open(os.getenv('COV_AUTH_KEY'))
    secret = json.load(fpCovKey)
    fpCovKey.close()
    if configs['url'].endswith("/"):
        configs['url'] = configs['url'][:-1]
    #utils.heavyLogging("debug coverityapi 76 reviewed")
    coverityapi.createCoverityProjects(secret['username'], secret['key'], configs['url'], os.path.join(configs['WORK_DIR'], 'payloadProject.json'))

def createStream(configs):
    payload = dict()
    payload['name'] = configs['stream']
    payload['triageStoreName'] = configs['triage_store']
    payload['primaryProjectName'] = configs['project']
    payload['ownerAssignmentOption'] = 'default_component_owner'
    payload['autoDeleteOnExpiry'] = True
    payload['enableDesktopAnalysis'] = True
    payload['summaryExpirationDays'] = 30
    payload['analysisVersionOverride'] = '2021.06'
    payload['pluginVersionOverride'] = '1.7.5'
    payload['componentMapName'] = 'Default'
    payload['versionMismatchMessage'] = 'wrong version'
    payload['roleAssignments'] = []
    roleAssignment = dict()
    roleAssignment['roleAssignmentType'] = 'user'
    roleAssignment['roleName'] = 'streamOwner'
    roleAssignment['scope'] = 'stream'
    roleAssignment['username'] = configs['admin_account']
    payload['roleAssignments'].append(roleAssignment)
    # add committer permission
    roleAssignment = dict()
    roleAssignment['roleAssignmentType'] = 'user'
    roleAssignment['roleName'] = 'committer'
    roleAssignment['scope'] = 'stream'
    roleAssignment['username'] = configs['user_account']
    payload['roleAssignments'].append(roleAssignment)
    # add observer permission
    roleAssignment = dict()
    roleAssignment['roleAssignmentType'] = 'user'
    roleAssignment['roleName'] = 'observer'
    roleAssignment['scope'] = 'stream'
    roleAssignment['username'] = configs['user_account']
    payload['roleAssignments'].append(roleAssignment)

    with open(os.path.join(configs['WORK_DIR'], 'payloadStream.json'), 'w') as outfile:
        json.dump(payload, outfile, indent=2)

    fpCovKey = open(os.getenv('COV_AUTH_KEY'))
    secret = json.load(fpCovKey)
    fpCovKey.close()
    if configs['url'].endswith("/"):
        configs['url'] = configs['url'][:-1]
    #utils.heavyLogging("debug coverityapi 122 reviewed")
    coverityapi.createCoverityStream(secret['username'], secret['key'], configs['url'], os.path.join(configs['WORK_DIR'], 'payloadStream.json'))

def covSetup(configs):
    if checkProjectExistence(configs) == False:
        utils.heavyLogging('covSetup: create coverity project {}'.format(configs['project']))
        createProject(configs)
    else:
        utils.heavyLogging('covSetup: coverity project {} was already existed.'.format(configs['project']))

    if checkStreamExistence(configs) == False:
        utils.heavyLogging('covSetup: create coverity stream {}'.format(configs['stream']))
        createStream(configs)
    else:
        utils.heavyLogging('covSetup: coverity stream {} was already existed.'.format(configs['stream']))

def main(argv):
    if "COV_AUTH_KEY" not in os.environ:
        sys.exit("Environment variable COV_AUTH_KEY not defined")

    workDir = ''
    configFile = ''
    skipTranslate = False
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

    logging.basicConfig(filename=os.path.join(workDir, 'covsetup.log'), format='%(asctime)s %(levelname)-8s %(message)s', level=logging.DEBUG, filemode='w')
    if skipTranslate == False:
        utils.translateConfig(configFile)
    configs = utils.loadConfigs(configFile)
    if configs['enabled'] == False:
        print('main: skip covsetup')
        sys.exit(0)
    configs['WORK_DIR'] = workDir
    covSetup(configs)

if __name__ == '__main__':
    main(sys.argv)