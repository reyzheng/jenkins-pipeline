import json, glob
import getopt, sys
import os, shutil, time
import subprocess as sb
import logging
import utils, jira, urfftp

#configs = dict()
JENKINS_WS = ""
WORK_DIR = ""

def queryURFStatus(smsAccount, SMSURFId):
    expectedStatus = [20, 25, 207, 210, 301]
    RELEASE_STATUS = "Unknown"
    # test 600 seconds
    for i in range(10):
        ret = utils.queryURFReleaseStatus(smsAccount, os.getenv('SMS_TOKEN'), SMSURFId)
        if ret in expectedStatus:
            if ret == 20:
                RELEASE_STATUS = "Finish"
            elif ret == 25:
                RELEASE_STATUS = "Finish IT release"
            elif ret == 207:
                RELEASE_STATUS = "Parse SBOM Fail"
            elif ret == 210:
                RELEASE_STATUS = "Check Checkers Fail"
            elif ret == 301:
                RELEASE_STATUS = "IT Release Fail"
            break
        else:
            logging.debug('Wait 60 seconds')
            time.sleep(60)

    return RELEASE_STATUS

def exportParams():
    fpParams = open('env', 'r')
    while True:
        line = fpParams.readline()
        if not line:
            break
        splitpos = line.index('=')
        if splitpos > 0:
            param = line[:splitpos].strip()
            value = line[splitpos + 1:].strip()
            os.environ[param] = value
            utils.heavyLogging('exportParams: {}={}'.format(param, value))
    fpParams.close()

