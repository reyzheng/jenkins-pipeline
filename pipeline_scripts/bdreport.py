import json
import getopt, sys
import os, shutil, glob
import subprocess as sb
import zipfile
import base64
import logging, time
import utils

POLLING_INT = 30
RETRY_TIMES = 60
FAILURE_COUNT = 2

def dashboardReport(projectName, configs):
    smsHashSrc = os.getenv('BD_TOKEN').encode('UTF-8')
    smsHashBytes = base64.b64encode(smsHashSrc)
    smsHashString = smsHashBytes.decode('UTF-8')

    WORK_DIR = configs['WORK_DIR']
    pwd = os.getcwd()
    dstPath = pwd
    if 'blackduckreport_dst' in configs and configs['blackduckreport_dst'] != '':
        os.makedirs(configs['blackduckreport_dst'], exist_ok=True)
        dstPath = os.path.join(pwd, configs['blackduckreport_dst'])

    os.chdir(WORK_DIR)
    dashboardUrl = 'https://devops.realtek.com/cicd/blackduck/'
    if 'BUILD_URL' in os.environ and '-infra' in os.getenv('BUILD_URL'):
        dashboardUrl = 'https://devops-infra.rtkbf.com/cicd/blackduck/'
    utils.heavyLogging('dashboardReport: url {}'.format(dashboardUrl))

    if 'blackduckreport_projects' in configs:
        blackduckProjects = configs['blackduckreport_projects']
        blackduckVersions = configs['blackduckreport_versions']
    elif 'unified_release_flow_blackduck_projects' in configs:
        blackduckProjects = configs['unified_release_flow_blackduck_projects']
        blackduckVersions = configs['unified_release_flow_blackduck_versions']
    coverityProjects = []
    if projectName != '':
        coverityProjects = projectName.split(',')
    for i in range(len(blackduckProjects)):
        blackduckProject = blackduckProjects[i]
        blackduckVersion = blackduckVersions[i]
        utils.heavyLogging('dashboardReport: project {}, version {}'.format(blackduckProject, blackduckVersion))
        if len(coverityProjects) > i:
            # take coverityProject as report file name
            urfComponent = coverityProjects[i]
            logging.debug('Take coverityProject {} as report file name'.format(urfComponent))
        else:
            urfComponent = blackduckProject + "." + blackduckVersion
            urfComponent = urfComponent.replace(' ', '')

        projectVersionUpToDate = False
        for j in range(FAILURE_COUNT):
            input = dict()
            input['projectName'] = blackduckProject
            input['versionName'] = blackduckVersion
            with open('bom-status-input.json', 'w') as outfile:
                json.dump(input, outfile)
            utils.popenWithStdout(['curl', '-v', '-k', '-w', '%{http_code}', '-X', 'POST', \
                                    '{}bom-status'.format(dashboardUrl), \
                                    '-H', 'Authorization: Basic {}'.format(smsHashString), \
                                    '-H', 'Content-Type: application/json', \
                                    '--data', '@bom-status-input.json', '-o', 'bom-status.json'], dict(os.environ))
            with open('bom-status.json', encoding='utf8') as fpBOMStatus:
                bomStatus = json.load(fpBOMStatus)
                if bomStatus['code'] == 0 and bomStatus['data']['status'] == 'UP_TO_DATE':
                    projectVersionUpToDate = True
                    break
                elif bomStatus['code'] == 9 and 'apiToken is invalid' in bomStatus['msg']:
                    utils.heavyLogging('dashboardReport: invalid blackduck API token')
                    sys.exit(bomStatus['code'])
                else:
                    utils.heavyLogging('dashboardReport: wait bom status ready')
                    time.sleep(POLLING_INT)
        if projectVersionUpToDate == False:
            utils.heavyLogging('dashboardReport: project version status error, permission issue maybe')
            continue

        for j in range(FAILURE_COUNT):
            input = dict()
            input['projectName'] = blackduckProject
            input['versionName'] = blackduckVersion
            input['createdAt'] = ''
            with open('create-report-input.json', 'w') as outfile:
                json.dump(input, outfile)
            cmdCurl = sb.Popen(['curl', '-k', '-w', '%{http_code}', '-X', 'POST', '{}create-report/v2'.format(dashboardUrl), \
                                    '-H', 'Authorization: Basic {}'.format(smsHashString), \
                                    '-H', 'Content-Type: application/json', \
                                    '--data', '@create-report-input.json', '-o', 'create-report.json'], stdout=sb.PIPE)
            cmdCurl.wait()
            with open('create-report.json', encoding='utf8') as fpCreateReport:
                jsonCreateReport = json.load(fpCreateReport)
            if 'createdAt' in jsonCreateReport:
                utils.heavyLogging('dashboardReport: createdAt {}'.format(jsonCreateReport['createdAt']))
            else:
                utils.heavyLogging('dashboardReport: create-report failed, {}'.format(jsonCreateReport))
                sys.exit(-1)

            input['createdAt'] = jsonCreateReport['createdAt']
            with open('check-report-input.json', 'w') as outfile:
                json.dump(input, outfile)
            for rt in range(RETRY_TIMES):
                cmdCurl = sb.Popen(['curl', '-k', '-w', '%{http_code}', '-X', 'POST', '{}check-report/v2'.format(dashboardUrl), \
                                        '-H', 'Authorization: Basic {}'.format(smsHashString), \
                                        '-H', 'Content-Type: application/json', \
                                        '--data', '@check-report-input.json', '-o', 'check-report.json'], stdout=sb.PIPE)
                cmdCurl.wait()
                with open('check-report.json', encoding='utf8') as fpCheckReport:
                    jsonCheckReport = json.load(fpCheckReport)
                if 'msg' in jsonCheckReport and jsonCheckReport['msg'] == 'COMPLETED':
                    utils.heavyLogging('dashboardReport: check-report COMPLETED')
                    break
                else:
                    utils.heavyLogging('dashboardReport: check-report {} ...'.format(rt))
                    time.sleep(POLLING_INT)

            if 'msg' in jsonCheckReport and jsonCheckReport['msg'] == 'COMPLETED':
                utils.popenWithStdout(['curl', '-v', '-k', '-w', '%{http_code}', '-X', 'POST', '{}download-report/v2'.format(dashboardUrl), \
                                        '-H', 'Authorization: Basic {}'.format(smsHashString), \
                                        '-H', 'Content-Type: application/json', \
                                        '--data', '@check-report-input.json', '-o', 'reports.zip'], dict(os.environ))
                if os.path.exists('reports.zip'):
                    with zipfile.ZipFile("reports.zip","r") as zip_ref:
                        zip_ref.extractall()
                    reportDirs = glob.glob('{}-{}_*'.format(blackduckProject, blackduckVersion))
                    if len(reportDirs) > 0:
                        reportDir = reportDirs[-1]
                        os.chdir(reportDir)
                        csvfiles = glob.glob('components_*.csv')
                        for csvfile in csvfiles:
                            print("BDREPORT: move " + csvfile)
                            shutil.move(csvfile, os.path.join(dstPath, 'blackduck_{}_components.csv'.format(urfComponent)))
                        csvfiles = glob.glob('security_*.csv')
                        for csvfile in csvfiles:
                            print("BDREPORT: move " + csvfile)
                            shutil.move(csvfile, os.path.join(dstPath, 'blackduck_{}_security.csv'.format(urfComponent)))
                        #sh "rm -rf reports.zip $blackduckProject-$blackduckVersion*"
                        os.chdir('..')
                        utils.lightLogging('dashboardReport: clean {}'.format(reportDir))
                        shutil.rmtree(reportDir)
                break
            else:
                if j == 0:
                    utils.heavyLogging('dashboardReport: check-report failed, try again')
                    cmdCurl = sb.Popen(['curl', '-k', '-X', 'POST', '{}delete-report/v2'.format(dashboardUrl), \
                                            '-H', 'Authorization: Basic {}'.format(smsHashString), \
                                            '-H', 'Content-Type: application/json', '--data', '@check-report-input.json'], stdout=sb.PIPE)
                    cmdCurl.wait()
                else:
                    utils.heavyLogging('dashboardReport: check-report failed')
                    sys.exit(-1)

    os.chdir(pwd)

