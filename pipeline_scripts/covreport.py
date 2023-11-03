import json
import getopt, sys
import os, shutil, logging
import subprocess as sb
import glob
import utils

def checkReportInPATH(path):
    try:
        cmdShell = sb.Popen([os.path.join(path, 'cov-generate-integrity-report'), '--help'], stdout=sb.PIPE)
        cmdShell.communicate()
        return 0
    except FileNotFoundError:
        return -1

def downloadURFSif(dir):
    pwd = os.getcwd()
    if os.name == "posix":
        urfSIFPath = os.path.join(dir, "URF-sif/urf.sif")
        if not os.path.isfile(urfSIFPath):
            urfSIFDir = os.path.dirname(os.path.abspath(urfSIFPath))
            if os.path.exists(urfSIFDir):
                shutil.rmtree(urfSIFDir)
            os.makedirs(urfSIFDir, exist_ok=True)
            os.chdir(urfSIFDir)
            cmdEnv = dict(os.environ)
            cmdEnv['GIT_SSL_NO_VERIFY'] = 'true'
            cmdGit = sb.Popen(['git', 'clone', 'https://mirror.rtkbf.com/gerrit/sdlc/jenkins-pipeline/singularity/urf', \
                                '--depth', '1', '.'], stdout=sb.PIPE, env=cmdEnv)
            cmdGit.wait()
            logging.debug("downloadURFSif: checkout CTCSOC urf.sif ({})".format(urfSIFPath))
        commandPrefix = "singularity exec {}".format(urfSIFPath).split()
        os.chdir(pwd)
        return commandPrefix
    else:
        logging.debug('Singularity image not available in windows')
        os.chdir(pwd)
        return []

