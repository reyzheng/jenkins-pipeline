import json
import getopt, sys
import os, shutil, time
import subprocess as sb
import logging
import utils, jira

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

def attachURFArtifacts(jenkinsReportUrl, urfProjects, issueKey, configs):
    artifacts = configs['artifacts']
    jiraSite = configs['jira_site']
    if len(artifacts) == 0:
        utils.heavyLogging('attachURFArtifacts: skip attach')
        return

    #devopsUser = 'devops_jenkins'
    #devsopsToken = '111127675998c80122b3d03a0347f583cd'
    releaseJenkinsUser = configs['release_jenkins_user']
    releaseJenkinsToken = configs['release_jenkins_token']
    if 'RELEASE_JENKINS_TOKEN' in os.environ:
        releaseJenkinsToken = os.getenv('RELEASE_JENKINS_TOKEN')
    for artifact in artifacts:
        for urfProject in urfProjects:
            if artifact == 'RSCAT':
                utils.heavyLogging('attachURFArtifacts: Retrieve RSCAT')
                # https://user:token@release.rtkbf.com/jenkins/job/CTC_PSP_DEMO/job/Test/122/Release_20Report/rscat_CTCSOC_test.html'
                artifactFile = 'rscat_{}.html'.format(urfProject)
                utils.heavyLogging('attachURFArtifacts: Retrieve artifacts: {}{}'.format(jenkinsReportUrl, artifactFile))
                cmdCurl = sb.Popen(['curl', '-s', '-k', '-w', '%{http_code}', '-X', 'GET', \
                                        '--user', '{}:{}'.format(releaseJenkinsUser, releaseJenkinsToken), \
                                        '{}{}'.format(jenkinsReportUrl, artifactFile), '-o', artifactFile], stdout=sb.PIPE)
                cmdCurl.wait()
                while True:
                    http_code = cmdCurl.stdout.readline()
                    http_code = bytes.decode(http_code, 'utf-8')
                    break
                if http_code == '200':
                    jira.jiraUploadAttachment(jiraSite, issueKey, artifactFile)
                else:
                    utils.heavyLogging('attachURFArtifacts: Retrieve artifacts {} failed'.format(artifactFile))
            elif artifact == 'COVREPORT':
                utils.heavyLogging('attachURFArtifacts: Retrieve COVREPORT')
                # https://user:token@release.rtkbf.com/jenkins/job/CTC_PSP_DEMO/job/Test/122/Release_20Report/user/coverity_CTCSOC_test_cvss.xml'
                artifactFiles = ['coverity_{}_cvss.pdf'.format(urfProject),
                                 'coverity_{}_integrity.pdf'.format(urfProject),
                                 'coverity_{}_security.pdf'.format(urfProject),]
                for artifactFile in artifactFiles:
                    utils.heavyLogging('attachURFArtifacts: Retrieve artifacts {}user/{}'.format(jenkinsReportUrl, artifactFile))
                    cmdCurl = sb.Popen(['curl', '-s', '-k', '-w', '%{http_code}', '-X', 'GET', \
                                            '--user', '{}:{}'.format(releaseJenkinsUser, releaseJenkinsToken), \
                                            '{}user/{}'.format(jenkinsReportUrl, artifactFile), '-o', artifactFile], stdout=sb.PIPE)
                    cmdCurl.wait()
                    while True:
                        http_code = cmdCurl.stdout.readline()
                        http_code = bytes.decode(http_code, 'utf-8')
                        break
                    if http_code == '200':
                        jira.jiraUploadAttachment(jiraSite, issueKey, artifactFile)
                    else:
                        utils.heavyLogging('attachURFArtifacts: Retrieve artifacts {} failed'.format(artifactFile))
            elif artifact == 'BDREPORT':
                utils.heavyLogging('attachURFArtifacts: Retrieve BDREPORT')
                # https://user:token@release.rtkbf.com/jenkins/job/CTC_PSP_DEMO/job/Test/122/Release_20Report/user/blackduck_CTCSOC_test_components.csv'
                artifactFiles = ['blackduck_{}_components.csv'.format(urfProject),
                                 'blackduck_{}_security.csv'.format(urfProject)]
                for artifactFile in artifactFiles:
                    utils.heavyLogging('attachURFArtifacts: Retrieve artifacts: {}user/{}'.format(jenkinsReportUrl, artifactFile))
                    cmdCurl = sb.Popen(['curl', '-s', '-k', '-w', '%{http_code}', '-X', 'GET', \
                                            '--user', '{}:{}'.format(releaseJenkinsUser, releaseJenkinsToken), \
                                            '{}user/{}'.format(jenkinsReportUrl, artifactFile), '-o', artifactFile], stdout=sb.PIPE)
                    cmdCurl.wait()
                    while True:
                        http_code = cmdCurl.stdout.readline()
                        http_code = bytes.decode(http_code, 'utf-8')
                        break
                    if http_code == '200':
                        jira.jiraUploadAttachment(jiraSite, issueKey, artifactFile)
                    else:
                        utils.heavyLogging('attachURFArtifacts: Retrieve artifacts {} failed'.format(artifactFile))
            elif artifact.startswith('file:'):
                tokens = artifact.split(':')
                if os.path.isfile(tokens[1]):
                    jira.jiraUploadAttachment(jiraSite, issueKey, tokens[1])
                    utils.heavyLogging('attachURFArtifacts: file {}'.format(tokens[1]))
                else:
                    utils.heavyLogging('attachURFArtifacts: invalid file {}'.format(tokens[1]))
            else:
                utils.heavyLogging('attachURFArtifacts: invalid artifacts {}'.format(artifact))

