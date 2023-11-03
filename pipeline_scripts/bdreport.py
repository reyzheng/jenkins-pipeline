import json
import getopt, sys
import os, shutil, glob
import subprocess as sb
import zipfile
import base64
import logging, time
import utils

POLLING_INT = 10
RETRY_TIMES = 60

def dashboardReport(projectName, configs):
    smsHashSrc = configs['release_urf_user'] + ':' + os.getenv('SMS_TOKEN')
    smsHashSrc = smsHashSrc.encode('UTF-8')
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

        input = dict()
        input['projectName'] = blackduckProject
        input['versionName'] = blackduckVersion
        input['createdAt'] = ''
        with open('create-report-input.json', 'w') as outfile:
            json.dump(input, outfile)
        cmdCurl = sb.Popen(['curl', '-k', '-w', '%{http_code}', '-X', 'POST', '{}create-report'.format(dashboardUrl), \
                                '-H', 'Authorization: Basic {}'.format(smsHashString), \
                                '-H', 'Content-Type: application/json', \
                                '--data', '@create-report-input.json', '-o', 'create-report.json'], stdout=sb.PIPE)
        cmdCurl.wait()
        fpCreateReport = open('create-report.json')
        jsonCreateReport = json.load(fpCreateReport)
        fpCreateReport.close()
        if 'createdAt' in jsonCreateReport:
            utils.heavyLogging('dashboardReport: createdAt {}'.format(jsonCreateReport['createdAt']))
        else:
            utils.heavyLogging('dashboardReport: create-report failed')
            sys.exit(-1)

        input['createdAt'] = jsonCreateReport['createdAt']
        with open('check-report-input.json', 'w') as outfile:
            json.dump(input, outfile)
        for rt in range(RETRY_TIMES):
            cmdCurl = sb.Popen(['curl', '-k', '-w', '%{http_code}', '-X', 'POST', '{}check-report'.format(dashboardUrl), \
                                    '-H', 'Authorization: Basic {}'.format(smsHashString), \
                                    '-H', 'Content-Type: application/json', \
                                    '--data', '@check-report-input.json', '-o', 'check-report.json'], stdout=sb.PIPE)
            cmdCurl.wait()
            fpCheckReport = open('check-report.json')
            jsonCheckReport = json.load(fpCheckReport)
            fpCheckReport.close()
            if 'msg' in jsonCheckReport and jsonCheckReport['msg'] == 'COMPLETED':
                utils.heavyLogging('dashboardReport: check-report COMPLETED')
                break
            else:
                utils.heavyLogging('dashboardReport: check-report {} ...'.format(rt))
                time.sleep(POLLING_INT)

        if 'msg' in jsonCheckReport and jsonCheckReport['msg'] == 'COMPLETED':
            cmdCurl = sb.Popen(['curl', '-k', '-w', '%{http_code}', '-X', 'POST', '{}download-report'.format(dashboardUrl), \
                                    '-H', 'Authorization: Basic {}'.format(smsHashString), \
                                    '-H', 'Content-Type: application/json', \
                                    '--data', '@check-report-input.json', '-o', 'reports.zip'], stdout=sb.PIPE)
            cmdCurl.wait()
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
        else:
            utils.heavyLogging('dashboardReport: check-report failed')
            sys.exit(-1)

    shutil.rmtree(reportDir)
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

    if os.path.exists('hub-rest-api-python-builds'):
        shutil.rmtree('hub-rest-api-python-builds')
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
    if 'SMS_TOKEN' in os.environ:
        utils.heavyLogging('generateReport: dashboard blackduck report')
        dashboardReport(projectName, configs)
    else:
        utils.heavyLogging('generateReport: bdcli blackduck report')
        bdcliReport(projectName, configs)

def main(argv):
    # check if jenkins credentials defined (as env. variable)
    if "BD_TOKEN" in os.environ:
        print("BDREPORT: got environmental variable, BD_TOKEN")
    else:
        sys.exit("Environmental variable BD_TOKEN not defined")

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
            logging.basicConfig(filename=os.path.join(workDir, 'bdreport.log'), level=logging.DEBUG)

    if skipTranslate == False:
        utils.translateConfig(configFile)
    # step 1
    #     Load configurations
    #     Get coverity project name if necessary
    #     Generate .coverity.license.config
    configs = utils.loadConfigs(configFile)
    configs['WORK_DIR'] = workDir
    generateReport(coverityProjectInfo, configs)

if __name__ == "__main__":
    main(sys.argv)