def bdcliReport(projectName, configs):
    WORK_DIR = configs['WORK_DIR']
    pwd = os.getcwd()
    dstPath = pwd
    if 'blackduckreport_dst' in configs and configs['blackduckreport_dst'] != '':
        os.makedirs(configs['blackduckreport_dst'], exist_ok=True)
        dstPath = os.path.join(pwd, configs['blackduckreport_dst'])

    os.chdir(WORK_DIR)
    with open('config.bd_cli.yml', 'w') as fpConfig:
        fpConfig.write('bd_url: https://blackduck.rtkbf.com\n')
        fpConfig.write('bd_token: {}\n'.format(os.getenv('BD_TOKEN')))
        fpConfig.write('insecure: true\n')
        fpConfig.write('timeout: 60\n')
        fpConfig.write('debug: false')

    utils.makeEmptyDirectory('hub-rest-api-python-builds')
    cmdEnv = dict(os.environ)
    cmdEnv['GIT_SSL_NO_VERIFY'] = 'true'
    cmdGit = sb.Popen(['git', 'clone', 'https://mirror.rtkbf.com/gerrit/sdlc/hub-rest-api-python/builds', \
                        '--depth', '1', 'hub-rest-api-python-builds'], stdout=sb.PIPE, env=cmdEnv)
    cmdGit.wait()

    if 'blackduckreport_projects' in configs:
        blackduckProjects = configs['blackduckreport_projects']
        blackduckVersions = configs['blackduckreport_versions']
    elif 'unified_release_flow_blackduck_projects' in configs:
        blackduckProjects = configs['unified_release_flow_blackduck_projects']
        blackduckVersions = configs['unified_release_flow_blackduck_versions']
    coverityProjects = []
    if projectName != '':
        coverityProjects = projectName.split(',')
    for i in range(len(blackduckProjects)):
        blackduckProject = blackduckProjects[i]
        blackduckVersion = blackduckVersions[i]
        if len(coverityProjects) > i:
            # take coverityProject as report file name
            urfComponent = coverityProjects[i]
            logging.debug('Take coverityProject {} as report file name'.format(urfComponent))
        else:
            urfComponent = blackduckProject + "." + blackduckVersion
            urfComponent = urfComponent.replace(' ', '')
		
        #hub-rest-api-python-builds/bd_cli.py report generate ${blackduckProject} ${blackduckVersion} -r VULNERABILITIES,COMPONENTS --output reports.zip
        if os.name == "posix":
            bdExec = 'bd_cli'
        else:
            bdExec = 'bd_cli.exe'
        # retry 10 minutes at most
        cmds = [os.path.join('hub-rest-api-python-builds', bdExec), 'report', 'generate', \
                            blackduckProject, blackduckVersion, '--polling', str(POLLING_INT), '--retries', str(RETRY_TIMES), \
                            '-r', 'VULNERABILITIES,COMPONENTS', '--output', 'reports.zip']
        utils.popenWithStdout(cmds, cmdEnv)

        if os.path.exists('reports.zip'):
            with zipfile.ZipFile("reports.zip","r") as zip_ref:
                zip_ref.extractall()
            reportDirs = glob.glob('{}-{}_*'.format(blackduckProject, blackduckVersion))
            if len(reportDirs) > 0:
                reportDir = reportDirs[-1]
                os.chdir(reportDir)
                csvfiles = glob.glob('components_*.csv')
                for csvfile in csvfiles:
                    print("BDREPORT: move " + csvfile)
                    shutil.move(csvfile, os.path.join(dstPath, 'blackduck_{}_components.csv'.format(urfComponent)))
                csvfiles = glob.glob('security_*.csv')
                for csvfile in csvfiles:
                    print("BDREPORT: move " + csvfile)
                    shutil.move(csvfile, os.path.join(dstPath, 'blackduck_{}_security.csv'.format(urfComponent)))
			    #sh "rm -rf reports.zip $blackduckProject-$blackduckVersion*"
                os.chdir('..')

    os.remove('config.bd_cli.yml')
    os.remove('reports.zip')
    shutil.rmtree(reportDir)
    os.chdir(pwd)

