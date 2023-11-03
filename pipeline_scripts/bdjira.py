import json
import getopt, sys
from math import log
import os, shutil, time
import subprocess as sb
import logging
import utils
import jira, covjira

jiraIssues = dict()
configs = dict()
JENKINS_WS = ""
WORK_DIR = ""

def parseComponents(bdProject, bdVersion, bdRules):
    global jiraIssues
    with open('output.json') as f:
        jsonSummary = json.load(f)

    components = jsonSummary['components']
    for component in components:
        componentName = component['componentName']
        versionName = component['componentVersionName']
        issueIndex = '{}-{}'.format(componentName, versionName)
        #labels = []
        # TODO: waiting for Realtek's components rule
        #if 'components' in bdRules:
        #    riskProfileInfo = component['licenseRiskProfile']
        #    for countInfo in riskProfileInfo['counts']:
        #        if (countInfo['countType'] == 'CRITICAL' and countInfo['count'] > 0):
        #            labels.append('license:CRITICAL')
        #        if (countInfo['countType'] == 'HIGH' and countInfo['count'] > 0):
        #            labels.append('license:HIGH')
        isVulComponent = False
        vulLabels = []
        vulDesc = ''
        if 'security' in bdRules:
            origins = component['origins']
            for origin in origins:
                vulnerabilities = origin['vulnerabilities']
                for vulnerability in vulnerabilities:
                    if vulnerability['severity'] == 'CRITICAL' or vulnerability['severity'] == 'HIGH':
                        isVulComponent = True
                        utils.heavyLogging('parseComponents: {}-{} security awared'.format(componentName, versionName))
                    if vulnerability['remediationStatus'] == 'NEW':
                        vulLabels.append(vulnerability['vulnerabilityName'])
                    vulDesc = vulDesc + '{} severity:{}, status:{}\n'.format(vulnerability['vulnerabilityName'], vulnerability['severity'], vulnerability['remediationStatus'])
        if isVulComponent == False:
            continue

        summary = '{} {}'.format(componentName, versionName)
        if issueIndex not in jiraIssues:
            # push this componet to jiraIssues
            jiraIssues[issueIndex] = dict()
            jiraIssues[issueIndex]['fields'] = dict()
            jiraIssues[issueIndex]['fields']['project'] = dict()
            jiraIssues[issueIndex]['fields']['summary'] = summary
            desc = 'component: {}\n'.format(componentName)
            desc = desc + 'version: {}\n'.format(versionName)
            desc = desc + vulDesc
            desc = desc + 'review status: {}\n'.format(component['reviewStatus'])
            desc = desc + 'last commitDate: {}\n'.format(component['activityData']['lastCommitDate'])
            desc = desc + component['componentVersion']
            jiraIssues[issueIndex]['fields']['description'] = desc
            jiraIssues[issueIndex]['fields']['issuetype'] = dict()
            jiraIssues[issueIndex]['fields']['issuetype']['name'] = 'Task'
            jiraIssues[issueIndex]['fields']['labels'] = []
            jiraIssues[issueIndex]['fields']['labels'].append(bdProject)
            jiraIssues[issueIndex]['fields']['labels'].append(bdVersion)
        jiraIssues[issueIndex]['fields']['labels'] = jiraIssues[issueIndex]['fields']['labels'] + vulLabels

