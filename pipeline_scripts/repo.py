import json
import getopt, sys
import os, stat
import subprocess as sb
import logging
import utils

configs = dict()
JENKINS_WS = ""
WORK_DIR = ""
DST_DIR = ""

def loadConfigs(configFile):
    fpConfig = open(configFile)

    global configs
    configs = json.load(fpConfig)
    fpConfig.close()

def repoSyncRefspec():
    pwd = os.getcwd()

    if "GERRIT_EVENT_TYPE" not in os.environ or os.getenv('GERRIT_EVENT_TYPE') != 'patchset-created':
        utils.heavyLogging('Not patchset-created, skip')
        sys.exit(0)
    # prepare sync.sh
    with open(os.path.join(WORK_DIR, 'repoSyncRefspec.sh'), 'w') as f:
        f.write('#!/bin/sh\n\n')
        f.write('if [ "$REPO_PROJECT" = "$1" ]; then\n')
        f.write('    git fetch --force --progress origin $2:$2\n')
        f.write('    git checkout -f $3\n')
        f.write('fi')
    scriptPath = os.path.abspath(os.path.join(WORK_DIR, 'repoSyncRefspec.sh'))
    os.chmod(scriptPath, 0o744)
    utils.heavyLogging('scriptPath {}'.format(scriptPath))
    if DST_DIR != '':
        os.chdir(DST_DIR)
    repoCmd = '{} {} {} {}'.format(scriptPath, os.getenv('GERRIT_PROJECT'), os.getenv('GERRIT_REFSPEC'), os.getenv('GERRIT_PATCHSET_REVISION'))
    utils.heavyLogging('scriptPath args {}'.format(repoCmd))
    cmdEnv = dict(os.environ)
    cmdEnv['REPO_TRACE'] = '1'
    cmdRepo = sb.Popen(['repo', 'forall', '-c', '{}'.format(repoCmd)], stdout=sb.PIPE, env=cmdEnv)
    cmdRepo.communicate()

    os.chdir(pwd)

def main(argv):
    configFile = ''
    command = ''
    global JENKINS_WS
    global WORK_DIR
    global DST_DIR
    try:
        opts, args = getopt.getopt(argv[1:], 'd:c:w:j:f:u:p:v', ["dst=", "command=", "work_dir=", "jenkins_workspace=", "config=", "user=", "password=", "version"])
    except getopt.GetoptError:
        sys.exit(1)
    for name, value in opts:
        if name in ('-v', '--version'):
            print("0.1")
            sys.exit(0)
        elif name in ('-u', '--user'):
            # override if --user
            covuser = value
        elif name in ('-p', '--password'):
            # override if --password
            covpass = value
        elif name in ('-f', '--config'):
            configFile = value
        elif name in ('-j', '--jenkins_workspace'):
            JENKINS_WS = value
        elif name in ('-d', '--dst'):
            DST_DIR = value
        elif name in ('-c', '--command'):
            command = value
        elif name in ('-w', '--work_dir'):
            if os.path.isdir(value) == False:
                os.makedirs(value)
            WORK_DIR = value
            logging.basicConfig(filename=os.path.join(WORK_DIR, 'source.log'), level=logging.DEBUG, filemode='w')

    # step 1
    #     Load configurations
    #     Get coverity project name if necessary
    #     Generate .coverity.license.config
    if os.path.isdir(WORK_DIR) == False:
        os.makedirs(WORK_DIR)
    #loadConfigs(configFile)
    if command == 'REPO_SYNC_REFSPEC':
        repoSyncRefspec()
    else:
        logging.debug('Invalid command {}'.format(command))

if __name__ == "__main__":
    main(sys.argv)
