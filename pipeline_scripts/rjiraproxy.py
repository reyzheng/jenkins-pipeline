import sys, getopt
import os, logging
import subprocess as sb
import utils

def encryptJiraCredentials(configs):
    from Crypto.PublicKey import RSA
    from Crypto.Cipher import PKCS1_OAEP

    publicKeyPath = os.path.join(os.getenv('PF_ROOT'), 'pipeline_scripts', 'devops.pub')
    utils.heavyLogging('encryptJiraCredentials: publicKeyPath {}'.format(publicKeyPath))
    publicKey = RSA.import_key(open(publicKeyPath).read())
    cipherRSA = PKCS1_OAEP.new(publicKey)

    if 'JIRA_TOKEN' in os.environ:
        plain = os.getenv('JIRA_TOKEN')
        encryptToken = cipherRSA.encrypt(plain.encode())
        with open(os.path.join(configs['WORK_DIR'], 'encryptToken'), "wb") as binary_file:
            binary_file.write(encryptToken)
    else:
        plain = os.getenv('JIRA_USER')
        encryptUsername = cipherRSA.encrypt(plain.encode())
        plain = os.getenv('JIRA_PASSWORD')
        encryptPassword = cipherRSA.encrypt(plain.encode())
        with open(os.path.join(configs['WORK_DIR'], 'encryptUsername'), "wb") as binary_file:
            binary_file.write(encryptUsername)
        with open(os.path.join(configs['WORK_DIR'], 'encryptPassword'), "wb") as binary_file:
            binary_file.write(encryptPassword)

    return

def checkJenkinsCredentials(configs):
    if 'JENKINS_URL' not in os.environ:
        utils.heavyLogging('checkJenkinsCredentials: skip')

    jenkinsUser = 'devops_jenkins'
    if 'JENKINS_USER' in os.environ:
        jenkinsUser = os.getenv('JENKINS_USER')
    utils.heavyLogging('checkJenkinsCredentials: jenkinsUser {}'.format(jenkinsUser))
    cmdCurl = sb.Popen(['curl', '-k', '-w', '%{http_code}', '-X', 'GET', \
                            '{}api/'.format(os.getenv('JENKINS_URL')), \
                            '--user', '{}:{}'.format(jenkinsUser, os.getenv('JENKINS_TOKEN')), \
                            '-o', os.path.join(configs['WORK_DIR'], 'jenkinsTokenTest')], stdout=sb.PIPE)
    cmdCurl.wait()
    while True:
        http_code = cmdCurl.stdout.readline()
        http_code = bytes.decode(http_code, 'utf-8')
        break
    if http_code == '200':
        pass
    else:
        utils.heavyLogging('checkJenkinsCredentials: failure {}'.format(http_code))
        sys.exit(-1)

def encryptGerritEnv(configs):
    output = open(os.path.join(configs['WORK_DIR'], 'gerritENV'), 'w')
    for name, value in os.environ.items():
        if name.startswith('GERRIT_'):
            output.write('{}={}\n'.format(name, value))
    output.close

def main(argv):
    workDir = ''
    configFile = ''
    try:
        opts, args = getopt.getopt(argv[1:], 'c:w:f:vs', ['command=', 'work_dir=', 'config=', 'version', 'skip_translate'])
    except getopt.GetoptError:
        sys.exit()
    for name, value in opts:
        if name in ('-v', '--version'):
            print("0.1")
            sys.exit(0)
        elif name in ('-f', '--config'):
            configFile = value
        elif name in ('-c', '--command'):
            command = value
        elif name in ('-w', '--work_dir'):
            if os.path.isdir(value) == False:
                os.makedirs(value)
            workDir = value

    logging.basicConfig(filename=os.path.join(workDir, 'rjiraproxy.log'), format='%(asctime)s %(levelname)-8s %(message)s', level=logging.DEBUG, filemode='w')
    configs = utils.loadConfigs(configFile)
    if configs['enable'] == False:
        print('main: skip upload')
        sys.exit(0)
    configs['WORK_DIR'] = workDir
    if command == 'ENCRYPT_JIRA_CREDENTIALS':
        encryptJiraCredentials(configs)
    elif command == 'ENCRYPT_GERRIT_ENV':
        encryptGerritEnv(configs)
    elif command == 'CHECK_JENKINS_TOKEN':
        checkJenkinsCredentials(configs)

if __name__ == '__main__':
    main(sys.argv)