#def parseSnippets(epicLinkFieldId, epicKey, bdProject, bdVersion, existedIssues, existedIssuesHash):
def parseSnippets(bdProject, bdVersion):
    global jiraIssues
    with open('output.json') as f:
        jsonSummary = json.load(f)
    # parse licenses
    dangerLicenses = []
    licenses = jsonSummary['licenses']
    for key in licenses:
        if 'Reciprocal' in licenses[key]['licenseFamily']['name']:
            dangerLicenses.append(licenses[key]['spdxId'])
    logging.debug('parseSnippets: {}'.format(dangerLicenses))

    snippets = jsonSummary['source_bom']
    for snippet in snippets:
        issueIndex = '{}'.format(snippet['name'])
        labels = []
        boms = dict()
        hasNotReviewedSnippet = False
        for fileSnippetBomComponent in snippet['fileSnippetBomComponents']:
            for license in fileSnippetBomComponent['license']['licenses']:
                if 'spdxId' in license and license['spdxId'] in dangerLicenses:
                    labels.append(license['spdxId'])
                    boms[license['spdxId']] = fileSnippetBomComponent
            if fileSnippetBomComponent['reviewStatus'] == 'NOT_REVIEWED':
                hasNotReviewedSnippet = True
        if hasNotReviewedSnippet == False:
            utils.heavyLogging('parseSnippets: {} reviewed'.format(snippet['name']))
            continue
        if len(labels) == 0:
            continue
        summary = '[SNIPPET] {}'.format(snippet['name'])
        if issueIndex not in jiraIssues:
            # push this componet to jiraIssues
            jiraIssues[issueIndex] = dict()
            jiraIssues[issueIndex]['fields'] = dict()
            jiraIssues[issueIndex]['fields']['project'] = dict()
            jiraIssues[issueIndex]['fields']['summary'] = summary
            desc = 'name: {}\n'.format(snippet['name'])
            desc = desc + 'path: {}\n'.format(snippet['compositePath']['path'])
            for label in labels:
                bom = boms[label]
                desc = desc + 'component: {} {} ({})\n'.format(bom['project']['name'], bom['release']['version'], label)
            desc = desc + 'reviewStatus: {}\n'.format(bom['reviewStatus'])
            jiraIssues[issueIndex]['fields']['description'] = desc
            jiraIssues[issueIndex]['fields']['issuetype'] = dict()
            jiraIssues[issueIndex]['fields']['issuetype']['name'] = 'Task'
            jiraIssues[issueIndex]['fields']['labels'] = []
            jiraIssues[issueIndex]['fields']['labels'].append(bdProject)
            jiraIssues[issueIndex]['fields']['labels'].append(bdVersion)
        jiraIssues[issueIndex]['fields']['labels'] = jiraIssues[issueIndex]['fields']['labels'] + labels

def bdToJIRAIssues():
    global jiraIssues
    global WORK_DIR
    global JENKINS_WS

    pwd = os.getcwd()
    os.chdir(WORK_DIR)

    utils.makeEmptyDirectory('blackduck_scan')
    cmdEnv = dict(os.environ)
    cmdEnv['GIT_SSL_NO_VERIFY'] = 'true'
    cmdGit = sb.Popen(['git', 'clone', 'https://mirror.rtkbf.com/gerrit/sdlc/hub-rest-api-python/builds', \
                            '--depth', '1', 'blackduck_scan'], stdout=sb.PIPE, env=cmdEnv)
    cmdGit.wait()

    with open('config.bd_cli.yml', 'w') as fpYaml:
        fpYaml.write('bd_url: {}\n'.format(configs['blackduck_url']))
        fpYaml.write('bd_token: {}\n'.format(os.getenv('BD_TOKEN')))
        fpYaml.write('insecure: true\n')
        fpYaml.write('timeout: 180\n')
        fpYaml.write('debug: true\n')
    #./bd_cli \
    #    project version-summary \
    #    PROJECT_NAME VERSION_NAME \
    #    --filter bomMatchType:snippet \
    #    --output "output.json"
    bdProjects = configs['blackduck_project'].split(',')
    bdVersions = configs['blackduck_version'].split(',')
    bulks = dict()
    for i in range(len(bdProjects)):
        cmdBDSummary = sb.Popen([os.path.join('blackduck_scan', 'bd_cli'), 'project', 'version-summary', \
                                    bdProjects[i], bdVersions[i], '--filter-source-bom', 'bomMatchType:snippet', \
                                    '--output', 'output.json'], stdout=sb.PIPE)
        cmdBDSummary.communicate()
        if not os.path.isfile('output.json'):
            utils.heavyLogging('bdToJIRAIssues: bd_cli version-summary failed {} {}'.format(bdProjects[i], bdVersions[i]))
            continue

        utils.heavyLogging('bdToJIRAIssues: bd_cli version-summary {} {} to JIRA'.format(bdProjects[i], bdVersions[i]))

        jiraIssues = dict()
        # JIRA Issue
        bdRules = configs['bdjira_rules'].split(',')
        utils.heavyLogging('bdToJIRAIssues: search {}'.format(bdRules))
        if 'components' in bdRules or 'security' in bdRules:
            parseComponents(bdProjects[i], bdVersions[i], bdRules)
        if 'snippets' in bdRules:
            parseSnippets(bdProjects[i], bdVersions[i])

        key = str(hash(bdProjects[i] + bdVersions[i]))
        bulks[key] = dict()
        bulks[key]['project'] = bdProjects[i]
        bulks[key]['version'] = bdVersions[i]
        bulks[key]['issues'] = jiraIssues.copy()

    # output jiraIssues to bdIssues.json
    with open("bdIssues.json", "w") as outfile:
        json.dump(bulks, outfile)

    os.remove('config.bd_cli.yml')
    os.chdir(pwd)

