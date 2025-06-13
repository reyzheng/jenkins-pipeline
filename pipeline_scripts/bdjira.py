import json
import getopt, sys
from math import log
import os, shutil, time
import subprocess as sb
import logging
import re
import utils
import jira

jiraIssues = dict()
configs = dict()
JENKINS_WS = ""
WORK_DIR = ""

def getExistedJIRAIssues(jiraSite, jiraProject, jiraIssueType, bdProject, bdVersion):
    issueTypes = jira.jiraProjectIssueTypes(jiraSite, jiraProject)
    if jiraIssueType == 'Issue' and 'Issue' in issueTypes:
        jqlCommand = "project={} and (issuetype='Task' or issuetype='Issue')".format(jiraProject)
    else:
        jqlCommand = "project={} and issuetype='Task'".format(jiraProject)
    jqlCommand = jqlCommand + ' and labels=\'BDPRJ:{}\' and labels=\'BDVER:{}\''.format(bdProject.replace(' ', '_'), bdVersion)

    issues = []
    utils.heavyLogging('getExistedJIRAIssues: {}'.format(jqlCommand))
    for i in range(100):
        jira.jiraJQLSearch(jiraSite, jqlCommand, i*1000, 1000, 'issues.json')
        with open('issues.json', encoding='utf-8') as f:
            ret = json.load(f)
        issues = issues + ret['issues']
        if len(ret['issues']) < 1000:
            break
    with open("issues.json", "w") as outfile:
        json.dump(issues, outfile)

def parseComponents(bdProject, bdVersion, bdRules):
    # sometimes the source is folder, so it is hard to find author of security, components sources
    global jiraIssues
    with open('output.json', encoding='utf-8') as f:
        jsonSummary = json.load(f)

    components = jsonSummary['components']
    for component in components:
        componentName = component['componentName']
        # unexpected unknown version
        if 'componentVersionName' in component:
            versionName = component['componentVersionName']
        else:
            versionName = 'unknown'
        issueIndex = '{}-{}'.format(componentName, versionName)

        toJIRAIssue = False

        licenseLabels = []
        licenseDesc = ''
        utils.lightLogging('parseComponents: component {}, version {}'.format(componentName, versionName))
        if 'components' in bdRules:
            hasCriticalHighLicenseRisk = False
            utils.lightLogging('parseComponents: check component risk')
            licenses = component['licenses']
            if len(licenses) > 0 and 'licenseType' in licenses[0] and \
                    (licenses[0]['licenseType'] == 'CONJUNCTIVE' or licenses[0]['licenseType'] == 'DISJUNCTIVE'):
                licenses = licenses[0]['licenses']
            utils.lightLogging('parseComponents: licenses {}'.format(licenses))
            for license in licenses:
                if license['licenseFamilyName'] == 'RECIPROCAL' or license['licenseFamilyName'] == 'AGPL':
                    licenseDesc = licenseDesc + 'license: {}, family: {}\n'.format(license['licenseDisplay'], license['licenseFamilyName'])
            riskProfileInfo = component['licenseRiskProfile']
            for countInfo in riskProfileInfo['counts']:
                if (countInfo['countType'] == 'CRITICAL' and countInfo['count'] > 0):
                    licenseLabels.append('license:CRITICAL')
                    hasCriticalHighLicenseRisk = True
                if (countInfo['countType'] == 'HIGH' and countInfo['count'] > 0):
                    licenseLabels.append('license:HIGH')
                    hasCriticalHighLicenseRisk = True
            if hasCriticalHighLicenseRisk == True and component['reviewStatus'] == 'NOT_REVIEWED' and component['ignored'] == False:
                toJIRAIssue = True
            utils.lightLogging('parseComponents: component risk {}'.format(licenseLabels))

        vulLabels = []
        vulDesc = ''
        if 'security' in bdRules:
            utils.lightLogging('parseComponents: check security risk')
            origins = component['origins']
            for origin in origins:
                vulnerabilities = origin['vulnerabilities']
                for vulnerability in vulnerabilities:
                    if 'severity' in vulnerability and (vulnerability['severity'] == 'CRITICAL' or vulnerability['severity'] == 'HIGH'):
                        vulLabels.append(vulnerability['vulnerabilityName'])
                        if vulnerability['remediationStatus'] == 'NEW':
                            toJIRAIssue = True
                        vulDesc = vulDesc + '{} severity:{}, status:{}\n'.format(vulnerability['vulnerabilityName'], vulnerability['severity'], vulnerability['remediationStatus'])
            utils.lightLogging('parseComponents: security risk {}'.format(vulLabels))
        summary = '{} {}'.format(componentName, versionName)
        if issueIndex not in jiraIssues:
            # push this componet to jiraIssues
            jiraIssues[issueIndex] = dict()
            jiraIssues[issueIndex]['fields'] = dict()
            jiraIssues[issueIndex]['fields']['project'] = dict()
            jiraIssues[issueIndex]['fields']['summary'] = summary
            desc = 'component: {}\n'.format(componentName)
            desc = desc + 'version: {}\n'.format(versionName)
            desc = desc + licenseDesc
            desc = desc + vulDesc
            desc = desc + 'review status: {}\n'.format(component['reviewStatus'])
            desc = desc + 'ignored: {}\n'.format(component['ignored'])
            if 'lastCommitDate' in component['activityData']:
                desc = desc + 'last commitDate: {}\n'.format(component['activityData']['lastCommitDate'])
            else:
                desc = desc + 'last commitDate: unknown\n'
            if 'componentVersion' in component:
                desc = desc + component['componentVersion']
            jiraIssues[issueIndex]['fields']['description'] = desc
            jiraIssues[issueIndex]['fields']['issuetype'] = dict()
            jiraIssues[issueIndex]['fields']['issuetype']['name'] = 'Task'
            jiraIssues[issueIndex]['fields']['labels'] = []
            jiraIssues[issueIndex]['fields']['labels'].append('BDPRJ:{}'.format(bdProject.replace(' ', '_')))
            jiraIssues[issueIndex]['fields']['labels'].append('BDVER:{}'.format(bdVersion))
        if toJIRAIssue == False:
            utils.lightLogging('parseComponents: skip JIRA')
            jiraIssues[issueIndex]['close_issue'] = True
        else:
            utils.lightLogging('parseComponents: to JIRA')
            jiraIssues[issueIndex]['close_issue'] = False
        jiraIssues[issueIndex]['fields']['labels'] = jiraIssues[issueIndex]['fields']['labels'] + vulLabels + licenseLabels

