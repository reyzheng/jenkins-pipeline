import json
import getopt, sys
from shlex import join
import os, shutil, glob
import subprocess as sb
import zipfile
import logging
import utils

def setupFuzzBox(workDir, ipAddr):
    # COPY remote fuzzbox .crt (scripts/fuzzbox.crt) to local
    with open(os.path.join(os.getenv('PF_ROOT'), 'scripts', 'fuzzbox.crt')) as f:
        fpLines = f.readlines()
    fuzzboxCaCert = ''
    for fpLine in fpLines:
        if fpLine.startswith('-----'):
            pass
        else:
            fuzzboxCaCert = fuzzboxCaCert + fpLine.strip()

    certObject = dict()
    certObject['version'] = 1.0
    certObject['fuzzboxes'] = []
    fuzzboxObject = dict()
    fuzzboxObject['name'] = ipAddr + "-pipeline"
    fuzzboxObject['hostname'] = ipAddr
    fuzzboxObject['fuzzboxCaCert'] = fuzzboxCaCert
    fuzzboxObject['clientCert'] = "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"
    certObject['fuzzboxes'].append(fuzzboxObject)
    os.makedirs(os.path.join(workDir, '.synopsys', 'defensics'), exist_ok = True)
    with open(os.path.join(workDir, '.synopsys', 'defensics', 'fuzzboxes.json'), "w") as outfile:
        json.dump(certObject, outfile, indent=2)
    os.chmod(os.path.join(workDir, '.synopsys', 'defensics', 'fuzzboxes.json'), 0o777)
    # /opt/Synopsys/FuzzBox/nginx
    #     conf.d/80211scanner.secure.conf
    #     conf.d/defensics-core-services.secure.conf
    #     stream.conf.d/80211socket.secure.conf
    #sh "sshpass -p '123456qwerty' ssh -o "StrictHostKeyChecking=no" root@${ipAddr} \"sed -e '/ssl_verify_client/ s/^#*/#/' -i /etc/nginx/conf.d/defensics-core-services.secure.conf\""
    #sh "sshpass -p '123456qwerty' ssh -o "StrictHostKeyChecking=no" root@192.168.56.110 \"systemctl restart nginx\""

def startTest(configs):
    # prepare test configuration file
    if configs["test_parameters"] == '':
        with open(os.path.join(os.getenv('PF_ROOT'), 'scripts', configs['set_file'])) as f:
            setFile = f.readlines()
        utils.heavyLogging('startTest: load set file {}'.format(configs['set_file']))

    #defensicsScreen = "screen-${env.JOB_NAME}-${env.BUILD_NUMBER}"
    #defensicsScreenLog = "screenlog-${env.JOB_NAME}-${env.BUILD_NUMBER}.txt"
    #if (configs.screen_enabled == true) {
    #    sh """
    #        # remember to restart agent if screen failed
    #        JENKINS_NODE_COOKIE=dontKillMe screen -dm -S ${defensicsScreen} -L -Logfile ${defensicsScreenLog} ${configs.screen_tty} ${configs.screen_baud}
    #        screen -ls
    #    """
    #}

    utils.heavyLogging('startTest: suite {}'.format(configs['test_suite']))
    if configs['test_suite'] == '80211ap-fp1':
        setupFuzzBox(configs['WORK_DIR'], configs['fuzzbox_ip'])
        testSuite = "suites/80211ap-fp1-1.2.0/testtool/80211ap-fp1-120.jar"
    elif configs['test_suite'] == 'ipv4':
        testSuite = "suites/ipv4-6.0.0/testtool/ipv4-600.jar"
    elif configs['test_suite'] == 'dns-client':
        testSuite = "suites/dns-client-7.1.0/testtool/dns-client-710.jar"
    elif configs['test_suite'] == 'rtsp':
        testSuite = "suites/rtsp-server-5.0.0/testtool/rtsp-server-500.jar"
    else:
        utils.heavyLogging('Unsupported test suite {}'.format(configs['test_suite']))
        sys.exit(-1)

    pwd = os.getcwd()
    os.chdir(configs['WORK_DIR'])
    # mkdir tmp under .pf-defensics
    os.makedirs('tmp', exist_ok = True)
    setFilePath = os.path.join('tmp', 'setfile')
    fpSetfile = open(setFilePath, 'w')
    fpSetfile.writelines(setFile)
    fpSetfile.close()
    utils.heavyLogging('startTest: set file {}'.format(os.path.abspath(setFilePath)))
    os.chdir(pwd)
    try:
        os.makedirs('synopsys', exist_ok = True)
        os.makedirs('tmp', exist_ok = True)
        cmdEnv = dict(os.environ)
        if configs['defensics_path'] == "CTCDOCKER":
            utils.popenWithStdout(['docker', 'run', '--rm', '--network', 'host', \
                                   '-v', '{}/.synopsys:/root/.synopsys'.format(configs['WORK_DIR']),  \
                                   '-v', '{}/synopsys:/root/synopsys'.format(configs['WORK_DIR']), \
                                   '-v', '{}/tmp:/tmp'.format(configs['WORK_DIR']), 'defensics-exec-image', \
                                   testSuite, 'set-file', '{}-{}'.format(os.getenv('JOB_NAME'), os.getenv('BUILD_NUMBER'))], cmdEnv)
        else:
            pass
            #def DEFENSICS_PATH = configs["defensics_path"]
            #sh """
            #    cd ${DEFENSICS_PATH}
            #    java -jar monitor/boot.jar --set-license-flex-addr 1123@papyrus.realtek.com
            #    java -jar monitor/boot.jar --plan-result-dir ${WORKSPACE}/.pf-defensics/synopsys/defensics/results/${env.JOB_NAME}-${env.BUILD_NUMBER} --interop-probe --suite ${testSuite} --set-file ${WORKSPACE}/.pf-defensics/tmp/setfile
            #    java -jar monitor/boot.jar --report single-html --result-dir ${WORKSPACE}/.pf-defensics/synopsys/defensics/results/${env.JOB_NAME}-${env.BUILD_NUMBER} --output-dir ${WORKSPACE}/.pf-defensics/tmp/report
            #    java -jar monitor/boot.jar --report remediation --result-dir ${WORKSPACE}/.pf-defensics/synopsys/defensics/results/${env.JOB_NAME}-${env.BUILD_NUMBER} --output-dir ${WORKSPACE}/.pf-defensics/tmp/report
            #"""
    except Exception as e:
        utils.heavyLogging('startTest: defensics failed')
        utils.heavyLogging(e)