def publishBDIssues():
    pwd = os.getcwd()
    os.chdir(WORK_DIR)

    configs['jira_project'] = jira.jiraGetProjectKey(configs['jira_site'], configs['jira_project'])
    utils.heavyLogging('publishBDIssues: JIRA project key {}'.format(configs['jira_project']))
    utils.heavyLogging('publishBDIssues: validate user {}'.format(configs['issue_assignee']))
    jira.jiraValidateUser(configs['jira_site'], configs['issue_assignee'])
    with open('validate-{}.json'.format(configs['issue_assignee'])) as f:
        userInfo = json.load(f)
    if 'errorMessages' in userInfo:
        utils.heavyLogging('publishBDIssues: validate user fail')
        sys.exit(-1)

    with open('bdIssues.json') as f:
        bulks = json.load(f)
    for bulkKey in bulks:
        bdProject = bulks[bulkKey]['project']
        bdVersion = bulks[bulkKey]['version']
        jiraIssues = bulks[bulkKey]['issues']
        # JIRA EPIC
        # take bd project as epic name: [Blackduck] CTCSOC_TEST
        jira.getKeyFields(configs['jira_site'], '')
        logging.debug('publishBDIssues: BD project as EPIC name: {}'.format(bdProject))
        jira.getEPICKey(configs['jira_site'], configs['jira_project'], '[Blackduck] {}'.format(bdProject))
        # get epic key and field id
        fpEPICKey = open('epicKey.json')
        fpEPICLinkField = open('epicLinkField.json')
        epicKey = json.load(fpEPICKey)
        epicLinkFieldId = json.load(fpEPICLinkField)
        fpEPICKey.close()
        fpEPICLinkField.close()
        epicKey = epicKey['key']
        epicLinkFieldId = epicLinkFieldId['id']
        logging.debug('publishBDIssues: EPIC key {}'.format(epicKey))
        logging.debug('publishBDIssues: EPIC link field id {}'.format(epicLinkFieldId))

        # get existed issues
        covjira.getExistedJIRAIssues(configs['jira_site'], configs['jira_project'], 'Task', bdVersion)
        with open('issues.json') as f:
            existedIssues = json.load(f)
        existedIssuesHash = dict()
        for j in range(len(existedIssues)):
            existedIssuesHash[existedIssues[j]['fields']['summary']] = j
            # flag to check if discovered at current scan
            existedIssues[j]['detected'] = False
            logging.debug('publishBDIssues: construct hash {}/{}'.format(existedIssues[j]['fields']['summary'], j))

        # fill epicKey, projectKey and update detected flag
        for key in jiraIssues:
            jiraIssues[key]['fields'][epicLinkFieldId] = epicKey
            summary = jiraIssues[key]['fields']['summary']
            jiraIssues[key]['fields']['project']['key'] = configs['jira_project']
            if summary in existedIssuesHash:
                # already in existedIssuesHash
                jiraIssues[key]['key'] = existedIssues[existedIssuesHash[summary]]['key']
                existedIssues[existedIssuesHash[summary]]['detected'] = True
                logging.debug('publishBDIssues: existed {} {}'.format(key, jiraIssues[key]['key']))
            else:
                logging.debug('publishBDIssues: new {}'.format(key))

        # to JIRA
        for key in jiraIssues:
            jiraIssue = jiraIssues[key]
            with open("jiraIssue.json", "w") as outfile:
                json.dump(jiraIssue, outfile)
            if 'key' in jiraIssue:
                # transit to reopen if necessary
                jira.jiraTransitStatus(configs['jira_site'], jiraIssue['key'], 'Reopen', '')
                # update
                logging.debug('publishBDIssues: update {}'.format(jiraIssue['key']))
                jira.jiraUpdateIssue(configs['jira_site'], jiraIssue['key'], 'jiraIssue.json')
            else:
                # new
                logging.debug('publishBDIssues: new issue')
                jira.jiraCreateIssue(configs['jira_site'], 'jiraIssue.json', 'newIssueResult.json')
                fpIssueResult = open('newIssueResult.json')
                jsonIssueResult = json.load(fpIssueResult)
                fpIssueResult.close()
                if 'errors' in jsonIssueResult:
                    # create issue failed
                    logging.debug('publishBDIssues: create issue {} failed'.format(jiraIssue['fields']['summary']))
                else:
                    issueKey = jsonIssueResult['key']
                    logging.debug('publishBDIssues: create JIRA issue {}'.format(issueKey))
                    assignee = dict()
                    assignee['name'] = configs['issue_assignee']
                    with open('assignee.json', 'w') as fp:
                        json.dump(assignee, fp)
                    logging.debug('publishBDIssues: assign JIRA issue {} to {}'.format(issueKey, assignee['name']))
                    jira.jiraAssignIssue(configs['jira_site'], issueKey, 'assignee.json', 'urfAssignResult.json')
        # close issue no longer existed
        for existedIssue in existedIssues:
            if existedIssue['detected'] == False:
                logging.debug('publishBDIssues: close existed issue {}'.format(existedIssue['key']))
                jira.jiraTransitStatus(configs['jira_site'], existedIssue['key'], 'Close', '')
    os.chdir(pwd)