def parseSnippets(bdProject, bdVersion):
    dangerFamily = ['Reciprocal', 'AGPL']

    pwd = os.getcwd()
    global jiraIssues
    with open('output.json', encoding='utf-8') as f:
        jsonSummary = json.load(f)
    # parse licenses
    dangerLicenses = []
    licenses = jsonSummary['licenses']
    for key in licenses:
        if licenses[key]['licenseFamily']['name'] in dangerFamily:
            if 'spdxId' in licenses[key]:
                # the strange license "GNU General Public License v2.0 with Linux Syscall Note" has no spdxId
                dangerLicenses.append(licenses[key]['spdxId'])
    utils.heavyLogging('parseSnippets: dangerLicenses, {}'.format(dangerLicenses))

    snippets = jsonSummary['source_bom']
    for snippet in snippets:
        issueIndex = '{}-{}'.format(snippet['name'], snippet['compositeId'])
        labels = []
        bomComponents = []
        hasNotReviewedSnippet = False
        for fileSnippetBomComponent in snippet['fileSnippetBomComponents']:
            if len(fileSnippetBomComponent['license']['licenses']) > 0:
                # conjunctive licenses
                allLicenses = fileSnippetBomComponent['license']['licenses']
            else:
                allLicenses = []
                allLicenses.append(fileSnippetBomComponent['license'])
            for license in allLicenses:
                if 'spdxId' in license and license['spdxId'] in dangerLicenses:
                    labels.append(license['spdxId'])
                    bomComponent = dict()
                    bomComponent['license'] = license['spdxId']
                    bomComponent['component'] = dict()
                    bomComponent['component']['name'] = fileSnippetBomComponent['project']['name']
                    bomComponent['component']['version'] = fileSnippetBomComponent['release']['version']
                    bomComponent['component']['reviewStatus'] = fileSnippetBomComponent['reviewStatus']
                    bomComponent['component']['ignored'] = fileSnippetBomComponent['ignored']

                    foundAuthor = False
                    # sourceStartLines/sourceEndLines: mine
                    # matchStartLines/matchEndLines: matched OSS component file
                    startLine = fileSnippetBomComponent['sourceStartLines'][0]
                    endLine = fileSnippetBomComponent['sourceEndLines'][0]
                    event = dict()
                    event["startLine"] = startLine
                    event["endLine"] = endLine
                    event["author"] = ''
                    event["authorfull"] = ''

                    if snippet['uri'].startswith('file://'):
                        try:
                            filepath = snippet['uri'][7:]
                            filedir = os.path.dirname(os.path.abspath(filepath))
                            filename = os.path.basename(filepath)
                            os.chdir(filedir)
                            cmds = ['git', 'blame' , '-e', '-L', '{},{}'.format(startLine, endLine), filename]
                            utils.heavyLogging("parseSnippets: git blame {} {}:{}\n".format(filepath, startLine, endLine))
                            authorLine = utils.popenFirstLine(cmds, dict(os.environ))
                            #if "realtek" in line or "realsil" in line:
                            if "@" in authorLine:
                                authorLine = re.split('[>< ]', authorLine)
                                if '@' in authorLine[2]:
                                    authorLine = authorLine[2]
                                else:
                                    authorLine = authorLine[3]
                                if "realtek" not in authorLine and "realsil" not in authorLine:
                                    utils.heavyLogging("parseSnippets: skip non-rtk {}: {}\n".format(filepath, authorLine))
                                    continue
                                tokens = authorLine.split('@')
                                author = tokens[0]
                                authorfull = authorLine
                                foundAuthor = True
                                utils.heavyLogging("parseSnippets: found author: {}".format(author))
                            else:
                                utils.heavyLogging("parseSnippets: invlid author: {}".format(authorLine))
                            if foundAuthor == True:
                                event["author"] = author
                                event["authorfull"] = authorfull
                        except:
                            utils.heavyLogging("parseSnippets: invalid uri, {}".format(snippet['uri']))

                    bomComponent['event'] = event
                    bomComponents.append(bomComponent)
            # user has two choices
            # 1. change reviewStatus from NOT_REVIEWED to Confirmed
            # 2. change ignored from False to True
            if fileSnippetBomComponent['reviewStatus'] == 'NOT_REVIEWED' and fileSnippetBomComponent['ignored'] == False:
                hasNotReviewedSnippet = True

        summary = '[SNIPPET] {}({})'.format(snippet['name'], snippet['compositeId'])
        if issueIndex not in jiraIssues:
            # push this componet to jiraIssues
            jiraIssues[issueIndex] = dict()
            jiraIssues[issueIndex]['fields'] = dict()
            jiraIssues[issueIndex]['fields']['project'] = dict()
            jiraIssues[issueIndex]['fields']['summary'] = summary
            desc = 'name: {}\n'.format(snippet['name'])
            desc = desc + 'path: {}\n'.format(snippet['uri'])
            for bomComponent in bomComponents:
                desc = desc + 'component: {} {} ({}), {}:{} {}\n'.format(bomComponent['component']['name'], bomComponent['component']['version'], \
                                                                         bomComponent['license'], bomComponent['event']['startLine'], bomComponent['event']['endLine'], 
                                                                         bomComponent['event']['author'])
                desc = desc + 'reviewStatus: {}\n'.format(bomComponent['component']['reviewStatus'])
                desc = desc + 'ignored: {}\n'.format(bomComponent['component']['ignored'])
            jiraIssues[issueIndex]['fields']['description'] = desc
            jiraIssues[issueIndex]['fields']['issuetype'] = dict()
            jiraIssues[issueIndex]['fields']['issuetype']['name'] = 'Task'
            jiraIssues[issueIndex]['fields']['labels'] = []
            jiraIssues[issueIndex]['fields']['labels'].append('BDPRJ:{}'.format(bdProject.replace(' ', '_')))
            jiraIssues[issueIndex]['fields']['labels'].append('BDVER:{}'.format(bdVersion))
        if hasNotReviewedSnippet == False or len(labels) == 0:
            utils.lightLogging('parseSnippets: skip JIRA')
            jiraIssues[issueIndex]['close_issue'] = True
        else:
            utils.lightLogging('parseSnippets: to JIRA')
            jiraIssues[issueIndex]['close_issue'] = False
        jiraIssues[issueIndex]['fields']['labels'] = jiraIssues[issueIndex]['fields']['labels'] + labels
    os.chdir(pwd)

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
                                    '--wait', '--output', 'output.json'], stdout=sb.PIPE)
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
        json.dump(bulks, outfile, indent=2)

    os.remove('config.bd_cli.yml')
    os.chdir(pwd)