def generateReport(configs):
    JENKINS_WS = configs['JENKINS_WS']
    WORK_DIR = configs['WORK_DIR']

    pfRoot = ''
    if 'PF_ROOT' in os.environ:
        pfRoot = os.getenv('PF_ROOT')
    pfRoot = os.path.join(JENKINS_WS, pfRoot)

    reportPrefixes = []
    reportCommand = ''
    if configs['coverity_report_toolpath'] != "":
        reportCommand = configs['coverity_report_toolpath']
    elif configs['coverity_report_toolbox'] != "":
        # user-defined singularity image
        reportPrefixes = "singularity exec {}".format(configs['coverity_report_toolbox']).split()
    else:
        reportPrefixes = downloadURFSif(JENKINS_WS)
        reportCommand = '/SDLC/cov-report/bin/'

    print('generateReport: reportPrefixes', reportPrefixes, flush = True)
    print('generateReport: reportCommand', reportCommand, flush = True)
    if configs['coverity_report_config'] == "":
        # use default report config
        fpReportConfig = open(os.path.join(pfRoot, 'rtk_coverity/coverity_report_config.yaml'))
        reportConfigLines = fpReportConfig.readlines()
        fpReportConfig.close()
        utils.heavyLogging("generateReport: take default report config ({})".format(pfRoot))
        if 'BUILD_URL' in os.environ and '-infra' in os.getenv('BUILD_URL'):
            # SD network
            for i in range(len(reportConfigLines)):
                if reportConfigLines[i].strip().startswith('url'):
                    reportConfigLines[i] = '    url: http://10.22.16.11:8080/\n'
                    utils.heavyLogging("generateReport: url: http://10.22.16.11:8080/")
    else:
        reportUnderWS = os.path.join(JENKINS_WS, configs['coverity_report_config'])
        # formal configs['coverity_report_config']: settings/URF/OOO.xml
        reportUnderPFRoot = os.path.join(pfRoot, configs['coverity_report_config'])
        if os.path.isfile(reportUnderWS):
            fpReportConfig = open(reportUnderWS)
            reportConfigLines = fpReportConfig.readlines()
            fpReportConfig.close()
            utils.heavyLogging("generateReport: take WS report config ({})".format(reportUnderWS))
        elif os.path.isfile(reportUnderPFRoot):
            fpReportConfig = open(reportUnderPFRoot)
            reportConfigLines = fpReportConfig.readlines()
            fpReportConfig.close()
            utils.heavyLogging("generateReport: take work dir report config ({})".format(reportUnderPFRoot))
        else:
            sys.exit("COVREPORT: invalid report config {}".format(configs['coverity_report_config']))

    fpReportConfig = open(os.path.join(WORK_DIR, 'coverity_report_config.yaml'), "w")
    fpReportConfig.writelines(reportConfigLines)
    fpReportConfig.close()

    covUrl = "http://172.21.15.146:8080/"
    fpYaml = open(os.path.join(WORK_DIR, 'coverity_report_config.yaml'), 'r')
    while True:
        line = fpYaml.readline().strip()
        if line.startswith('url:') == True:
            covUrl = line[line.find('http'):].strip()
            utils.heavyLogging('generateReport: parse coverity connect {}'.format(covUrl))
            break
        if not line:
            break
    fpYaml.close()

    coverityProjects = []
    if 'coverity_report_projects' in configs and len(configs['coverity_report_projects']) > 0:
        coverityProjects = configs['coverity_report_projects']
    elif 'unified_release_flow_coverity_projects' in configs and len(configs['unified_release_flow_coverity_projects']) > 0:
        coverityProjects = configs['unified_release_flow_coverity_projects']
    else:
        utils.heavyLogging('generateReport: coverity projects undefined')
        sys.exit(-1)
    #elif 'PF_COV_STREAMS' in os.environ:
    #    # retrieve coverity project from covertiy stream
    #    configs['coverity_url'] = covUrl
    #    covStreams = os.getenv('PF_COV_STREAMS').split(',')
    #    for covStream in covStreams:
    #        configs['coverity_stream'] = covStream
    #        coverityProjects.append(utils.retrieveCoverityProjectFromStream(configs, covuser, covpass))
    with open(os.path.join(WORK_DIR, 'projects'), 'w') as f:
        json.dump(coverityProjects, f)

    if 'coverity_report_dst' in configs:
        os.makedirs(configs['coverity_report_dst'], exist_ok=True)
    for coverityProject in coverityProjects:
        print('COVREPORT: generate report for {}'.format(coverityProject), flush = True)
        reports = ['integrity', 'security', 'cvss']
        for report in reports:
            covCmd = os.path.join(reportCommand, 'cov-generate-{}-report'.format(report))
            print('COVREPORT: commamd {}'.format(covCmd), flush = True)
            covCmdPieces = reportPrefixes + [covCmd]
            utils.heavyLogging('generateReport: covCmdPieces {}'.format(covCmdPieces))
            cmdEnv = dict(os.environ)
            if report == 'security':
                cmdEnv['WRITE_SEVERITIES_CSV'] = 'coverity_{}_{}.csv'.format(coverityProject, report)
            cmdEnv['WRITE_REPORT_XML'] = 'coverity_{}_{}.xml'.format(coverityProject, report)
            if os.name == "posix":
                os.unsetenv('DISPLAY')
            with open(os.path.join(WORK_DIR, 'cov-generate-{}-report.log'.format(report)), "w") as logReport:
                if report == 'cvss':
                    cmdShell = sb.Popen(covCmdPieces + [os.path.join(WORK_DIR, 'coverity_report_config.yaml'), \
                            '--project', coverityProject, '--auth-key-file', os.getenv('COV_AUTH_KEY'), '--report', '--output', \
                            'coverity_{}_{}.pdf'.format(coverityProject, report)], stdout=logReport, stderr=logReport, env=cmdEnv)
                else:
                    cmdShell = sb.Popen(covCmdPieces + [os.path.join(WORK_DIR, 'coverity_report_config.yaml'), \
                            '--project', coverityProject, '--auth-key-file', os.getenv('COV_AUTH_KEY'), '--output', \
                            'coverity_{}_{}.pdf'.format(coverityProject, report)], stdout=logReport, stderr=logReport, env=cmdEnv)
                cmdShell.wait()
            print('COVREPORT: generate {} report {}/{}'.format(report, 'coverity_{}_{}.pdf'.format(coverityProject, report), os.path.abspath(cmdEnv['WRITE_REPORT_XML'])), flush = True)
        if 'coverity_report_ignored' in configs and configs['coverity_report_ignored'] == True:
            generateOSSReport(coverityProject, covUrl, WORK_DIR)
    with open(os.path.join(WORK_DIR, 'coverity_projects.json'), 'w') as f:
        json.dump(coverityProjects, f)    
    # move to configs['coverity_report_dst']
    if 'coverity_report_dst' in configs and configs['coverity_report_dst'] != '':
        for coverityProject in coverityProjects:
            for file in glob.glob('coverity_{}_*.csv'.format(coverityProject)):
                shutil.move(file, os.path.join(configs['coverity_report_dst'], file))
            for file in glob.glob('coverity_{}_*.xml'.format(coverityProject)):
                shutil.move(file, os.path.join(configs['coverity_report_dst'], file))
            for file in glob.glob('coverity_{}_*.pdf'.format(coverityProject)):
                shutil.move(file, os.path.join(configs['coverity_report_dst'], file))
            for file in glob.glob('coverity_{}_oss.json'.format(coverityProject)):
                shutil.move(file, os.path.join(configs['coverity_report_dst'], file))