def copyRemoteArtifacts():
    reportFile = 'bdIssues.json'
    cmdEnv = dict(os.environ)
    user = 'devops_jenkins'
    if 'SDJENKINS_USER' in os.environ:
        user = os.getenv('SDJENKINS_USER')
    utils.popenWithStdout(['curl', '-s', '-X', 'GET', '-u', '{}:{}'.format(user, os.getenv('SDJENKINS_TOKEN')), \
                        '--url', '{}artifact/{}'.format(os.getenv('SDJENKINS_URL'), reportFile), \
                        '-o', '{}/{}'.format(WORK_DIR, reportFile)], cmdEnv)

def main(argv):
    # check if jenkins credentials defined (as env. variable)
    if "BD_TOKEN" not in os.environ and "JIRA_TOKEN" not in os.environ and "JIRA_USER" not in os.environ:
        sys.exit("Environmental variable BD_TOKEN/JIRA_TOKEN not defined")

    configFile = ''
    global JENKINS_WS
    global WORK_DIR
    global configs
    try:
        opts, args = getopt.getopt(argv[1:], 'c:w:j:f:v', ["command", "work_dir=", "jenkins_workspace=", "config=", "version"])
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
            WORK_DIR = value
        elif name in ('-c', '--command'):
            command = value
            
    if os.path.isdir(WORK_DIR) == False and WORK_DIR != '':
        os.makedirs(WORK_DIR)
    logging.basicConfig(filename=os.path.join(WORK_DIR, 'bdjira.log'), level=logging.DEBUG, filemode='w')
    # step 1
    #     Load configurations
    #     Get coverity project name if necessary
    #     Generate .coverity.license.config
    utils.translateConfig(configFile)
    configs = utils.loadConfigs(configFile)
    utils.checkLicense(os.path.dirname(sys.argv[0]), configs, 'bdjira')
    if command == "CREATE_ISSUES":
        bdToJIRAIssues()
    elif command == "PUBLISH_ISSUES":
        publishBDIssues()
    elif command == "COPY_REMOTE_ARTIFACTS":
        copyRemoteArtifacts()

if __name__ == "__main__":
    main(sys.argv)