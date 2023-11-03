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

def knownHostsCheck():
    for scmUrl in configs["scm_urls"]:
        if scmUrl.startswith("ssh:"):
            domain = scmUrl.split("://")[1].split("/")[0] 
            port = '22'
            if ':' in domain:
                tokens = domain.split(':')
                domain = tokens[0]
                port = tokens[1]
            cmdCheck = sb.Popen(['ssh', '-p', port, '-o', 'StrictHostKeyChecking=no', domain, 'gerrit', 'version'], stdout=sb.PIPE)
            cmdCheck.wait()
            logging.debug('knownHostsCheck: {} {}'.format(domain, port))

def main(argv):
    configFile = ''
    global JENKINS_WS
    global WORK_DIR
    global configs
    try:
        opts, args = getopt.getopt(argv[1:], 'c:w:j:f:v', ["command=", "work_dir=", "jenkins_workspace=", "config=", "version"])
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
        elif name in ('-c', '--command'):
            command = value
            
    if os.path.isdir(WORK_DIR) == False and WORK_DIR != '':
        os.makedirs(WORK_DIR)
    logging.basicConfig(filename=os.path.join(WORK_DIR, 'source.log'), level=logging.DEBUG, filemode='w')
    utils.translateConfig(configFile)
    # step 1
    #     Load configurations
    #     Get coverity project name if necessary
    #     Generate .coverity.license.config
    configs = utils.loadConfigs(configFile)
    utils.checkLicense(os.path.dirname(sys.argv[0]), configs, 'source')
    if os.name == 'posix' and command == "KNOWN_HOSTS":
        knownHostsCheck()
        sys.exit(0)

if __name__ == "__main__":
    main(sys.argv)