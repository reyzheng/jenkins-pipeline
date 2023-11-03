import json
import getopt, sys
import os, shutil, glob
import subprocess as sb
import utils, covreport, bdreport

configs = dict()
JENKINS_WS = ""
WORK_DIR = ""
RELEASE_ENV = "RT_OA"
PF_ROOT = ""

def loadConfigs(configFile):
    fpConfig = open(configFile)

    global configs
    configs = json.load(fpConfig)
    fpConfig.close()

def cloneReleaseTools():
    pwd = os.getcwd()
    # TODO: rmtree failure on windows
    if os.path.exists('urf_script'):
        shutil.rmtree('urf_script')
    os.makedirs('urf_script', exist_ok=True)
    os.chdir('urf_script')
    cmdEnv = dict(os.environ)
    cmdEnv['GIT_SSL_NO_VERIFY'] = 'true'
    if os.name == "posix":
        branch = 'build/linux-x64'
    else:
        branch = 'build/win32-x64'
    cmdShell = sb.Popen(['git', 'clone', 'https://release.rtkbf.com/gerrit/sdlc/realtek_release_builds', \
                    '--branch={}'.format(branch), '--single-branch', '--depth=1', '.'], stdout=sb.PIPE, env=cmdEnv)
    cmdShell.wait()
    os.chdir(pwd)

def modifyURFConfig(configFile, parameter, value):
    fpConfig = open(configFile, 'r')
    configs = fpConfig.readlines()
    fpConfig.close()
    for config in configs:
        if config.startswith('{}='.format(parameter)):
            config = '{}={}'.format(parameter, value)
            break
    fpConfig = open(configFile, 'w')
    fpConfig.writelines(configs)
    fpConfig.close()


def prepareReleasePackage():
    global configs
    global WORK_DIR
    global PF_ROOT
    global JENKINS_WS

    pwd = os.getcwd()
    os.makedirs('urf_package', exist_ok=True)
    os.chdir('urf_package')
    if os.path.exists('release'):
        shutil.rmtree('release')
    if os.path.exists('reports'):
        shutil.rmtree('reports')
    os.makedirs('reports', exist_ok=True)
    os.makedirs('release', exist_ok=True)
    os.chdir(pwd)
    # SBOM
    releaseToolParameter = "--user {}".format(configs['release_urf_user'])
    if configs['unified_release_flow_bom'] == "":
        if os.path.exists('URFSBOM'):
            shutil.move('URFSBOM', 'urf_package/reports/source_repo.xml')
        else:
            # generate empty config
            pass
    elif configs['unified_release_flow_bom'].startswith('source:'):
        tokens = configs['unified_release_flow_bom'].split(':')
        releaseToolParameter += " --code {}".format(tokens[1])
    else:
        if os.path.exists(os.path.join(PF_ROOT, configs['unified_release_flow_bom'])):
            print('RELEASE: SBOM {} under PFROOT'.format(configs['unified_release_flow_bom']), flush = True)
            shutil.move(os.path.join(PF_ROOT, configs['unified_release_flow_bom']), 'urf_package/reports/source_repo.xml')
        elif os.path.exists(os.path.join(JENKINS_WS, configs['unified_release_flow_bom'])):
            print('RELEASE: SBOM {} under WORKSPACE'.format(configs['unified_release_flow_bom']), flush = True)
            shutil.move(os.path.join(JENKINS_WS, configs['unified_release_flow_bom']), 'urf_package/reports/source_repo.xml')
    # COV/BD report
    covProjects = ''
    configs['JENKINS_WS'] = JENKINS_WS
    configs['WORK_DIR'] = WORK_DIR
    if configs['unified_release_flow_coverity_report'] == True:
        utils.heavyLogging('prepareReleasePackage: generate coverity report {}'.format(configs['unified_release_flow_coverity_projects']))
        configs['coverity_report_dst'] = 'urf_package/reports'
        covreport.generateReport(configs)
        covProjects = ','.join(configs['unified_release_flow_coverity_projects'])
    if configs['unified_release_flow_balckduck_report'] == True:
        utils.heavyLogging('prepareReleasePackage: generate balckduck report {}'.format(configs['unified_release_flow_blackduck_projects']))
        configs['blackduckreport_dst'] = 'urf_package/reports'
        bdreport.generateReport(covProjects, configs)

    # RELEASE CONFIG
    if os.path.exists(os.path.join(PF_ROOT, configs['unified_release_flow_config'])):
        print('RELEASE: config {} under PFROOT'.format(configs['unified_release_flow_config']), flush = True)
        shutil.move(os.path.join(PF_ROOT, configs['unified_release_flow_config']), 'urf_package/config')
    elif os.path.exists(os.path.join(JENKINS_WS, configs['unified_release_flow_config'])):
        print('RELEASE: config {} under WORKSPACE'.format(configs['unified_release_flow_config']), flush = True)
        shutil.move(os.path.join(JENKINS_WS, configs['unified_release_flow_config']), 'urf_package/config')
    if configs['release_urf_reviewer'] != '':
        modifyURFConfig("urf_package/config", "REVIEWER", configs['release_urf_reviewer'])
        print('URF config: user-defined REVIEWER {}'.format(configs['release_urf_reviewer']))
    if configs['release_urf_receiver'] != '':
        modifyURFConfig("urf_package/config", "RECEIVER", configs['release_urf_receiver'])
        print('URF config: user-defined RECEIVER {}'.format(configs['release_urf_receiver']))

    artifacts = glob.glob('{}/release_artifacts/*'.format(WORK_DIR))
    for artifact in artifacts:
        if os.path.isfile(artifact):
            shutil.copy(artifact, 'urf_package/release')
        elif os.path.isdir(artifact):
            shutil.copytree(artifact, 'urf_package/release', dirs_exist_ok=True)
        else:
            utils.heavyLogging('prepareReleasePackage: {} invalid'.format(artifact))
            pass

    for filename in configs['unified_release_flow_files']:
        if filename.startswith('artifacts:'):
            continue
        if os.path.isfile(filename):
            shutil.copy(filename, 'urf_package/release')
        elif os.path.isdir(filename):
            shutil.copytree(filename, 'urf_package/release', dirs_exist_ok=True)
        else:
            utils.heavyLogging('prepareReleasePackage: {} invalid'.format(filename))
            pass

    return releaseToolParameter