def publishBDIssues():
    pwd = os.getcwd()
    os.chdir(WORK_DIR)

    configs['jira_project'] = jira.jiraGetProjectKey(configs['jira_site'], configs['jira_project'], '')
    utils.heavyLogging('publishBDIssues: JIRA project key {}'.format(configs['jira_project']))
    utils.heavyLogging('publishBDIssues: validate user {}'.format(configs['issue_assignee']))
    jira.jiraValidateUser(configs['jira_site'], configs['issue_assignee'])
    with open('validate-{}.json'.format(configs['issue_assignee']), encoding='utf-8') as f:
        userInfo = json.load(f)
    if 'errorMessages' in userInfo:
        utils.heavyLogging('publishBDIssues: validate user fail')
        sys.exit(-1)

    with open('bdIssues.json', encoding='utf-8') as f:
        bulks = json.load(f)
    for bulkKey in bulks:
        bdProject = bulks[bulkKey]['project']
        bdVersion = bulks[bulkKey]['version']
        jiraIssues = bulks[bulkKey]['issues']

        # get existed issues
        getExistedJIRAIssues(configs['jira_site'], configs['jira_project'], 'Task', bdProject, bdVersion)
        with open('issues.json', encoding='utf-8') as f:
            existedIssues = json.load(f)
        existedIssuesHash = dict()
        for j in range(len(existedIssues)):
            existedIssuesHash[existedIssues[j]['fields']['summary']] = j
            # flag to check if discovered at current scan
            existedIssues[j]['detected'] = False
            logging.debug('publishBDIssues: construct hash {}/{}'.format(existedIssues[j]['fields']['summary'], j))

        # fill projectKey and update detected flag
        for key in jiraIssues:
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
            # key = 'componentName-versionName'
            jiraIssue = jiraIssues[key]
            with open("jiraIssue.json", "w") as outfile:
                json.dump(jiraIssue, outfile)
            if 'key' in jiraIssue:
                summary = jiraIssue['fields']['summary']
                index = existedIssuesHash[summary]
                existedIssueStatus = existedIssues[index]['fields']['status']['name'].lower()

                if jiraIssue['close_issue'] == True:
                    utils.heavyLogging('publishBDIssues: close reviewed/ignored issue {}'.format(key))
                    # close issue, ex.) reviewed or ignored
                    if existedIssueStatus.startswith('close'):
                        utils.heavyLogging('publishBDIssues: already closed')
                        pass
                    else:
                        jira.jiraUpdateIssue(configs['jira_site'], jiraIssue['key'], 'jiraIssue.json')
                        jira.jiraTransitStatus(configs['jira_site'], jiraIssue['key'], 'Close', '')
                else:
                    utils.heavyLogging('publishBDIssues: update issue {}'.format(key))
                    if existedIssueStatus.startswith('close'):
                        # transit to reopen if necessary
                        utils.heavyLogging('publishBDIssues: transit to reopen')
                        jira.jiraTransitStatus(configs['jira_site'], jiraIssue['key'], 'Reopen', '')
                    else:
                        pass
                    # update
                    jira.jiraUpdateIssue(configs['jira_site'], jiraIssue['key'], 'jiraIssue.json')
            else:
                if jiraIssue['close_issue'] == True:
                    utils.heavyLogging('publishBDIssues: new issue {} skipped'.format(key))
                else:
                    # new
                    utils.heavyLogging('publishBDIssues: new issue {}'.format(key))
                    jira.jiraCreateIssue(configs['jira_site'], 'jiraIssue.json', 'newIssueResult.json')
                    with open('newIssueResult.json', encoding='utf-8') as fpIssueResult:
                        jsonIssueResult = json.load(fpIssueResult)
                    if 'errors' in jsonIssueResult:
                        # create issue failed
                        utils.heavyLogging('publishBDIssues: create issue {} failed'.format(jiraIssue['fields']['summary']))
                    else:
                        issueKey = jsonIssueResult['key']
                        utils.heavyLogging('publishBDIssues: create JIRA issue {}'.format(issueKey))
                        assignee = dict()
                        assignee['name'] = configs['issue_assignee']
                        with open('assignee.json', 'w') as fp:
                            json.dump(assignee, fp)
                        utils.heavyLogging('publishBDIssues: assign JIRA issue {} to {}'.format(issueKey, assignee['name']))
                        jira.jiraAssignIssue(configs['jira_site'], issueKey, 'assignee.json', 'urfAssignResult.json')

        # close issue no longer existed, ex.) the component is not detected
        for existedIssue in existedIssues:
            if existedIssue['detected'] == False:
                utils.heavyLogging('publishBDIssues: close issue not detected {}'.format(existedIssue['key']))
                jira.jiraTransitStatus(configs['jira_site'], existedIssue['key'], 'Close', '')
    os.chdir(pwd)