def retrieveURFArtifacts(jenkinsReportUrl, urfProjects, configs):
    retrievedFiles = []
    artifacts = configs['artifacts']
    artifacts.append("ENVPARAMS")
    #if len(artifacts) == 0:
    #    utils.heavyLogging('retrieveURFArtifacts: skip retrieve')
    #    return

    utils.heavyLogging('retrieveURFArtifacts: try to retrieve {}, {}'.format(artifacts, urfProjects))
    releaseJenkinsUser = configs['release_jenkins_user']
    releaseJenkinsToken = configs['release_jenkins_token']
    if 'RELEASE_JENKINS_TOKEN' in os.environ:
        releaseJenkinsToken = os.getenv('RELEASE_JENKINS_TOKEN')
    for artifact in artifacts:
        for urfProject in urfProjects:
            if artifact == 'ENVPARAMS':
                utils.heavyLogging('retrieveURFArtifacts: Retrieve ENVPARAMS')
                if 'MFT_KEY' not in os.environ:
                    utils.heavyLogging('retrieveURFArtifacts: skip retrieve ENVPARAMS')
                    continue
                sftpConfig = dict()
                sftpConfig['dst'] = ''
                sftpConfig['files'] = ['__urf__/package_list.json']
                urfftp.urfFtp(sftpConfig)
                if os.path.isfile('package_list.json'):
                    fpPackageList = open('package_list.json')
                    packageList = json.load(fpPackageList)
                    fpPackageList.close()
                    sftpConfig = dict()
                    sftpConfig['dst'] = ''
                    sftpConfig['files'] = []
                    sftpConfig['names'] = []
                    for files in packageList['files']:
                        if files['name'] == '.pf_params' and files['type'] == 'file':
                            sftpConfig['files'].append(files['path'])
                            sftpConfig['names'].append(files['name'])
                            utils.heavyLogging('retrieveURFArtifacts: Retrieve artifacts {}'.format(sftpConfig['files']))
                            urfftp.urfFtp(sftpConfig)
                            if os.path.isfile('.pf_params'):
                                shutil.copy('.pf_params', 'env')
                                exportParams()
                            break
            elif artifact == 'RSCAT':
                utils.heavyLogging('retrieveURFArtifacts: Retrieve RSCAT')
                # https://user:token@release.rtkbf.com/jenkins/job/CTC_PSP_DEMO/job/Test/122/Release_20Report/rscat_CTCSOC_test.html'
                artifactFile = 'rscat_{}.html'.format(urfProject)
                utils.heavyLogging('retrieveURFArtifacts: Retrieve artifacts: {}{}'.format(jenkinsReportUrl, artifactFile))
                cmdCurl = sb.Popen(['curl', '-s', '-k', '-w', '%{http_code}', '-X', 'GET', \
                                        '--user', '{}:{}'.format(releaseJenkinsUser, releaseJenkinsToken), \
                                        '{}{}'.format(jenkinsReportUrl, artifactFile), '-o', artifactFile], stdout=sb.PIPE)
                cmdCurl.wait()
                while True:
                    http_code = cmdCurl.stdout.readline()
                    http_code = bytes.decode(http_code, 'utf-8')
                    break
                if http_code == '200':
                    retrievedFiles.append(artifactFile)
                else:
                    utils.heavyLogging('retrieveURFArtifacts: Retrieve artifacts {} failed'.format(artifactFile))
            elif artifact == 'COVREPORT':
                utils.heavyLogging('retrieveURFArtifacts: Retrieve COVREPORT')
                # https://user:token@release.rtkbf.com/jenkins/job/CTC_PSP_DEMO/job/Test/122/Release_20Report/user/coverity_CTCSOC_test_cvss.xml'
                artifactFiles = ['coverity_{}_cvss.pdf'.format(urfProject),
                                 'coverity_{}_integrity.pdf'.format(urfProject),
                                 'coverity_{}_security.pdf'.format(urfProject),]
                for artifactFile in artifactFiles:
                    utils.heavyLogging('retrieveURFArtifacts: Retrieve artifacts {}user/{}'.format(jenkinsReportUrl, artifactFile))
                    cmdCurl = sb.Popen(['curl', '-s', '-k', '-w', '%{http_code}', '-X', 'GET', \
                                            '--user', '{}:{}'.format(releaseJenkinsUser, releaseJenkinsToken), \
                                            '{}user/{}'.format(jenkinsReportUrl, artifactFile), '-o', artifactFile], stdout=sb.PIPE)
                    cmdCurl.wait()
                    while True:
                        http_code = cmdCurl.stdout.readline()
                        http_code = bytes.decode(http_code, 'utf-8')
                        break
                    if http_code == '200':
                        retrievedFiles.append(artifactFile)
                    else:
                        utils.heavyLogging('retrieveURFArtifacts: Retrieve artifacts {} failed'.format(artifactFile))
            elif artifact == 'BDREPORT':
                utils.heavyLogging('retrieveURFArtifacts: Retrieve BDREPORT')
                # https://user:token@release.rtkbf.com/jenkins/job/CTC_PSP_DEMO/job/Test/122/Release_20Report/user/blackduck_CTCSOC_test_components.csv'
                artifactFiles = ['blackduck_{}_components.csv'.format(urfProject),
                                 'blackduck_{}_security.csv'.format(urfProject)]
                for artifactFile in artifactFiles:
                    utils.heavyLogging('retrieveURFArtifacts: Retrieve artifacts: {}user/{}'.format(jenkinsReportUrl, artifactFile))
                    cmdCurl = sb.Popen(['curl', '-s', '-k', '-w', '%{http_code}', '-X', 'GET', \
                                            '--user', '{}:{}'.format(releaseJenkinsUser, releaseJenkinsToken), \
                                            '{}user/{}'.format(jenkinsReportUrl, artifactFile), '-o', artifactFile], stdout=sb.PIPE)
                    cmdCurl.wait()
                    while True:
                        http_code = cmdCurl.stdout.readline()
                        http_code = bytes.decode(http_code, 'utf-8')
                        break
                    if http_code == '200':
                        retrievedFiles.append(artifactFile)
                    else:
                        utils.heavyLogging('retrieveURFArtifacts: Retrieve artifacts {} failed'.format(artifactFile))
            elif artifact == 'USERREPORT':
                utils.heavyLogging('retrieveURFArtifacts: Retrieve USERREPORT')
                if 'MFT_KEY' not in os.environ:
                    utils.heavyLogging('retrieveURFArtifacts: skip retrieve USERREPORT')
                    continue
                sftpConfig = dict()
                sftpConfig['dst'] = ''
                sftpConfig['files'] = ['__urf__/package_list.json']
                urfftp.urfFtp(sftpConfig)
                if os.path.isfile('package_list.json'):
                    fpPackageList = open('package_list.json')
                    packageList = json.load(fpPackageList)
                    fpPackageList.close()
                    sftpConfig = dict()
                    sftpConfig['dst'] = ''
                    sftpConfig['files'] = []
                    sftpConfig['names'] = []
                    for files in packageList['files']:
                        if files['path'].startswith('.pf_user_reports') and files['type'] == 'file':
                            sftpConfig['files'].append(files['path'])
                            sftpConfig['names'].append(files['name'])
                    utils.heavyLogging('retrieveURFArtifacts: Retrieve artifacts {}'.format(sftpConfig['files']))
                    urfftp.urfFtp(sftpConfig)
                    for file in sftpConfig['names']:
                        if os.path.isfile(file):
                            retrievedFiles.append(file)
            elif artifact.startswith('file:'):
                tokens = artifact.split(':')
                utils.heavyLogging('retrieveURFArtifacts: check file pattern {}'.format(tokens[1]))
                if '**' in tokens[1]:
                    import glob2
                    files = glob2.glob(tokens[1])
                else:
                    files = glob.glob(tokens[1])
                for file in files:
                    utils.heavyLogging('retrieveURFArtifacts: check file {}'.format(file))
                    if os.path.isfile(file):
                        # will got abspath here. refer to absArtifactsPath()
                        if file.startswith(os.getenv('WORKSPACE')):
                            file = os.path.relpath(file, os.getenv('WORKSPACE'))
                            retrievedFiles.append('WORKSPACE:{}'.format(file))
                        else:
                            retrievedFiles.append(file)
                        utils.heavyLogging('retrieveURFArtifacts: file {}'.format(file))
                    else:
                        utils.heavyLogging('retrieveURFArtifacts: invalid file {}'.format(file))
            else:
                utils.heavyLogging('retrieveURFArtifacts: invalid artifacts {}'.format(artifact))

    utils.heavyLogging('retrieveURFArtifacts: retrieved {}'.format(retrievedFiles))
    fpArtifacts = open(".artifacts", "w")
    fpArtifacts.write(','.join(retrievedFiles))
    fpArtifacts.close()
    return retrievedFiles