def doUnifiedReleaseFlow(releaseUser, sourcePath, urfPath, urfResult):
    global RELEASE_ENV
    if os.path.exists('{}.zip'.format(urfPath)):
        os.remove('{}.zip'.format(urfPath))
    releaseToolParameters = ['--user', releaseUser]
    if sourcePath != '':
        releaseToolParameters += ['--code', sourcePath]
    URFCmd = [os.path.join('urf_script', 'realtek_release')] + releaseToolParameters + ['--token', os.getenv('SMS_TOKEN'), \
                '-d', urfPath, '--ssh-key', os.getenv('MFT_KEY'), '--net-env', RELEASE_ENV]
    utils.heavyLogging('doUnifiedReleaseFlow: release command {}'.format(URFCmd))
    with open(urfResult, "w") as log:
        cmdShell = sb.Popen(URFCmd, stdout=log, stderr=log)
        exitCode = cmdShell.wait()
    print('URF {} result(python3):'.format(urfPath))
    # dump URF result
    fpResults = open(urfResult, 'r')
    lines = fpResults.readlines()
    for line in lines:
        print(line)
    fpResults.close()
    return exitCode

def URF():
    global configs
    cloneReleaseTools()
    params = prepareReleasePackage()
    params = params.split()
    releaseUser = ""
    sourcePath = ""
    for i in range(len(params)):
        if params[i] == "--user":
            releaseUser = params[i + 1]
        elif params[i] == "--code":
            sourcePath = params[i + 1]
    urfCode = doUnifiedReleaseFlow(releaseUser, sourcePath, 'urf_package', 'URFRESULT')
    #if urfCode == 0 and configs['urftojira_enable'] == True:
    #    prepareReleaseToJIRAPackage()
    #    doUnifiedReleaseFlow(releaseUser, '', 'urf_tojira', 'URFRESULT_JIRA')

def main(argv):
    # check if jenkins credentials defined (as env. variable)
    if 'SMS_TOKEN' not in os.environ or 'MFT_KEY' not in os.environ:
        sys.exit("Environmental variable SMS_TOKEN/MFT_KEY not defined")

    configFile = ''
    global JENKINS_WS
    global PF_ROOT
    global WORK_DIR
    global RELEASE_ENV
    try:
        opts, args = getopt.getopt(argv[1:], 'r:e:w:j:f:v', ["pf_root=", "env=", "work_dir=", "jenkins_workspace=", "config=", "version"])
    except getopt.GetoptError:
        sys.exit()
    for name, value in opts:
        if name in ('-v', '--version'):
            print("0.1")
            sys.exit(0)
        elif name in ('-f', '--config'):
            configFile = value
        elif name in ('-r', '--pf_root'):
            PF_ROOT = value
        elif name in ('-j', '--jenkins_workspace'):
            JENKINS_WS = value
        elif name in ('-e', '--env'):
            RELEASE_ENV = value
        elif name in ('-w', '--work_dir'):
            WORK_DIR = value

    if os.path.isdir(WORK_DIR) == False:
        os.makedirs(WORK_DIR, exist_ok=True)
    # step 1
    #     Load configurations
    #     Get coverity project name if necessary
    #     Generate .coverity.license.config
    loadConfigs(configFile)
    URF()

if __name__ == "__main__":
    main(sys.argv)