def copyRemoteArtifacts():
    reportFile = 'bdIssues.json'
    cmdEnv = dict(os.environ)
    user = 'devops_jenkins'
    if 'SDJENKINS_USER' in os.environ:
        user = os.getenv('SDJENKINS_USER')
    # copy bdIssues.json
    utils.popenWithStdout(['curl', '-s', '-X', 'GET', '-u', '{}:{}'.format(user, os.getenv('SDJENKINS_TOKEN')), \
                        '--url', '{}artifact/{}'.format(os.getenv('SDJENKINS_URL'), reportFile), \
                        '-o', '{}/{}'.format(WORK_DIR, reportFile)], cmdEnv)
    # copy RJIRA token
    cmdCurl = sb.Popen(['curl', '-s', '-X', 'GET', '-u', '{}:{}'.format(user, os.getenv('SDJENKINS_TOKEN')), \
                        '--url', '{}artifact/encryptToken'.format(os.getenv('SDJENKINS_URL')), \
                        '-o', '{}/encryptToken'.format(WORK_DIR)], stdout=sb.PIPE)
    cmdCurl.wait()
    from Crypto.PublicKey import RSA
    from Crypto.Cipher import PKCS1_OAEP
    privateKey = RSA.import_key(open(os.getenv('DECRYPT_KEY')).read())
    cipherRSA = PKCS1_OAEP.new(privateKey)
    plainToken = cipherRSA.decrypt(open('{}/encryptToken'.format(WORK_DIR), 'rb').read())
    plainToken = bytes.decode(plainToken, 'utf-8')
    with open(os.path.join(WORK_DIR, 'env'), 'w') as fp:
        fp.write('JIRA_TOKEN={}\n'.format(plainToken))

def main(argv):
    # check if jenkins credentials defined (as env. variable)
    if "BD_TOKEN" not in os.environ and \
        "DECRYPT_KEY" not in os.environ and \
        "JIRA_TOKEN" not in os.environ and \
        "JIRA_USER" not in os.environ:
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
    logging.basicConfig(filename=os.path.join(WORK_DIR, 'bdjira.log'), format='%(asctime)s %(levelname)-8s %(message)s', level=logging.DEBUG, filemode='w')
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