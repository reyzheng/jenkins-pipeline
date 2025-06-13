import json
import getopt, sys
import os, logging
import subprocess as sb
import git
import utils

configs = dict()
WORK_DIR = ""
DST_DIR = ""

# get PATH of 'GERRIT_PROJECT'
def getREPOPath(srcDir, workDir):
    scriptPath = os.path.abspath(os.path.join(os.getenv('PF_ROOT'), 'pipeline_scripts', 'repoPath.sh'))
    scriptLog = os.path.abspath(os.path.join(workDir, 'repoPath.log'))

    repoPath = ''
    pwd = os.getcwd()
    if srcDir != '':
        os.chdir(srcDir)
    if os.path.isdir('.repo') and 'GERRIT_PROJECT' in os.environ:
        # REPO
        utils.heavyLogging('getREPOPath: REPO repository, check project {}'.format(os.getenv('GERRIT_PROJECT')))
        repoCmd = '{} {} {}'.format(scriptPath, os.getenv('GERRIT_PROJECT'), scriptLog)
        cmdEnv = dict(os.environ)
        cmdEnv['REPO_TRACE'] = '1'
        utils.heavyLogging('getREPOPath: repoCmd {}'.format(repoCmd))

        #ret = utils.popenWithStdoutTimeout(['repo', 'forall', '-c', 'sh {}'.format(repoCmd)], 600, True, cmdEnv)
        #if ret == utils.POPEN_TIMEOUT:
        #    sys.exit(utils.POPEN_TIMEOUT)
        utils.popenWithStdout(['repo', 'forall', '-c', 'sh {}'.format(repoCmd)], cmdEnv)
        if os.path.isfile(scriptLog):
            fpLog = open(scriptLog, 'r')
            line = fpLog.readline()
            if line:
                repoPath = line.strip()
                utils.heavyLogging('getREPOPath: got REPO_PATH {}'.format(repoPath))
            fpLog.close()
        else:
            utils.heavyLogging('getREPOPath: cannot get REPO path')
    else:
        utils.heavyLogging('getREPOPath: Non-REPO repository')

    os.chdir(pwd)
    return repoPath

def revisionInfo(configs, idx):
    revisionFile = os.path.join(configs['WORK_DIR'], '.pf-revision-info')
    if configs['scm_repo_mirror'][idx] == '':
        # repo manifest is only available under non-mirror mode
        pwd = os.getcwd()
        if configs['scm_dsts'][idx] != '':
            os.chdir(configs['scm_dsts'][idx])
        cmdEnv = dict(os.environ)
        cmdPieces = [configs['repo_path'], 'manifest', '-r']
        try:
            ret = utils.popenReturnStdout(cmdPieces, cmdEnv)
        except:
            ret = dict()
            ret['lines'] = []
            utils.heavyLogging('revisionInfo: repo manifest failure (incorrect repo_path maybe)')
        os.chdir(pwd)

        fpRevision = open(revisionFile, 'w')
        for line in ret['lines']:
            try:
                fpRevision.write('{}\n'.format(bytes.decode(line, 'utf-8')))
            except:
                fpRevision.write('{}\n'.format(line))
        fpRevision.close()
    else:
        fpRevision = open(revisionFile, 'w')
        fpRevision.write('')
        fpRevision.close()

    utils.heavyLogging('revisionInfo: repo')

def diffFiles(srcDir, outputFile, patchFilePrefix, workDir):
    pwd = os.getcwd()

    repoPath = getREPOPath(srcDir, workDir)
    os.chdir(os.path.join(srcDir, repoPath))
    lines = git.diffRecursiveSubmodules(patchFilePrefix)
    fpRevision = open(outputFile, 'w')
    for line in lines:
        fpRevision.write('{}\n'.format(line))
    fpRevision.close()

    os.chdir(pwd)

def checkoutParent(sourcePath, workDir, mode):
    scriptPathParent = os.path.abspath(os.path.join(os.getenv('PF_ROOT'), 'pipeline_scripts', 'repoCheckoutParent.sh'))
    scriptPathPrev = os.path.abspath(os.path.join(os.getenv('PF_ROOT'), 'pipeline_scripts', 'repoCheckoutPrev.sh'))
    scriptPathForward = os.path.abspath(os.path.join(os.getenv('PF_ROOT'), 'pipeline_scripts', 'repoCheckoutCurrent.sh'))
    cmdEnv = dict(os.environ)
    pwd = os.getcwd()
    os.chdir(sourcePath)

    if mode == 'forward' or mode == 'cherry-pick':
        cmdPieces = ['repo', 'forall', '-vc', 'git reset --hard']
        utils.popenWithStdout(cmdPieces, cmdEnv)
        repoCmd = '{} {}'.format(scriptPathForward, os.getenv('GERRIT_PROJECT'))
        cmdEnv['REPO_TRACE'] = '1'
        cmdPieces = ['repo', 'forall', '-c', 'sh {}'.format(repoCmd)]
        utils.popenWithStdout(cmdPieces, cmdEnv)
    else:
        if mode == 'parent':
            repoCmd = '{} {}'.format(scriptPathParent, os.getenv('GERRIT_PROJECT'))
        else:
            repoCmd = '{} {}'.format(scriptPathPrev, os.getenv('GERRIT_PROJECT'))
        cmdEnv['REPO_TRACE'] = '1'
        cmdPieces = ['repo', 'forall', '-c', 'sh {}'.format(repoCmd)]
        utils.popenWithStdout(cmdPieces, cmdEnv)

    os.chdir(pwd)

def loadConfigs(configFile):
    fpConfig = open(configFile)

    global configs
    configs = json.load(fpConfig)
    fpConfig.close()

def repoSyncRefspec():
    pwd = os.getcwd()

    if "GERRIT_EVENT_TYPE" not in os.environ or (os.getenv('GERRIT_EVENT_TYPE') != 'patchset-created' and os.getenv('GERRIT_EVENT_TYPE') != 'comment-added'):
        utils.heavyLogging('Not patchset-created, skip')
        sys.exit(0)
    scriptPath = os.path.abspath(os.path.join(os.getenv('PF_ROOT'), 'pipeline_scripts', 'repoSyncRefspec.sh'))
    if DST_DIR != '':
        os.chdir(DST_DIR)
    repoCmd = '{} {} {} {}'.format(scriptPath, os.getenv('GERRIT_PROJECT'), os.getenv('GERRIT_REFSPEC'), os.getenv('GERRIT_PATCHSET_REVISION'))
    utils.heavyLogging('scriptPath args {}'.format(repoCmd))
    cmdEnv = dict(os.environ)
    cmdEnv['REPO_TRACE'] = '1'
    cmdPieces = ['repo', 'forall', '-c', 'sh {}'.format(repoCmd)]
    #ret = utils.popenWithStdoutTimeout(cmdPieces, 600, True, cmdEnv)
    #if ret == utils.POPEN_TIMEOUT:
    #    sys.exit(utils.POPEN_TIMEOUT)
    utils.popenWithStdout(cmdPieces, cmdEnv)

    os.chdir(pwd)

def main(argv):
    configFile = ''
    command = ''
    global WORK_DIR
    global DST_DIR
    try:
        opts, args = getopt.getopt(argv[1:], 'd:c:w:f:u:p:v', ["dst=", "command=", "work_dir=", "config=", "user=", "password=", "version"])
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