def absArtifactsPath(configs):
    for i in range(len(configs['artifacts'])):
        if configs['artifacts'][i].startswith('file:'):
            tokens = configs['artifacts'][i].split(':')
            configs['artifacts'][i] = 'file:{}'.format(os.path.abspath(tokens[1]))
    return configs

def URFResult2JIRA(configs):
    global WORK_DIR
    global JENKINS_WS

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
    configs['jira_project'] = jira.jiraGetProjectKey(configs['jira_site'], configs['jira_project'])
    # take RELEASE_JOB as epic
    jira.getKeyFields(configs['jira_site'], '')
    utils.heavyLogging('Take RELEASE_JOB as EPIC name: {}'.format(RELEASE_JOB))
    jira.getEPICKey(configs['jira_site'], configs['jira_project'], RELEASE_JOB)

    fpEPICKey = open('epicKey.json')
    fpEPICLinkField = open('epicLinkField.json')
    epicKey = json.load(fpEPICKey)
    epicLinkFieldId = json.load(fpEPICLinkField)
    fpEPICKey.close()
    fpEPICLinkField.close()
    epicKey = epicKey['key']
    epicLinkFieldId = epicLinkFieldId['id']
    utils.heavyLogging('EPIC key: {}'.format(epicKey))
    utils.heavyLogging('EPIC link field id: {}'.format(epicLinkFieldId))

    urfRecord = utils.queryURFReleaseRecord(SMSURFId)
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
    jiraIssueFields[epicLinkFieldId] = epicKey
    jiraIssueFields['issuetype'] = dict()
    jiraIssueFields['issuetype']['name'] = "Task"
    jiraIssue['fields'] = jiraIssueFields
    with open("urfIssue.json", "w") as outfile:
        json.dump(jiraIssue, outfile)
    jira.jiraCreateIssue(configs['jira_site'], 'urfIssue.json', 'urfIssueResult.json')
    fpIssueResult = open('urfIssueResult.json')
    jsonIssueResult = json.load(fpIssueResult)
    fpIssueResult.close()
    if 'errors' in jsonIssueResult:
        # create issue failed
        logging.debug('Create issue {} field'.format(jiraIssueFields['summary']))
    else:
        issueKey = jsonIssueResult['key']
        logging.debug('New JIRA issue: {}'.format(issueKey))
        assignee = dict()
        assignee['name'] = configs['issue_assignee']
        with open('assignee.json', 'w') as fp:
            json.dump(assignee, fp)
        jira.jiraAssignIssue(configs['jira_site'], issueKey, 'assignee.json', 'urfAssignResult.json')

        if urfRecord['code'] == 0:
            jenkinsReportUrl = urfRecord['data']['jenkinsReport']
            utils.heavyLogging('URFResult2JIRA: got URF Report URL {} success'.format(jenkinsReportUrl))
        else:
            utils.heavyLogging('URFResult2JIRA: got URF Report URL ({}) failed, cannot attach report to JIRA'.format(SMSURFId))
            return
        attachURFArtifacts(jenkinsReportUrl, urfProjects, issueKey, configs)
        #jira.jiraUploadAttachment(configs['jira_site'], 'urfIssue.json', 'urfIssueResult.json')
                    #jiraUploadAttachment idOrKey: issueKey, 
                    #                            file: miscInfo["REPORTS"][i], 
                    #                            site: jiraConfig.site_name
                    #jiraAssignIssue idOrKey: issueKey, 
                    #                        userName: jiraConfig.urf_to_jira_assignee, 
                    #                        accountId: "",
                    #                        site: jiraConfig.site_name
    os.chdir(pwd)

def main(argv):
    # check if jenkins credentials defined (as env. variable)
    if "SMS_TOKEN" not in os.environ:
        sys.exit("Environmental variable SMS_TOKEN not defined")

    configFile = ''
    global JENKINS_WS
    global WORK_DIR
    try:
        opts, args = getopt.getopt(argv[1:], 'w:j:f:u:p:v', ["work_dir=", "jenkins_workspace=", "config=", "user=", "password=", "version"])
    except getopt.GetoptError:
        sys.exit()
    for name, value in opts:
        if name in ('-v', '--version'):
            print("0.1")
            sys.exit(0)
        elif name in ('-u', '--user'):
            # override if --user
            covuser = value
        elif name in ('-p', '--password'):
            # override if --password
            covpass = value
        elif name in ('-f', '--config'):
            configFile = value
        elif name in ('-j', '--jenkins_workspace'):
            JENKINS_WS = value
        elif name in ('-w', '--work_dir'):
            if os.path.isdir(value) == False:
                os.makedirs(value)
            WORK_DIR = value
            logging.basicConfig(filename=os.path.join(WORK_DIR, 'urfjira.log'), level=logging.DEBUG, filemode='w')

    # step 1
    #     Load configurations
    #     Get coverity project name if necessary
    #     Generate .coverity.license.config
    configs = utils.loadConfigs(configFile)
    if configs['enable'] == False:
        print('skip')
        sys.exit(0)
    URFResult2JIRA(configs)

if __name__ == "__main__":
    main(sys.argv)
