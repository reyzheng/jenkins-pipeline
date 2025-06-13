import json, re
import getopt, sys
import os, shutil, glob
import subprocess as sb
import logging
import utils, covreport, bdreport

configs = dict()
JENKINS_WS = ""
WORK_DIR = ""
RELEASE_ENV = "OA"
PF_ROOT = ""

def loadConfigs(configFile):
    fpConfig = open(configFile)

    global configs
    configs = json.load(fpConfig)
    fpConfig.close()

def cloneReleaseTools():
    pwd = os.getcwd()
    utils.makeEmptyDirectory('urf_script')
    os.chdir('urf_script')
    cmdEnv = dict(os.environ)
    cmdEnv['GIT_SSL_NO_VERIFY'] = 'true'
    if os.name == "posix":
        branch = 'build/linux-x64'
    else:
        branch = 'build/win32-x64'
    cmdShell = sb.Popen(['git', 'clone', 'https://mirror.rtkbf.com/gerrit/sdlc/realtek_release_builds', \
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

def addReleaseInfo(dst):
    releaseInfo = dict()
    vars = ['BUILD_URL', 'JOB_NAME', 'BUILD_NUMBER']
    for var in vars:
        if var in os.environ:
            releaseInfo[var] = os.getenv(var)
    with open(os.path.join(dst, '.pf-release-info.json'), 'w') as f:
        json.dump(releaseInfo, f)

def prepareReleasePackage():
    global configs
    global WORK_DIR
    global PF_ROOT
    global JENKINS_WS

    pwd = os.getcwd()
    os.makedirs('urf_package', exist_ok=True)
    os.chdir('urf_package')
    utils.makeEmptyDirectory('release')
    utils.makeEmptyDirectory('reports')
    os.chdir('reports')
    utils.makeEmptyDirectory('user')
    os.chdir(pwd)
    os.chdir('urf_package')
    os.chdir('release')
    utils.makeEmptyDirectory('.pf_user_reports')
    os.chdir(pwd)
    # SBOM
    releaseToolParameter = "--user {}".format(configs['release_urf_user'])
    if configs['unified_release_flow_bom'] == "":
        revisionFile = ''
        files = glob.glob(os.path.join(WORK_DIR, 'revision_info', '**', '.pf-revision-info'))
        utils.heavyLogging('prepareReleasePackage: revision_info files {}'.format(files))
        try:
            count = 0
            urfBOM = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            urfBOM += "<manifest>\n"
            for f in files:
                revisionFile = f
                fpRevisionInfo = open(f)
                jsonGitInfo = json.load(fpRevisionInfo)
                fpRevisionInfo.close()
                originRemote = ''
                for revision in jsonGitInfo['sources']:
                    if count == 0:
                        urfBOM += "<remote fetch=\"{}\" name=\"origin\" />\n".format(revision['addr'])
                        urfBOM += "<default remote=\"origin\" revision=\"master\" />\n"
                        # take the 0th source as origin remote
                        originRemote = revision['addr']
                    else:
                        if originRemote != revision['addr']:
                            urfBOM += "<remote fetch=\"{}\" name=\"remote{}\" />\n".format(revision['addr'], count)
                    if originRemote == revision['addr']:
                        urfBOM += "<project name=\"{}\" path=\"{}\" revision=\"{}\" upstream=\"{}\"/>\n".format(revision['name'], revision['path'], revision['revision'], revision['upstream'])
                    else:
                        urfBOM += "<project name=\"{}\" path=\"{}\" revision=\"{}\" upstream=\"{}\" remote=\"remote{}\"/>\n".format(revision['name'], revision['path'], revision['revision'], revision['upstream'], count)
                    count = count + 1
            urfBOM += "</manifest>"
            f = open(os.path.join(WORK_DIR, 'URFSBOM'), 'w')
            f.write(urfBOM)
            f.close()
            shutil.copy(os.path.join(WORK_DIR, 'URFSBOM'), 'urf_package/reports/source_repo.xml')
        except:
            # non json format, maybe repo
            if revisionFile != '':
                utils.heavyLogging('prepareReleasePackage: revision_info repo {}'.format(revisionFile))
                shutil.copy(revisionFile, 'urf_package/reports/source_repo.xml')
    elif configs['unified_release_flow_bom'].startswith('source:'):
        tokens = configs['unified_release_flow_bom'].split(':')
        releaseToolParameter += " --code {}".format(tokens[1])
    else:
        if os.path.isabs(configs['unified_release_flow_bom']):
            utils.heavyLogging('RELEASE: SBOM abs path {}'.format(configs['unified_release_flow_bom']))
            shutil.copy(configs['unified_release_flow_bom'], 'urf_package/reports/source_repo.xml')
        else:
            if os.path.exists(os.path.join(PF_ROOT, configs['unified_release_flow_bom'])):
                utils.heavyLogging('RELEASE: SBOM {} under PFROOT'.format(configs['unified_release_flow_bom']))
                shutil.move(os.path.join(PF_ROOT, configs['unified_release_flow_bom']), 'urf_package/reports/source_repo.xml')
            elif os.path.exists(os.path.join(JENKINS_WS, configs['unified_release_flow_bom'])):
                utils.heavyLogging('RELEASE: SBOM {} under WORKSPACE'.format(configs['unified_release_flow_bom']))
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
    # User reports
    # 1. user reports from stash, artifacts
    artifacts = glob.glob('{}/report_artifacts/*'.format(WORK_DIR))
    for artifact in artifacts:
        if os.path.isfile(artifact):
            shutil.copy(artifact, 'urf_package/reports/user')
        elif os.path.isdir(artifact):
            shutil.copytree(artifact, 'urf_package/reports/user', dirs_exist_ok=True)
        else:
            utils.heavyLogging('prepareReleasePackage: {} invalid'.format(artifact))
            pass
    # 2. others
    if 'unified_release_flow_user_reports' in configs:
        for userReport in configs['unified_release_flow_user_reports']:
            if userReport.startswith('artifacts:') or userReport.startswith('stash:'):
                continue
            if os.path.isdir(userReport):
                shutil.copytree(userReport, 'urf_package/reports/user', dirs_exist_ok=True)
                shutil.copytree(userReport, 'urf_package/release/.pf_user_reports', dirs_exist_ok=True)
                utils.heavyLogging('prepareReleasePackage: copy user report dir {}'.format(userReport))
            else:
                userReportFiles = glob.glob(userReport)
                for userReportFile in userReportFiles:
                    shutil.copy(userReportFile, 'urf_package/reports/user')
                    shutil.copy(userReportFile, 'urf_package/release/.pf_user_reports')
                    utils.heavyLogging('prepareReleasePackage: copy user report file {}'.format(userReportFile))
    # add release info to urf_package/release/.pf_user_reports/.pf-release-info.json
    addReleaseInfo('urf_package/release/.pf_user_reports')
    if os.path.isfile('.pf_params'):
        shutil.copy('.pf_params', 'urf_package/release')
    # RELEASE CONFIG
    if os.path.isabs(configs['unified_release_flow_config']):
        utils.heavyLogging('prepareReleasePackage: config abs path {}'.format(configs['unified_release_flow_config']))
        shutil.copy(configs['unified_release_flow_config'], 'urf_package/config')
    else:
        if os.path.exists(os.path.join(PF_ROOT, configs['unified_release_flow_config'])):
            utils.heavyLogging('prepareReleasePackage: config {} under PFROOT'.format(configs['unified_release_flow_config']))
            shutil.move(os.path.join(PF_ROOT, configs['unified_release_flow_config']), 'urf_package/config')
        elif os.path.exists(os.path.join(JENKINS_WS, configs['unified_release_flow_config'])):
            utils.heavyLogging('prepareReleasePackage: config {} under WORKSPACE'.format(configs['unified_release_flow_config']))
            shutil.move(os.path.join(JENKINS_WS, configs['unified_release_flow_config']), 'urf_package/config')
        else:
            utils.heavyLogging('prepareReleasePackage: config {} invalid'.format(configs['unified_release_flow_config']))
            sys.exit(-1)
    if configs['release_urf_reviewer'] != '':
        modifyURFConfig("urf_package/config", "REVIEWER", configs['release_urf_reviewer'])
        utils.heavyLogging('URF config: user-defined REVIEWER {}'.format(configs['release_urf_reviewer']))
    if configs['release_urf_receiver'] != '':
        modifyURFConfig("urf_package/config", "RECEIVER", configs['release_urf_receiver'])
        utils.heavyLogging('URF config: user-defined RECEIVER {}'.format(configs['release_urf_receiver']))

    artifacts = glob.glob('{}/release_artifacts/*'.format(WORK_DIR))
    for artifact in artifacts:
        if os.path.isfile(artifact):
            shutil.copy(artifact, 'urf_package/release')
            utils.heavyLogging('prepareReleasePackage: copy file {}'.format(artifact))
        elif os.path.isdir(artifact):
            shutil.copytree(artifact, 'urf_package/release', dirs_exist_ok=True)
            utils.heavyLogging('prepareReleasePackage: copy directory {}'.format(artifact))
        else:
            utils.heavyLogging('prepareReleasePackage: {} invalid'.format(artifact))
            pass

    for filepattern in configs['unified_release_flow_files']:
        if filepattern.startswith('artifacts:') or filepattern.startswith('stash:'):
            continue
        filenames = glob.glob(filepattern)
        utils.heavyLogging('prepareReleasePackage: release files {}'.format(filenames))
        for filename in filenames:
            if os.path.isfile(filename):
                shutil.copy(filename, 'urf_package/release')
                utils.heavyLogging('prepareReleasePackage: copy file {}'.format(filename))
            elif os.path.isdir(filename):
                shutil.copytree(filename, 'urf_package/release', dirs_exist_ok=True)
                utils.heavyLogging('prepareReleasePackage: copy directory {}'.format(filename))
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
                '-d', urfPath, '--ssh-key', os.getenv('MFT_KEY'), '--network', RELEASE_ENV, '--self-update', 'off']
    utils.heavyLogging('doUnifiedReleaseFlow: release command {}'.format(URFCmd))

    cmdEnv = dict(os.environ)
    utils.popenToFile(URFCmd, cmdEnv, urfResult, urfResult)

    utils.heavyLogging('URF {} result(python3):'.format(urfPath))
    # dump URF result
    fpResults = open(urfResult, 'rb')
    lines = fpResults.readlines()
    for line in lines:
        try:
            print(bytes.decode(line, 'utf-8'), flush=True)
        except:
            pass
    fpResults.close()

def queryReleaseInfo():
    releaseInfo = dict()
    releaseInfo['RELEASE_JOB'] = ''
    releaseInfo['RELEASE_TYPE'] = ''
    re
    fpConfig = open(os.path.join('urf_package', 'config'), 'r')
    configs = fpConfig.readlines()
    fpConfig.close()
    for config in configs:
        if config.startswith('RELEASE_JOB='):
            releaseInfo['RELEASE_JOB'] = config[config.index('=') + 1:].strip()
        elif config.startswith('RELEASE_TYPE='):
            releaseInfo['RELEASE_TYPE'] = config[config.index('=') + 1:].strip()
    return releaseInfo

def parseURFResult():
    SMSURFId = 0
    with open('URFRESULT', encoding='utf-8', errors='ignore') as fpURF:
        while True:
            line = fpURF.readline()
            if not line:
                break
            if 'sms_id' in line:
                jsonMatch = re.search(r'\{.*\}', line)
                jsonStr = jsonMatch.group()
                try:
                    jsonObject = json.loads(jsonStr)
                    if jsonObject['msg'] == 'Success':
                        SMSURFId = int(jsonObject['sms_id'])
                        utils.heavyLogging('SMS URF ID: {}'.format(SMSURFId))
                        # add relase info to license server
                        releaseInfo = queryReleaseInfo()
                        releaseInfo['SMS_URF_ID'] = SMSURFId
                        os.environ["ACTIONS"] = json.dumps(releaseInfo)
                        if os.name == "posix":
                            cmdExec = 'wrapper_pipeline_linux'
                        else:
                            cmdExec = 'wrapper_pipeline_win.exe'
                        utils.popenWithStdout([os.path.join(os.getenv('PF_ROOT'), 'pipeline_scripts', cmdExec), '-s', 'CTCSOCURFPIPELINE'], dict(os.environ))
                    else:
                        utils.heavyLogging('parseURFResult: error {}'.format(jsonStr))
                except:
                    pass
    return SMSURFId

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
    doUnifiedReleaseFlow(releaseUser, sourcePath, 'urf_package', 'URFRESULT')
    urfId = parseURFResult()
    utils.saveEnv(WORK_DIR, 'PIPELINE_AS_CODE_URF_ID', urfId)
    utils.saveEnv(WORK_DIR, 'PIPELINE_AS_CODE_URF_INFO', configs['plainStageName'])
    if urfId == 0:
        utils.heavyLogging('URF: failed')
        sys.exit(-1)
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
            if os.path.isdir(value) == False:
                os.makedirs(value)
            WORK_DIR = value
            logging.basicConfig(filename=os.path.join(WORK_DIR, 'release.log'), format='%(asctime)s %(levelname)-8s %(message)s', level=logging.DEBUG, filemode='w')

    if os.path.isdir(WORK_DIR) == False:
        os.makedirs(WORK_DIR, exist_ok=True)
    # step 1
    #     Load configurations
    #     Get coverity project name if necessary
    #     Generate .coverity.license.config
    loadConfigs(configFile)
    utils.cleanEnvAndArchives(WORK_DIR)
    URF()

if __name__ == "__main__":
    main(sys.argv)
