import os, zipfile, yaml, json
import utils

def downloadHSMCli(workDir):
    pwd = os.getcwd()

    os.chdir(workDir)
    if 'BUILD_URL' in os.environ and ('-infra' in os.getenv('BUILD_URL')):
        devopsServer = 'devops-infra.rtkbf.com'
    else:
        devopsServer = 'devops.realtek.com'
    if os.name == 'posix':
        cmds = ['curl', '-k', '-X', 'GET', 'https://{}/cicd/hsm/tool?filename=hsm-cli.tar.xz'.format(devopsServer), '-o', 'hsm-cli.tar.xz']
    else:
        cmds = ['curl', '-k', '-X', 'GET', 'https://{}/cicd/hsm/tool?filename=hsm-cli.zip'.format(devopsServer), '-o', 'hsm-cli.zip']
    utils.popenReturnStdout(cmds, dict(os.environ))
    if os.name == 'posix':
        cmds = ['tar', '-xJf', 'hsm-cli.tar.xz']
        utils.popenReturnStdout(cmds, dict(os.environ))
    else:
        with zipfile.ZipFile('hsm-cli.zip', 'r') as zip_ref:
            zip_ref.extractall('.')

    os.chdir(pwd)

def hsmConfig(workDir):
    # generate hsm.config.yaml under workDir
    hsmConfig = dict()
    if 'BUILD_URL' in os.environ and ('-infra' in os.getenv('BUILD_URL')):
        # infra
        hsmConfig['SERVER'] = 'https://devops-infra.rtkbf.com'
    else:
        hsmConfig['SERVER'] = 'https://devops.realtek.com'
    hsmConfig['USER_NAME'] = os.getenv('DASHBOARD_USER')
    hsmConfig['USER_TOKEN'] = os.getenv('DASHBOARD_PASSWORD')
    with open(os.path.join(workDir, 'hsm.config.yaml'), 'w') as outfile:
        yaml.dump(hsmConfig, outfile, default_flow_style=False)

def listAvailableAlgos(workDir):
    # ./hsm-cli setting ls
    hsmCliExe = hsmCliExec(workDir)
    cmds = [hsmCliExe, '-c', os.path.join(workDir, 'hsm.config.yaml'), 'setting', 'ls']
    ret = utils.popenReturnStdout(cmds, dict(os.environ))
    if ret['code'] == 0:
        line = bytes.decode(ret['lines'][0], 'utf-8')
        #utils.heavyLogging('debug: {}'.format(line))
        return json.loads(line)
    else:
        utils.heavyLogging('listAvailableAlgos: fail')
        return []

def preapareHookConfig(configs):
    if configs['hook_jenkins_job'] == '':
        utils.heavyLogging('preapareHookConfig: skip')
    else:
        hookFile = os.path.join(configs['work_dir'], 'hook-config.yaml')
        hook = dict()
        hook['name'] = 'call-jenkins'
        hook['type'] = 'JENKINS'
        hook['param']

def hsmCliExec(workDir):
    if os.name == 'posix':
        hsmCliExe = os.path.join(workDir, 'hsm-cli')
    else:
        hsmCliExe = os.path.join(workDir, 'hsm-cli', 'hsm-cli.exe')

    return hsmCliExe