def generateOSSReport(coverityProject, url, workDir):
    WORK_DIR = workDir
    projectMatcher = dict()
    projectMatcher['class'] = 'Project'
    projectMatcher['name'] = coverityProject
    projectMatcher['type'] = 'nameMatcher'
    projectFilter = dict()
    projectFilter['columnKey'] = 'project'
    projectFilter['matchMode'] = 'oneOrMoreMatch'
    projectFilter['matchers'] = [projectMatcher]

    statusMatcher = dict()
    statusMatcher['key'] = 'Fixed'
    statusMatcher['type'] = 'keyMatcher'
    statusFilter = dict()
    statusFilter['columnKey'] = 'status'
    statusFilter['matchMode'] = 'noneMatch'
    statusFilter['matchers'] = [statusMatcher]

    actionMatcher = dict()
    actionMatcher['key'] = 'Ignore'
    actionMatcher['type'] = 'keyMatcher'
    actionFilter = dict()
    actionFilter['columnKey'] = 'action'
    actionFilter['matchMode'] = 'oneOrMoreMatch'
    actionFilter['matchers'] = [actionMatcher]

    classificationMatcher1 = dict()
    classificationMatcher1['key'] = 'False Positive'
    classificationMatcher1['type'] = 'keyMatcher'
    classificationMatcher2 = dict()
    classificationMatcher2['key'] = 'Intentional'
    classificationMatcher2['type'] = 'keyMatcher'
    classificationFilter = dict()
    classificationFilter['columnKey'] = 'classification'
    classificationFilter['matchMode'] = 'noneMatch'
    classificationFilter['matchers'] = [classificationMatcher1, classificationMatcher2]

    baseFilter = dict()
    baseFilter['filters'] = [projectFilter, statusFilter, actionFilter, classificationFilter]
    baseFilter['columns'] = ['cid', 'displayImpact', 'column_standard_OWASP Web Top Ten 2021', 'column_standard_2021 CWE Top 25']
    with open(os.path.join(WORK_DIR, 'payload.json'), 'w') as f:
        json.dump(baseFilter, f)

    fAuth = open(os.getenv('COV_AUTH_KEY'))
    authInfo = json.load(fAuth)
    fAuth.close()
    if url.endswith('/') == False:
        url = url + "/"

    ingoredCIDs = dict()
    ossSummary = dict()
    ossSummary['impact_hight_count'] = 0
    ossSummary['cwe_top25_count'] = 0
    ossSummary['owasp_top10_count'] = 0
    ossSummary['impact_hight_count'] = 0
    ossSummary['severity_veryhigh_count'] = 0
    ossSummary['severity_high_count'] = 0

    fetchRows = 0
    totalRows = 0
    while True:
        cmdShell = sb.Popen(['curl', '-L', '-X', 'POST', \
                             '{}api/v2/issues/search?includeColumnLabels=true&locale=en_us&offset={}'.format(url, fetchRows), \
                             '-H', 'Content-Type: application/json', '-H', 'Accept: application/json', \
                             '--user', '{}:{}'.format(authInfo['username'], authInfo['key']), '--data', '@{}'.format(os.path.join(WORK_DIR, 'payload.json')), \
                             '-o', os.path.join(WORK_DIR, 'ignored.json')], stdout=sb.PIPE)
        cmdShell.wait()
        fpIgnored = open(os.path.join(WORK_DIR, 'ignored.json'))
        ignoredDefects = json.load(fpIgnored)
        fpIgnored.close()
        totalRows = ignoredDefects['totalRows']
        for row in ignoredDefects['rows']:
            fetchRows = fetchRows + 1
            for keyValue in row:
                if keyValue['key'] == 'cid':
                    ingoredCIDs[keyValue['value']] = True
                elif keyValue['key'] == 'displayImpact' and keyValue['value'] == 'High':
                    ossSummary['impact_hight_count'] = ossSummary['impact_hight_count'] + 1
                elif keyValue['key'] == 'column_standard_OWASP Web Top Ten 2021' and keyValue['value'] != 'None':
                    ossSummary['owasp_top10_count'] = ossSummary['owasp_top10_count'] + 1
                elif keyValue['key'] == 'column_standard_2021 CWE Top 25' and keyValue['value'] != 'None':
                    ossSummary['cwe_top25_count'] = ossSummary['cwe_top25_count'] + 1
        print('COVREPORT: curl rows {}'.format(fetchRows), flush = True)
        if fetchRows >= totalRows:
            break

    fpSeverity = open('coverity_{}_security.csv'.format(coverityProject), 'r')
    while True:
        line = fpSeverity.readline()
        if line.startswith('CID') == False:
            tokens = line.split(',')
            if tokens[0] in ingoredCIDs:
                if tokens[3] == 'High':
                    ossSummary['severity_high_count'] = ossSummary['severity_high_count'] + 1
                elif tokens[3] == 'Very High':
                    ossSummary['severity_veryhigh_count'] = ossSummary['severity_veryhigh_count'] + 1
        if not line:
            break
    fpSeverity.close()

    with open('coverity_{}_oss.json'.format(coverityProject), 'w') as f:
        json.dump(ossSummary, f)

def main(argv):
    # check if jenkins credentials defined (as env. variable)
    if "COV_AUTH_KEY" in os.environ:
        print("COVREPORT: got environmental variable, COV_AUTH_KEY", flush = True)
    else:
        sys.exit("Environmental variable COV_AUTH_KEY not defined")

    configFile = ''
    skipTranslate = False
    jenkinsWS = ''
    workDir = ''
    configs = dict()
    try:
        opts, args = getopt.getopt(argv[1:], 'w:j:f:u:p:vs', ["work_dir=", "jenkins_workspace=", "config=", "user=", "password=", "version", "skip_translate"])
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
        elif name in ('-j', '--jenkins_workspace'):
            jenkinsWS = value
        elif name in ('-w', '--work_dir'):
            if os.path.isdir(value) == False:
                os.makedirs(value)
            workDir = value

    if skipTranslate == False:
        utils.translateConfig(configFile)
    # step 1
    #     Load configurations
    #     Get coverity project name if necessary
    #     Generate .coverity.license.config
    configs = utils.loadConfigs(configFile)
    configs['JENKINS_WS'] = jenkinsWS
    configs['WORK_DIR'] = workDir
    generateReport(configs)

if __name__ == "__main__":
    main(sys.argv)