def generateReport(projectName, configs):
    utils.heavyLogging('generateReport: dashboard blackduck report')
    dashboardReport(projectName, configs)
    # bdcliReport deprecated?
    #utils.heavyLogging('generateReport: bdcli blackduck report')
    #bdcliReport(projectName, configs)

def main(argv):
    # check if jenkins credentials defined (as env. variable)
    if "BD_TOKEN" not in os.environ and "SMS_TOKEN" not in os.environ:
        sys.exit("Environmental variable BD_TOKEN/SMS_TOKEN not defined")

    configFile = ''
    coverityProjectInfo = ''
    skipTranslate = False
    workDir = ""
    configs = dict()
    try:
        opts, args = getopt.getopt(argv[1:], 'p:w:j:f:u:p:vs', ["project_info=", "work_dir=", "jenkins_workspace=", "config=", "user=", "password=", "version", "skip_translate"])
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
        elif name in ('-p', '--project_info'):
            coverityProjectInfo = value
        elif name in ('-w', '--work_dir'):
            if os.path.isdir(value) == False:
                os.makedirs(value)
            workDir = value
            logging.basicConfig(filename=os.path.join(workDir, 'bdreport.log'), level=logging.DEBUG, filemode='w')

    if skipTranslate == False:
        utils.translateConfig(configFile)
    # step 1
    #     Load configurations
    configs = utils.loadConfigs(configFile)
    configs['WORK_DIR'] = workDir
    generateReport(coverityProjectInfo, configs)

if __name__ == "__main__":
    main(sys.argv)
