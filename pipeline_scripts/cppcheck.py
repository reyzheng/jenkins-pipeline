import json
import getopt, sys
from math import log
import os
import subprocess as sb
import logging
import utils

jiraIssues = dict()
configs = dict()
JENKINS_WS = ""
WORK_DIR = ""

def loadConfigs(configFile):
    fpConfig = open(configFile)

    global configs
    configs = json.load(fpConfig)
    fpConfig.close()

def checkoutPrevVersion(path):
    pwd = os.getcwd()
    os.chdir(path)
    if 'GERRIT_BRANCH' not in os.environ:
        logging.debug('cppcheck: GERRIT_BRANCH not defined')
        sys.exit(-1)
    logging.debug('checkoutPrevVersion: checkout source to {}', os.getenv('GERRIT_BRANCH'))
    cmdCheckoutParent = sb.Popen(['git', 'checkout', os.getenv('GERRIT_BRANCH')], stdout=sb.PIPE)
    cmdCheckoutParent.wait()
    os.chdir(pwd)

def cppcheck():
    global WORK_DIR
    pwd = os.getcwd()
    if configs['cppcheck_scan_path'] == '':
        configs['cppcheck_scan_path'] = os.path.abspath(pwd)
    else:
        configs['cppcheck_scan_path'] = os.path.abspath(configs['cppcheck_scan_path'])
    logging.debug('cppcheck: scan path {}'.format(configs['cppcheck_scan_path']))
    os.chdir(WORK_DIR)

    cppcheckProg = os.path.join(configs['cppcheck_install_path'], 'cppcheck')
    logging.debug('cppcheck: scan output {}'.format('pf-cppcheck.xml'))
    with open('pf-cppcheck.xml', "w") as logReport:
        cmdCheck = sb.Popen([cppcheckProg, configs['cppcheck_scan_path'], '--xml'], stdout=logReport, stderr=logReport)
        cmdCheck.wait()
        logReport.flush()
    if configs['gerrit_diff'] == True:
        checkoutPrevVersion(configs['cppcheck_scan_path'])
        logging.debug('cppcheck: scan output {}'.format('pf-cppcheck-parent.xml'))
        with open('pf-cppcheck-parent.xml', "w") as logReport:
            cmdCheck = sb.Popen([cppcheckProg, configs['cppcheck_scan_path'], '--xml'], stdout=logReport, stderr=logReport)
            cmdCheck.wait()
            logReport.flush()

    os.chdir(pwd)

def main(argv):
    # check if jenkins credentials defined (as env. variable)
    #if "BD_TOKEN" not in os.environ or "JIRA_TOKEN" not in os.environ:
    #    sys.exit("Environmental variable BD_TOKEN/JIRA_TOKEN not defined")

    configFile = ''
    global JENKINS_WS
    global WORK_DIR
    try:
        opts, args = getopt.getopt(argv[1:], 'w:j:f:v', ["work_dir=", "jenkins_workspace=", "config=", "version"])
    except getopt.GetoptError:
        sys.exit()
    for name, value in opts:
        if name in ('-v', '--version'):
            print("0.1")
            sys.exit(0)
        elif name in ('-f', '--config'):
            configFile = value
        elif name in ('-j', '--jenkins_workspace'):
            JENKINS_WS = value
        elif name in ('-w', '--work_dir'):
            WORK_DIR = value
            
    if os.path.isdir(WORK_DIR) == False and WORK_DIR != '':
        os.makedirs(WORK_DIR)
    logging.basicConfig(filename=os.path.join(WORK_DIR, 'cppcheck.log'), level=logging.DEBUG, filemode='w')
    # step 1
    #     Load configurations
    #     Get coverity project name if necessary
    #     Generate .coverity.license.config
    loadConfigs(configFile)
    utils.checkLicense(os.path.dirname(sys.argv[0]), configs, 'cppcheck')
    cppcheck()

if __name__ == "__main__":
    main(sys.argv)