def attachURFArtifacts(artifactFiles, issueKey, configs):
    # TODO: under WORKDIR
    if len(artifactFiles) == 0:
        utils.heavyLogging('attachURFArtifacts: skip attach')
        return
    for artifactFile in artifactFiles:
        if artifactFile.startswith('WORKSPACE:'):
            artifactFile = artifactFile.split(':')[1]
            artifactFile = os.path.join(os.getenv('WORKSPACE'), artifactFile)
        jira.jiraUploadAttachment(configs['jira_site'], issueKey, artifactFile)

def absArtifactsPath(configs):
    for i in range(len(configs['artifacts'])):
        if configs['artifacts'][i].startswith('file:'):
            tokens = configs['artifacts'][i].split(':')
            configs['artifacts'][i] = 'file:{}'.format(os.path.abspath(tokens[1]))
    return configs

def waitingIssueClosed(issueKey, configs):
    global WORK_DIR
    global JENKINS_WS
    issueStatus = ''

    while issueStatus != configs['waiting_issue_status']:
        time.sleep(60)

        jqlCommand = "project={} and key='{}'".format(configs['jira_project'], issueKey)
        jira.jiraJQLSearch(configs['jira_site'], jqlCommand, 0, 100, os.path.join(WORK_DIR, 'issues.json'))

        fpIssues = open(os.path.join(WORK_DIR, 'issues.json'))
        issues = json.load(fpIssues)
        fpIssues.close()
        if 'total' in issues and issues['total'] > 0:
            issueStatus = issues['issues'][0]['fields']['status']['name']
            utils.heavyLogging('waitingIssueClosed: got issue status {}'.format(issueStatus))
        else:
            utils.heavyLogging('waitingIssueClosed: cannot found {}'.format(issueKey))
            sys.exit(1)