def cleanTest(configs):
    if configs['defensics_path'] == "CTCDOCKER":
        cmdEnv = dict(os.environ)
        # remove artifacts created by docker root
        utils.popenWithStdout(['docker', 'run', '--rm', '--network', 'host', \
                                '-v', '{}:/root'.format(configs['WORK_DIR']),  \
                                '--entrypoint', '/bin/rm', 'defensics-exec-image', \
                                '-rf', '/root/synopsys'], cmdEnv)
        utils.popenWithStdout(['docker', 'run', '--rm', '--network', 'host', \
                                '-v', '{}:/root'.format(configs['WORK_DIR']),  \
                                '--entrypoint', '/bin/rm', 'defensics-exec-image', \
                                '-rf', '/root/tmp'], cmdEnv)
        utils.popenWithStdout(['docker', 'run', '--rm', '--network', 'host', \
                                '-v', '{}:/root'.format(configs['WORK_DIR']),  \
                                '--entrypoint', '/bin/rm', 'defensics-exec-image', \
                                '-rf', '/root/.synopsys'], cmdEnv)
        #sh """
        #    docker run --rm --network host -v /data/workspace/test-defensics-USDK232-80211-2_job_2/.pf-defensics:/root --entrypoint "/bin/rm" defensics-exec-image "-rf" "/root/synopsys"
        #    docker run --rm --network host -v /data/workspace/test-defensics-USDK232-80211-2_job_2/.pf-defensics:/root --entrypoint "/bin/rm" defensics-exec-image "-rf" "/root/tmp"
        #    docker run --rm --network host -v /data/workspace/test-defensics-USDK232-80211-2_job_2/.pf-defensics:/root --entrypoint "/bin/rm" defensics-exec-image "-rf" "/root/.synopsys"
        #"""

def main(argv):
    configFile = ''
    workDir = ""
    configs = dict()
    try:
        opts, args = getopt.getopt(argv[1:], 'c:w:j:f:u:p:v', ["command=", "work_dir=", "jenkins_workspace=", "config=", "user=", "password=", "version"])
    except getopt.GetoptError:
        sys.exit()
    for name, value in opts:
        if name in ('-v', '--version'):
            print("0.1")
            sys.exit(0)
        elif name in ('-c', '--command'):
            command = value
        elif name in ('-f', '--config'):
            configFile = value
        elif name in ('-w', '--work_dir'):
            workDir = value

    if os.path.isdir(workDir) == False:
        os.makedirs(workDir)
    workDir = os.path.abspath(workDir)
    logging.basicConfig(filename=os.path.join(workDir, 'defensics.log'), level=logging.DEBUG, filemode='w')
    print('log file: {}'.format(os.path.join(workDir, 'defensics.log')))

    if command == 'TRANSLATE_CONFIG':
        utils.translateConfig(configFile)
    elif command == 'START':
        configs = utils.loadConfigs(configFile)
        configs['WORK_DIR'] = workDir
        startTest(configs)
    elif command == 'CLEAN':
        configs = utils.loadConfigs(configFile)
        configs['WORK_DIR'] = workDir
        cleanTest(configs)

if __name__ == "__main__":
    main(sys.argv)