def URFResult2JIRA(configs):
    global WORK_DIR
    global JENKINS_WS

    issueKey = ''
    configs = absArtifactsPath(configs)
    urfProjects = []
    pwd = os.getcwd()
    os.chdir(WORK_DIR)
    SMSURFId = 0
    if configs['report_name'] != '':
        urfProjects = configs['report_name'].split(',')
    # https://wiki.realtek.com/display/SDLC/Trigger+BUs%27+Jenkins+Job
    if 'SMSURF_ID' in os.environ:
        # URF/JIRA at separated network segment
        SMSURFId = int(os.getenv('SMSURF_ID'))
        logging.debug('Got SMSURF_ID {}'.format(os.getenv('SMSURF_ID')))
    elif 'PIPELINE_AS_CODE_URF_ID' in os.environ:
        # URF/JIRA at same network segment
        SMSURFId = int(os.getenv('PIPELINE_AS_CODE_URF_ID'))
        logging.debug('Got SMSURF_ID {}'.format(os.getenv('PIPELINE_AS_CODE_URF_ID')))
        uffInfoFolder = os.path.join(JENKINS_WS, '.pf-{}'.format(os.getenv('PIPELINE_AS_CODE_URF_INFO')))
        if len(urfProjects) == 0:
            # got project name from coverity_projects.json
            fpProjectInfo = open(os.path.join(uffInfoFolder, 'coverity_projects.json'))
            urfProjects = json.load(fpProjectInfo)
            fpProjectInfo.close()
            logging.debug('Get URF projects from PIPELINE_AS_CODE_URF_PROJECTS: ')
            logging.debug(urfProjects)
    else:
        print("Invalid SMSURFId")
        sys.exit(1)
    RELEASE_STATUS = queryURFStatus(configs['sms_account'], SMSURFId)
    #https://ctcsoc_jenkins:Real12345@release.rtkbf.com/jenkins/job/CTC_PSP_DEMO/job/Test/122/Release_20Report/rscat_siren.html
    if 'RELEASE_NAME' in os.environ:
        releaseName = os.getenv('RELEASE_NAME')
        tokens = releaseName.split('-')
        RELEASE_JOB = tokens[0]
        RELEASE_TYPE = tokens[1]
    elif 'PIPELINE_AS_CODE_URF_ID' in os.environ:
        RELEASE_JOB = utils.getURFConfig(os.path.join(JENKINS_WS, "urf_package/config"), "RELEASE_JOB").strip()
        RELEASE_TYPE = utils.getURFConfig(os.path.join(JENKINS_WS, "urf_package/config"), "RELEASE_TYPE").strip()
    configs['jira_project'] = jira.jiraGetProjectKey(configs['jira_site'], configs['jira_project'], '')

    urfRecord = utils.queryURFReleaseRecord(SMSURFId)
    # retrieve report
    if urfRecord['code'] == 0:
        jenkinsReportUrl = urfRecord['data']['jenkinsReport']
        utils.heavyLogging('URFResult2JIRA: got URF Report URL {} success'.format(jenkinsReportUrl))
        artifactFiles = retrieveURFArtifacts(jenkinsReportUrl, urfProjects, configs)
    else:
        utils.heavyLogging('URFResult2JIRA: got URF Report URL ({}) failed, cannot retrieve report to JIRA'.format(SMSURFId))

    if configs['post_jira'] == False:
        utils.heavyLogging('URFResult2JIRA: skip post JIRA issue')
        return issueKey
    # post jira issue
    jira.getKeyFields(configs['jira_site'], configs['defects_extra_fields'])
    jiraIssue = dict()
    jiraIssueFields = dict()
    # create issue with assignee is not preferred
    # may cause issue creation failure
    #if 'key' in jiraUser:
    #    jiraIssueFields['assignee'] = dict()
    #    jiraIssueFields['assignee']['name'] = configs['issue_assignee']
    jiraIssueFields['project'] = dict()
    jiraIssueFields['project']['key'] = configs['jira_project']
    jiraIssueFields['summary'] = "URF {} {} ({}): {}".format(RELEASE_JOB, RELEASE_TYPE, SMSURFId, RELEASE_STATUS)
    if urfRecord['code'] == 0:
        jiraIssueFields['description'] = 'sftp://sdmft.rtkbf.com/release.out/{}'.format(urfRecord['data']['releaseName'])
    else:
        jiraIssueFields['description'] = ''
    jiraIssueFields['issuetype'] = dict()
    jiraIssueFields['issuetype']['name'] = "Task"
    jiraIssue['fields'] = jiraIssueFields
    jiraIssue['fields']['labels'] = ['RELEASE_JOB:{}'.format(RELEASE_JOB)]
    if os.path.isfile('extraFieldsMap.json'):
        with open('extraFieldsMap.json') as f:
            fieldsMap = json.load(f)
        for fieldsMapKey in fieldsMap:
            fieldId = fieldsMap[fieldsMapKey]['id']
            fieldValue = fieldsMap[fieldsMapKey]['value']
            jiraIssue['fields'][fieldId] = fieldValue
    with open("urfIssue.json", "w") as outfile:
        json.dump(jiraIssue, outfile)
    jira.jiraCreateIssue(configs['jira_site'], 'urfIssue.json', 'urfIssueResult.json')
    fpIssueResult = open('urfIssueResult.json')
    jsonIssueResult = json.load(fpIssueResult)
    fpIssueResult.close()
    if 'errors' in jsonIssueResult:
        # create issue failed
        utils.heavyLogging('URFResult2JIRA: create issue [{}] failed'.format(jiraIssueFields['summary']))
        sys.exit(-1)
    else:
        issueKey = jsonIssueResult['key']
        utils.heavyLogging('URFResult2JIRA: new JIRA issue: {}'.format(issueKey))
        assignee = dict()
        assignee['name'] = configs['issue_assignee']
        with open('assignee.json', 'w') as fp:
            json.dump(assignee, fp)
        jira.jiraAssignIssue(configs['jira_site'], issueKey, 'assignee.json', 'urfAssignResult.json')

        if urfRecord['code'] == 0:
            attachURFArtifacts(artifactFiles, issueKey, configs)
        #else:
        #    return issueKey
    # TODO: remove chdir
    os.chdir(pwd)
    return issueKey

def main(argv):
    # check if jenkins credentials defined (as env. variable)
    if "SMS_TOKEN" not in os.environ:
        sys.exit("Environmental variable SMS_TOKEN not defined")

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
            if os.path.isdir(value) == False:
                os.makedirs(value)
            WORK_DIR = value
            logging.basicConfig(filename=os.path.join(WORK_DIR, 'urfjira.log'), format='%(asctime)s %(levelname)-8s %(message)s', level=logging.DEBUG, filemode='w')

    # step 1
    #     Load configurations
    #     Get coverity project name if necessary
    #     Generate .coverity.license.config
    utils.translateConfig(configFile)
    configs = utils.loadConfigs(configFile)
    if configs['enable'] == False:
        print('skip')
        sys.exit(0)
    utils.cleanEnvAndArchives(WORK_DIR)
    issueKey = URFResult2JIRA(configs)
    if 'waiting_issue_status' in configs and configs['waiting_issue_status'] != '' and issueKey != '':
        waitingIssueClosed(issueKey, configs)

if __name__ == "__main__":
    main(sys.argv)
