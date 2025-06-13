import os, logging
import getopt, sys
import json
import urllib.parse
import subprocess as sb
from string import Template
import utils

workDir = ''

def checkJIRACredentials():
    if 'JIRA_TOKEN' not in os.environ and 'JIRA_USER' not in os.environ:
        sys.exit('Environmental variable JIRA_USER/JIRA_TOKEN not defined')

def getAuthPieces():
    authPieces = []
    if 'JIRA_TOKEN' in os.environ:
        authPieces = ['-H', 'Authorization: Bearer {}'.format(os.getenv('JIRA_TOKEN'))]
    elif 'JIRA_USER' in os.environ:
        authPieces = ['--user', '{}:{}'.format(os.getenv('JIRA_USER'), os.getenv('JIRA_PASSWORD'))]
    return authPieces

def jiraGetProjectKey(jiraSite, projectKey, workDir):
    checkJIRACredentials()
    authPieces = getAuthPieces()
    utils.heavyLogging('jiraGetProjectKey: check project key {}'.format(projectKey))
    cmdCurl = sb.Popen(['curl', '-k', '-s', '-w', '%{http_code}', '-X', 'GET', '--url', \
                        'https://{}/rest/api/2/project/{}'.format(jiraSite, projectKey), \
                        '-H', 'Accept: application/json', '-o', os.path.join(workDir, 'getProject.json')] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
    while True:
        http_code = cmdCurl.stdout.readline()
        http_code = bytes.decode(http_code, 'utf-8')
        break
    if http_code == '200':
        utils.heavyLogging('jiraGetProjectKey: valid project key {}'.format(projectKey))
        return projectKey
    else:
        # cannot found, maybe project name
        # WTF: https://jira.realtek.com/rest/api/2/project deprecated
        # recommended https://jira.realtek.com/rest/api/2/project/search error...
        cmdCurl = sb.Popen(['curl', '-k', '-s', '-X', 'GET', '--url', \
                            'https://{}/rest/api/2/project'.format(jiraSite), \
                            '-H', 'Accept: application/json', '-o', os.path.join(workDir, 'allProjects.json')] + authPieces, stdout=sb.PIPE)
        cmdCurl.wait()
        with open(os.path.join(workDir, 'allProjects.json'), 'r', encoding='utf-8') as f:
            allProjects = json.load(f)
        for project in allProjects:
            if project['name'] == projectKey:
                utils.heavyLogging('jiraGetProjectKey: found project {} key {}'.format(projectKey, project['key']))
                return project['key']

    utils.heavyLogging('jiraGetProjectKey: invalid project {}'.format(projectKey))
    return ''

def jiraJQLSearch(jiraSite, jql, startAt, maxResults, output):
    checkJIRACredentials()
    authPieces = getAuthPieces()
    utils.heavyLogging('jiraJQLSearch: jql {}'.format(jql))
    cmdCurl = sb.Popen(['curl', '-k', '-s', '-X', 'GET', '--url', \
                        'https://{}/rest/api/2/search?jql={}&startAt={}&maxResults={}'.format(jiraSite, urllib.parse.quote(jql), startAt, maxResults), \
                        '-H', 'Accept: application/json', '-o', output] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
    utils.lightLogging('jiraJQLSearch: jql encode {}'.format(urllib.parse.quote(jql)))
    utils.lightLogging('JIRA_rest_api:jql_search')

def jiraProjectIssueTypes(jiraSite, projectKey):
    checkJIRACredentials()
    authPieces = getAuthPieces()
    cmdCurl = sb.Popen(['curl', '-k', '-s', '-X', 'GET', '--url', \
                        'https://{}/rest/api/2/project/{}'.format(jiraSite, projectKey), \
                        '-H', 'Accept: application/json', '-o', 'projectInfo.json'] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
    ret = []
    with open('projectInfo.json', 'r', encoding='utf-8') as f:
        projectInfo = json.load(f)
    if 'issueTypes' in projectInfo:
        for issueType in projectInfo['issueTypes']:
            ret.append(issueType['name'])
    utils.heavyLogging('jiraProjectIssueTypes: {}'.format(ret))
    return ret

def jiraQueryIssue(jiraSite, issueKey, output):
    checkJIRACredentials()
    authPieces = getAuthPieces()

    cmdCurl = sb.Popen(['curl', '-k', '-s', '-w', '%{http_code}', '-X', 'GET', '--url', \
                        'https://{}/rest/api/2/issue/{}'.format(jiraSite, issueKey), \
                        '-H', 'Content-Type: application/json', \
                        '-H', 'Accept: application/json', '-o', output] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
    utils.lightLogging('JIRA_rest_api:query_issue')
    while True:
        http_code = cmdCurl.stdout.readline()
        http_code = bytes.decode(http_code, 'utf-8')
        break

    return http_code

def jiraCreateIssue(jiraSite, input, output, notifyUsers=True):
    checkJIRACredentials()
    authPieces = getAuthPieces()

    notifyParam = ''
    if notifyUsers == False:
        notifyParam = '?notifyUsers=false'

    cmdCurl = sb.Popen(['curl', '-k', '-s', '-w', '%{http_code}', '-X', 'POST', '--url', \
                        'https://{}/rest/api/2/issue{}'.format(jiraSite, notifyParam), \
                        '-H', 'Content-Type: application/json', \
                        '-H', 'Accept: application/json', '--data', '@{}'.format(input), '-o', output] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
    utils.lightLogging('JIRA_rest_api:create_issue')
    while True:
        http_code = cmdCurl.stdout.readline()
        http_code = bytes.decode(http_code, 'utf-8')
        break

    return http_code

def jiraUpdateIssue(jiraSite, idOrKey, input, notifyUsers=True):
    checkJIRACredentials()
    authPieces = getAuthPieces()

    notifyParam = ''
    if notifyUsers == False:
        notifyParam = '?notifyUsers=false'

    cmdCurl = sb.Popen(['curl', '-k', '-s', '-w', '%{http_code}', '-X', 'PUT', '--url', \
                        'https://{}/rest/api/2/issue/{}{}'.format(jiraSite, idOrKey, notifyParam), \
                        '-H', 'Content-Type: application/json', \
                        '-H', 'Accept: application/json', '--data', '@{}'.format(input)] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
    while True:
        http_code = cmdCurl.stdout.readline()
        http_code = bytes.decode(http_code, 'utf-8')
        break

    utils.lightLogging('JIRA_rest_api:update_issue {}'.format(http_code))
    return http_code

def jiraGetComments(jiraSite, idOrKey, output, notifyUsers=True):
    checkJIRACredentials()
    authPieces = getAuthPieces()

    notifyParam = ''
    if notifyUsers == False:
        notifyParam = '?notifyUsers=false'

    cmdCurl = sb.Popen(['curl', '-k', '-s', '-w', '%{http_code}', '-X', 'GET', '--url', \
                        'https://{}/rest/api/2/issue/{}/comment{}'.format(jiraSite, idOrKey, notifyParam), \
                        '-H', 'Accept: application/json', '-o', output] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
    while True:
        http_code = cmdCurl.stdout.readline()
        http_code = bytes.decode(http_code, 'utf-8')
        break

    if idOrKey == '':
        utils.heavyLogging('jiraGetComments: invalid issues key {}'.format(idOrKey))
    else:
        utils.heavyLogging('jiraGetComments: get comment of issues key {}, {}'.format(idOrKey, http_code))
    return http_code

def jiraAddComments(jiraSite, idOrKey, input, notifyUsers=True):
    checkJIRACredentials()
    authPieces = getAuthPieces()

    notifyParam = ''
    if notifyUsers == False:
        notifyParam = '?notifyUsers=false'

    cmdCurl = sb.Popen(['curl', '-k', '-s', '-w', '%{http_code}', '-X', 'POST', '--url', \
                        'https://{}/rest/api/2/issue/{}/comment{}'.format(jiraSite, idOrKey, notifyParam), \
                        '-H', 'Content-Type: application/json', \
                        '-H', 'Accept: application/json', '--data', '@{}'.format(input)] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
    utils.lightLogging('JIRA_rest_api:add_comment')
    while True:
        http_code = cmdCurl.stdout.readline()
        http_code = bytes.decode(http_code, 'utf-8')
        break

    utils.heavyLogging('jiraAddComments: add comment {}, {}'.format(idOrKey, http_code))
    return http_code

def jiraUpdateComments(jiraSite, idOrKey, commentId, input, notifyUsers=True):
    checkJIRACredentials()
    authPieces = getAuthPieces()

    notifyParam = ''
    if notifyUsers == False:
        notifyParam = '?notifyUsers=false'

    cmdCurl = sb.Popen(['curl', '-k', '-s', '-w', '%{http_code}', '-X', 'PUT', '--url', \
                        'https://{}/rest/api/2/issue/{}/comment/{}{}'.format(jiraSite, idOrKey, commentId, notifyParam), \
                        '-H', 'Content-Type: application/json', \
                        '-H', 'Accept: application/json', '--data', '@{}'.format(input)] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
    utils.lightLogging('JIRA_rest_api:add_comment')
    while True:
        http_code = cmdCurl.stdout.readline()
        http_code = bytes.decode(http_code, 'utf-8')
        break

    utils.heavyLogging('jiraUpdateComments: update comment {}, {}'.format(idOrKey, http_code))
    return http_code

def jiraAddWatcher(jiraSite, idOrKey, userId):
    checkJIRACredentials()
    authPieces = getAuthPieces()
    cmdCurl = sb.Popen(['curl', '-k', '-s', '-w', '%{http_code}', '-X', 'POST', '--url', \
                        'https://{}/rest/api/2/issue/{}/watchers'.format(jiraSite, idOrKey), \
                        '-H', 'Content-Type: application/json', \
                        '-H', 'Accept: application/json', '--data', '"{}"'.format(userId)] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
    utils.lightLogging('JIRA_rest_api:add_watcher')
    while True:
        http_code = cmdCurl.stdout.readline()
        http_code = bytes.decode(http_code, 'utf-8')
        break
    return http_code

def jiraDeleteAttachment(jiraSite, attachmentId):
    authPieces = getAuthPieces()
    cmdCurl = sb.Popen(['curl', '-k', '-s', '-X', 'DELETE', '--url', \
                        'https://{}/rest/api/2/attachment/{}'.format(jiraSite, attachmentId)] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()

def jiraUploadAttachment(jiraSite, idOrKey, filename, attachMode='IGNORE_EXISTED'):
    authPieces = getAuthPieces()
    if attachMode == 'REPLACE':
        attachmentId = 0
        output = 'summaryIssue.json'
        jiraQueryIssue(jiraSite, idOrKey, output)
        with open(output, 'r', encoding='utf-8') as fpSummary:
            summaryIssue = json.load(fpSummary)
            attachments = summaryIssue['fields']['attachment']
            for attachment in attachments:
                if attachment['filename'] == os.path.basename(filename):
                    attachmentId = attachment['id']
        if attachmentId != 0:
            jiraDeleteAttachment(jiraSite, attachmentId)

    cmdCurl = sb.Popen(['curl', '-k', '-s', '-X', 'POST', '--url', \
                        'https://{}/rest/api/2/issue/{}/attachments'.format(jiraSite, idOrKey), \
                        '-H', 'X-Atlassian-Token: no-check', \
                        '-H', 'Accept: application/json', '--form', 'file=@"{}"'.format(filename), \
                        '-o', 'uploadAttach-{}.json'.format(os.path.basename(filename))] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
    logging.debug('jiraUploadAttachment: upload attachment {}'.format(filename))

def jiraQueryUser(jiraSite, userName, output):
    authPieces = getAuthPieces()
    cmdCurl = sb.Popen(['curl', '-k', '-s', '-X', 'GET', '--url', \
                        'https://{}/rest/api/2/user?username={}'.format(jiraSite, userName), \
                        '-H', 'Content-Type: application/json', \
                        '-H', 'Accept: application/json', '--data', '@{}'.format(input), '-o', output] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()

def jiraMyself(jiraSite, outputJson):
    authPieces = getAuthPieces()
    # query myself info.
    cmdCurl = sb.Popen(['curl', '-k', '-s', '-w', '%{http_code}', '-X', 'GET', '--url', \
                        'https://{}/rest/api/2/myself'.format(jiraSite), \
                        '-H', 'Content-Type: application/json', \
                        '-H', 'Accept: application/json', '-o', outputJson] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
    while True:
        http_code = cmdCurl.stdout.readline()
        http_code = bytes.decode(http_code, 'utf-8')
        break
    if http_code == '200':
        with open(outputJson, 'r', encoding='utf-8') as f:
            myself = json.load(f)
        # Jira 7 introduces the concept of Application Access. Users require
        # application access to at least one application (Core, Software or Service Desk) to be able to create issues.
        if 'errorMessages' in myself or myself['applicationRoles']['size'] < 1:
            myself = dict()
            myself['name'] = 'INVALID'
            print('jiraMyself: query failure', flush=True)
        return myself
    else:
        utils.heavyLogging('jiraMyself: JIRA rest api error {} (incorrect JIRA token maybe.)'.format(http_code))
        sys.exit(-1)

def jiraMyPermissions(jiraSite, projectKey, idx):
    authPieces = getAuthPieces()
    # query my permission
    cmdCurl = sb.Popen(['curl', '-k', '-s', '-X', 'GET', '--url', \
                        'https://{}/rest/api/2/mypermissions?projectKey={}'.format(jiraSite, projectKey), \
                        '-H', 'Accept: application/json', '-o', 'mypermissions-{}.json'.format(idx)] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
    with open('mypermissions-{}.json'.format(idx), 'r', encoding='utf-8') as f:
        mypermissions = json.load(f)
        permissions = mypermissions['permissions']
        utils.heavyLogging('jiraMyPermissions: CREATE_ISSUE {}({})'.format(permissions['CREATE_ISSUE']['havePermission'], idx))
        utils.heavyLogging('jiraMyPermissions: EDIT_ISSUE {}({})'.format(permissions['EDIT_ISSUE']['havePermission'], idx))
        utils.heavyLogging('jiraMyPermissions: ASSIGN_ISSUE {}({})'.format(permissions['ASSIGN_ISSUE']['havePermission'], idx))
        if permissions['CREATE_ISSUE']['havePermission'] == False or \
            permissions['EDIT_ISSUE']['havePermission'] == False or \
            permissions['ASSIGN_ISSUE']['havePermission'] == False:
            utils.heavyLogging('jiraMyPermissions: permission denied')
            sys.exit(-1)

def jiraIsAdministrator(jiraSite, idOrKey):
    authPieces = getAuthPieces()
    myself = jiraMyself(jiraSite, 'myself-test.json')
    myName = myself['name']
    print('jiraIsAdministrator: query myself {}'.format(myName), flush=True)
    if myName == "INVALID":
        return False
    # query project role
    cmdCurl = sb.Popen(['curl', '-k', '-s', '-X', 'GET', '--url', \
                        'https://{}/rest/api/2/project/{}/role'.format(jiraSite, idOrKey), \
                        '-H', 'Content-Type: application/json', \
                        '-H', 'Accept: application/json', '--data', '@{}'.format(input), '-o', 'role.json'] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
    with open('role.json', 'r', encoding='utf-8') as f:
        role = json.load(f)
    if 'errorMessages' in role:
        print('jiraIsAdministrator: query project role failure', flush=True)
        return False
    for roleKey in role:
        if roleKey == 'Administrators':
            cmdCurl = sb.Popen(['curl', '-k', '-s', '-X', 'GET', '--url', \
                                role[roleKey], \
                                '-H', 'Content-Type: application/json', \
                                '-H', 'Accept: application/json', '--data', '@{}'.format(input), '-o', 'adminusers.json'] + authPieces, stdout=sb.PIPE)
            cmdCurl.wait()
            with open('adminusers.json', 'r', encoding='utf-8') as f:
                adminusers = json.load(f)
            if 'errorMessages' in adminusers:
                print('jiraIsAdministrator: query project role users failure', flush=True)
                return False
            for actor in adminusers['actors']:
                if actor['name'] == myName:
                    print('jiraIsAdministrator: {} is admin'.format(myName), flush=True)
                    return True

    return False

def jiraAssignIssue(jiraSite, idOrKey, input, output):
    authPieces = getAuthPieces()
    cmdCurl = sb.Popen(['curl', '-k', '-s', '-w', '%{http_code}', '-X', 'PUT', '--url', \
                        'https://{}/rest/api/2/issue/{}/assignee'.format(jiraSite, idOrKey), \
                        '-H', 'Content-Type: application/json', \
                        '-H', 'Accept: application/json', '--data', '@{}'.format(input), '-o', output] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
    utils.lightLogging('JIRA_rest_api:assign_issue')
    while True:
        http_code = cmdCurl.stdout.readline()
        http_code = bytes.decode(http_code, 'utf-8')
        break
    return http_code

def jiraValidateUser(jiraSite, userName):
    authPieces = getAuthPieces()
    cmdCurl = sb.Popen(['curl', '-k', '-s', '-X', 'GET', '--url', \
                        'https://{}/rest/api/2/user?username={}'.format(jiraSite, userName), \
                        '-H', 'Accept: application/json', '-o', 'validate-{}.json'.format(userName)] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()

def jiraTransitStatus(jiraSite, issueKey, newStatus, resolution, notifyUsers=True):
    checkJIRACredentials()
    authPieces = getAuthPieces()

    notifyParam = ''
    if notifyUsers == False:
        notifyParam = '?notifyUsers=false'

    cmdCurl = sb.Popen(['curl', '-k', '-s', '-X', 'GET', '--url', \
                        'https://{}/rest/api/2/issue/{}{}'.format(jiraSite, issueKey, notifyParam), \
                        '-H', 'Accept: application/json', '-o', 'issue.json'] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
    utils.lightLogging('JIRA_rest_api:get_issue_info')
    with open('issue.json', 'r', encoding='utf-8') as f:
        jiraIssue = json.load(f)
    jiraIssueStatus = jiraIssue['fields']['status']['name']
    if newStatus == "Close":
        if jiraIssueStatus.lower().startswith("close"):
            return
    elif newStatus == "Reopen":
        if jiraIssueStatus.lower().startswith("close") == False and jiraIssueStatus.lower().startswith("resolved") == False:
            return

    cmdCurl = sb.Popen(['curl', '-k', '-s', '-X', 'GET', '--url', \
                        'https://{}/rest/api/2/issue/{}/transitions'.format(jiraSite, issueKey), \
                        '-H', 'Accept: application/json', '-o', 'transitions.json'] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
    with open('transitions.json', 'r', encoding='utf-8') as f:
        transitions = json.load(f)
        transitions = transitions['transitions']
    resolveStatusId = 0
    for j in range(len(transitions)):
        transition = transitions[j]
        if transition['name'].startswith(newStatus) or (newStatus == "Close" and transition['name'] == "Won't fix"):
            resolveStatusId = transition['id']
            break

    if resolveStatusId == 0:
        utils.heavyLogging('jiraTransitStatus: cannot transit issue {} to {}(project workflow/permissions issue maybe)'.format(issueKey, newStatus))
        return
    transitionInput = dict()
    transitionInput['transition'] = dict()
    transitionInput['transition']['id'] = resolveStatusId
    # enumerate conditions not required to add resolution
    if resolution != '':
        if newStatus.lower() == 'close' and jiraIssueStatus.lower() == 'resolved':
            # resolution is meaningless if transit from resolved to close
            pass
        else:
            transitionInput['fields'] = dict()
            transitionInput['fields']['resolution'] = dict()
            transitionInput['fields']['resolution']['name'] = resolution
    with open('transition.json', 'w') as fp:
        json.dump(transitionInput, fp)
    cmdCurl = sb.Popen(['curl', '-k', '-s', '-w', '%{http_code}', '-X', 'POST', '--url', \
                        'https://{}/rest/api/2/issue/{}/transitions'.format(jiraSite, issueKey), \
                        '-H', 'Content-Type: application/json', \
                        '-H', 'Accept: application/json', '--data', '@transition.json'] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
    utils.lightLogging('JIRA_rest_api:do_transitions')
    while True:
        http_code = cmdCurl.stdout.readline()
        http_code = bytes.decode(http_code, 'utf-8')
        break
    if http_code == '204':
        utils.heavyLogging('jiraTransitStatus: {}, status id {}, resolution {}'.format(issueKey, resolveStatusId, resolution))
    else:
        del transitionInput['fields']
        with open('transition.json', 'w') as fp:
            json.dump(transitionInput, fp)
        utils.heavyLogging('jiraTransitStatus: {}, status id {}'.format(issueKey, resolveStatusId))
        cmdCurl = sb.Popen(['curl', '-k', '-s', '-w', '%{http_code}', '-X', 'POST', '--url', \
                            'https://{}/rest/api/2/issue/{}/transitions'.format(jiraSite, issueKey), \
                            '-H', 'Content-Type: application/json', \
                            '-H', 'Accept: application/json', '--data', '@transition.json'] + authPieces, stdout=sb.PIPE)
        cmdCurl.wait()
        utils.lightLogging('JIRA_rest_api:do_transitions')

def jiraGeneralURLQuery(url, output):
    checkJIRACredentials()
    authPieces = getAuthPieces()
    cmdPieces = ['curl', '-k', '-s', '--url', url, \
                    '-H', 'Accept: application/json', '-o', output] + authPieces
    cmdCurl = sb.Popen(cmdPieces, stdout=sb.PIPE)
    cmdCurl.wait()

def getKeyFields(jiraSite, extraFields):
    checkJIRACredentials()
    authPieces = getAuthPieces()
    cmdCurl = sb.Popen(['curl', '-k', '-X', 'GET', '--url', \
                        'https://{}/rest/api/2/field'.format(jiraSite), \
                        '-H', 'Accept: application/json', '-o', 'fields.json'] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()

    with open('fields.json', 'rb') as f:
        fields = json.load(f)
    siteFieldsIdMap = dict()
    siteFieldsSchemaMap = dict()
    for field in fields:
        if field['name'] == 'Epic Link':
            with open("epicLinkField.json", "w") as outfile:
                json.dump(field, outfile)
        elif field['name'] == 'Epic Name':
            with open("epicNameField.json", "w") as outfile:
                json.dump(field, outfile)
        if field['custom'] == True:
            siteFieldsIdMap[field['name']] = field['id']
            # supported schema: array, option, string
            siteFieldsSchemaMap[field['name']] = field['schema']['type']

    extraFieldsMap = dict()
    # skip empty extraFields
    if extraFields != '':
        extraFields = json.loads(extraFields)
        for paramKey in extraFields:
            extraFields[paramKey] = utils.extractScriptedParameter(extraFields[paramKey], "params-extrafields-{}".format(paramKey))

        for fieldName in extraFields:
            if fieldName in siteFieldsIdMap:
                extraFieldsMap[fieldName] = dict()
                extraFieldsMap[fieldName]['id'] = siteFieldsIdMap[fieldName]
                if siteFieldsSchemaMap[fieldName] == 'array':
                    extraFieldsMap[fieldName]['value'] = []
                    values = extraFields[fieldName].split(',')
                    for value in values:
                        option = dict()
                        option['value'] = value.strip()
                        extraFieldsMap[fieldName]['value'].append(option)
                elif siteFieldsSchemaMap[fieldName] == "option":
                    option = dict()
                    option['value'] = extraFields[fieldName]
                    extraFieldsMap[fieldName]['value'] = option
                else:
                    extraFieldsMap[fieldName]['value'] = extraFields[fieldName]

    with open('extraFieldsMap.json', 'w') as outfile:
        json.dump(extraFieldsMap, outfile)

def getEPICKey(jiraSite, jiraProject, jiraEPIC, autoCreate=True):
    if autoCreate == False:
        # EPIC not supported in jiraProject
        issueTypes = jiraProjectIssueTypes(jiraSite, jiraProject)
        if 'Epic' not in issueTypes or os.path.isfile('epicNameField.json') == False:
            print('getEPICKey: EPIC not supported in {}'.format(jiraProject), flush=True)
            dummyObj = dict()
            dummyObj['total'] = 0
            with open('epic.json', "w") as outfile:
                json.dump(dummyObj, outfile)
            return
    # EPIC with summary ${jiraEPIC} not existed in jiraProject
    epicKey = dict()
    jiraEPICEscape = jiraEPIC.replace('[', '')
    jiraEPICEscape = jiraEPICEscape.replace(']', '')
    jqlCommand = "project={} and issuetype='EPIC' and summary ~ '{}'".format(jiraProject, jiraEPICEscape)
    jiraJQLSearch(jiraSite, jqlCommand, 0, 100, 'epic.json')
    with open('epic.json', 'r', encoding='utf-8') as f:
        epicInfo = json.load(f)
    # epic not existed, try to create
    if epicInfo['total'] == 0 and autoCreate == True:
        with open('epicNameField.json', 'r', encoding='utf-8') as f:
            epicNameFieldId = json.load(f)
        epicNameFieldId = epicNameFieldId["id"]
        logging.debug('getEPICKey: epicNameFieldId {}'.format(epicNameFieldId))
        jiraIssue = dict()
        jiraIssue['fields'] = dict()
        jiraIssue['fields']['project'] = dict()
        jiraIssue['fields']['project']['key'] = jiraProject
        jiraIssue['fields']['summary'] = jiraEPIC
        jiraIssue['fields']['description'] = jiraEPIC
        jiraIssue['fields'][epicNameFieldId] = jiraEPIC
        jiraIssue['fields']['issuetype'] = dict()
        jiraIssue['fields']['issuetype']['name'] = 'Epic'
        utils.heavyLogging('getEPICKey: to create new EPIC')
        utils.lightLogging(jiraIssue)
        # fill user-defined fields
        if os.path.isfile('extraFieldsMap.json'):
            with open('extraFieldsMap.json', 'r', encoding='utf-8') as f:
                userDefinedFields = json.load(f)
            for fieldsMapKey in userDefinedFields:
                jiraIssue['fields'][userDefinedFields[fieldsMapKey]['id']] = userDefinedFields[fieldsMapKey]['value']
        with open("newEpic.json", "w") as outfile:
            json.dump(jiraIssue, outfile)
        jiraCreateIssue(jiraSite, 'newEpic.json', 'epic.json')
        # {'id': '25920', 'key': 'CTCTESTCOV-380', 'self': 'https://jiraqa.realtek.com/rest/api/2/issue/25920'}
        # {'errorMessages': [], 'errors': {'QQ': "Field 'QQ' cannot be set. It is not on the appropriate screen, or unknown."}}
        with open('epic.json', 'r', encoding='utf-8') as f:
            newEpicOutput = json.load(f)
        if 'errors' in newEpicOutput:
            unnecessaryFields = []
            # check fields cannot be set
            for key in newEpicOutput['errors']:
                if newEpicOutput['errors'][key].endswith("It is not on the appropriate screen, or unknown."):
                    unnecessaryFields.append(key)
                    del jiraIssue['fields'][key]
            if len(unnecessaryFields) > 0:
                with open("newEpic.json", "w") as outfile:
                    json.dump(jiraIssue, outfile)
                jiraCreateIssue(jiraSite, 'newEpic.json', 'epic.json')
        else:
            pass
        with open('epic.json', 'r', encoding='utf-8') as f:
            newEpicOutput = json.load(f)
        epicKey['id'] = '0'
        epicKey['key'] = '0'
        if 'id' in newEpicOutput:
            epicKey['id'] = newEpicOutput['id']
        if 'key' in newEpicOutput:
            epicKey['key'] = newEpicOutput['key']
        utils.heavyLogging('getEPICKey: new EPIC key {}'.format(epicKey['key']))
    elif epicInfo['total'] > 0:
        foundEPIC = False
        for i in range(len(epicInfo['issues'])):
            if epicInfo['issues'][i]['fields']['summary'] == jiraEPIC:
                epicKey['id'] = epicInfo['issues'][i]['id']
                epicKey['key'] = epicInfo['issues'][i]['key']
                utils.heavyLogging('getEPICKey: existed EPIC key {}'.format(epicKey['key']))
                foundEPIC = True
        if foundEPIC == False:
            utils.heavyLogging('getEPICKey: invalid EPIC, {}'.format(jiraEPIC))
            sys.exit(-1)
    with open("epicKey.json", "w") as outfile:
        json.dump(epicKey, outfile)

def createIssue(inputFile):
    checkJIRACredentials()
    output = os.path.join(workDir, '.createIssue.json')
    jiraCreateIssue(os.getenv('JIRA_SITE'), inputFile, output)
    with open(output, 'r', encoding='utf-8') as f:
        createIssue = json.load(f)
    if "errorMessages" not in createIssue:
        utils.heavyLogging('createIssue: create issue {}'.format(createIssue['key']))
        return createIssue['key']
    else:
        utils.heavyLogging('createIssue: create issue failed {}'.format(createIssue['errors']))
        return 'ERROR'

def getComments(inputFile, outputFile):
    checkJIRACredentials()
    with open(inputFile, 'r', encoding='utf-8') as f:
        issue = json.load(f)
    if 'key' not in issue:
        logging.debug('getComments: invalid input {}'.format(inputFile))
        return
    retCode = jiraGetComments(os.getenv('JIRA_SITE'), issue['key'], outputFile)
    logging.debug('getComments: code {}'.format(retCode))

def addComment(inputFile, commentId):
    checkJIRACredentials()
    with open(inputFile, 'r', encoding='utf-8') as f:
        issue = json.load(f)
    if 'key' not in issue:
        logging.debug('addComment: invalid input {}'.format(inputFile))
        return
    if commentId == '0':
        retCode = jiraAddComments(os.getenv('JIRA_SITE'), issue['key'], inputFile)
    else:
        retCode = jiraUpdateComments(os.getenv('JIRA_SITE'), issue['key'], commentId, inputFile)
    logging.debug('addComment: code {}({})'.format(retCode, commentId))
    if retCode.endswith('201') == False and retCode.endswith('200') == False:
        sys.exit(retCode)

def updateIssue(inputFile):
    checkJIRACredentials()
    with open(inputFile, 'r', encoding='utf-8') as f:
        issue = json.load(f)
    if 'key' not in issue:
        logging.debug('updateIssue: invalid input {}'.format(inputFile))
    retCode = jiraUpdateIssue(os.getenv('JIRA_SITE'), issue['key'], inputFile)
    logging.debug('updateIssue: code {}'.format(retCode))

def addWatcher(inputFile):
    checkJIRACredentials()
    with open(inputFile, 'r', encoding='utf-8') as f:
        inputInfo = json.load(f)
    if 'key' not in inputInfo or 'userId' not in inputInfo:
        logging.debug('addWatcher: invalid input {}'.format(inputFile))
    users = inputInfo['userId'].split(',')
    for user in users:
        print(user)
        retCode = jiraAddWatcher(os.getenv('JIRA_SITE'), inputInfo['key'], user)
        logging.debug('addWatcher: code {}'.format(retCode))

def assignIssue(inputFile):
    checkJIRACredentials()
    with open(inputFile, 'r', encoding='utf-8') as f:
        issue = json.load(f)
    if 'key' not in issue:
        logging.debug('updateIssue: invalid input {}'.format(inputFile))
    retCode = jiraAssignIssue(os.getenv('JIRA_SITE'), issue['key'], inputFile, '.assignIssue.json')
    logging.debug('assignIssue: code {}'.format(retCode))

def uploadAttachment(inputFile):
    checkJIRACredentials()
    with open(inputFile, 'r', encoding='utf-8') as f:
        params = json.load(f)
    if not os.path.isfile(params['attach']):
        logging.debug('uploadAttachment: invalid file {}'.format(params['attach']))
    jiraUploadAttachment(os.getenv('JIRA_SITE'), params['key'], params['attach'])

def queryIssues(jiraSite, jqlCommand, ouputFile):
    outputDir = os.path.dirname(ouputFile)
    outputBase = os.path.basename(ouputFile)
    outputTmp = os.path.join(outputDir, 't_{}'.format(outputBase))
    issues = []
    for i in range(100):
        jiraJQLSearch(jiraSite, jqlCommand, i*1000, 1000, outputTmp)
        with open(outputTmp, 'r', encoding='utf-8') as f:
            ret = json.load(f)
        issues = issues + ret['issues']
        if len(ret['issues']) < 1000:
            break
    with open(ouputFile, 'w') as outfile:
        json.dump(issues, outfile)

def queryProjectIssues(inputFile):
    checkJIRACredentials()
    with open(inputFile, 'r', encoding='utf-8') as f:
        params = json.load(f)
    jqlCommand = "project={} and issuetype='{}'".format(params['project'], params['issuetype'])
    if 'labels' in params:
        for label in params['labels']:
            jqlCommand = jqlCommand + ' and labels=\'{}\''.format(label)
    queryIssues(os.getenv('JIRA_SITE'), jqlCommand, 'issues.json')

def coverityCheckToJIRA(configs, commentYaml, filename=''):
    global workDir
    tempCreateIssue = os.path.join(workDir, 'coverityCheckToJIRA_create.json')
    tempUpdateIssue = os.path.join(workDir, 'coverityCheckToJIRA_update.json')
    tempCommentIssue = os.path.join(workDir, 'coverityCheckToJIRA_comment.json')
    tempAssignIssue = os.path.join(workDir, 'coverityCheckToJIRA_assignee.json')
    #utils.heavyLogging('coverityCheckToJIRA: {}'.format(commentYaml['analysis']))
    #utils.heavyLogging('coverityCheckToJIRA: {}'.format(commentYaml['final_patch']))
    with open(os.path.join(os.getenv('PF_ROOT'), 'templates', 'git-commit-coverity-check-JIRA'), 'r') as fpTemplate:
        tJIRA = fpTemplate.read()
    with open(os.path.join(os.getenv('PF_ROOT'), 'templates', 'git-commit-coverity-check-JIRA-patch'), 'r') as fpTemplate:
        tJIRAPatch = fpTemplate.read()
    allPatches = ''
    if 'exception' in commentYaml:
        allPatches = 'RealGPT exception: {}'.format(commentYaml['exception'])
    else:
        if 'final_patch' in commentYaml:
            patchKey = 'final_patch'
            contentKey = 'diff'
        else:
            patchKey = 'corrected_file'
            contentKey = 'content'
        utils.heavyLogging('coverityCheckToJIRA: patchKey {}, contentKey {}'.format(patchKey, contentKey))
        if type(commentYaml[patchKey]) is list:
            for patch in commentYaml[patchKey]:
                allPatches = allPatches + Template(tJIRAPatch).safe_substitute(FILE=patch['file'], \
                                                                    REFINED_PATCH=patch[contentKey].replace('\\n', '\\\\ '))
        else:
            if 'note' in commentYaml[patchKey]:
                allPatches = Template(tJIRAPatch).safe_substitute(FILE='', \
                                                                    REFINED_PATCH=commentYaml[patchKey]['note'])
            else:
                allPatches = Template(tJIRAPatch).safe_substitute(FILE=commentYaml[patchKey]['file'], \
                                                                    REFINED_PATCH=commentYaml[patchKey][contentKey].replace('\\n', '\\\\ '))
    issueDescription = Template(tJIRA).safe_substitute(GERRIT_URL=os.getenv('GERRIT_CHANGE_URL'), \
                                                  BUILD_URL=os.getenv('BUILD_URL'),
                                                  PATCHES=allPatches)
    issueKey = None
    # query exist JIRA issues
    if filename == '':
        summary = 'git-commit-coverity-check: {}, change {}'.format(os.getenv('GERRIT_PROJECT'), os.getenv('GERRIT_CHANGE_NUMBER'))
    else:
        summary = 'git-commit-coverity-check: {}, change {}, file {}'.format(os.getenv('GERRIT_PROJECT'), os.getenv('GERRIT_CHANGE_NUMBER'), filename)
    jqlCommand = "project={} and issuetype='{}' and summary ~ '{}'".format(configs['jira_project'], \
                                                                            configs['defects_issue_type'], \
                                                                            summary)
    queryIssues(os.getenv('JIRA_SITE'), jqlCommand, os.path.join(workDir, 'issues.json'))
    with open(os.path.join(workDir, 'issues.json'), 'r', encoding='utf-8') as f:
        existedIssues = json.load(f)
    if len(existedIssues) > 0:
        # update JIRA issue
        jsonInput = dict()
        jsonInput['key'] = existedIssues[0]['key']
        utils.heavyLogging('coverityCheckToJIRA: update JIRA issue {}'.format(jsonInput['key']))
        jsonInput['fields'] = dict()
        jsonInput['fields']['description'] = issueDescription
        with open(tempUpdateIssue, 'w') as outfile:
            json.dump(jsonInput, outfile)
        updateIssue(tempUpdateIssue)
        issueKey = existedIssues[0]['key']
    else:
        # create JIRA issue
        jsonInput = dict()
        jsonInput['fields'] = dict()
        jsonInput['fields']['summary'] = summary
        jsonInput['fields']['description'] = issueDescription
        jsonInput['fields']['project'] = dict()
        jsonInput['fields']['project']['key'] = configs['jira_project']
        jsonInput['fields']['issuetype'] = dict()
        jsonInput['fields']['issuetype']['name'] = configs['defects_issue_type']
        with open(tempCreateIssue, 'w') as outfile:
            json.dump(jsonInput, outfile)
        retCreateIssue = createIssue(tempCreateIssue)
        if retCreateIssue != 'ERROR':
            # assign JIRA issue to uploader
            jsonInput = dict()
            jsonInput['key'] = retCreateIssue
            jsonInput['name'] = os.getenv('GERRIT_PATCHSET_UPLOADER_EMAIL')[:os.getenv('GERRIT_PATCHSET_UPLOADER_EMAIL').index('@')]
            with open(tempAssignIssue, 'w') as outfile:
                json.dump(jsonInput, outfile)
            assignIssue(tempAssignIssue)
            issueKey = retCreateIssue
    if issueKey is not None and 'analysis' in commentYaml:
        # add GPT analysis comment
        jsonInput = dict()
        jsonInput['key'] = issueKey
        import yaml
        jsonInput['body'] = yaml.dump(commentYaml['analysis'], default_flow_style=False)
        jsonInput['body'] = jsonInput['body'].replace('\\n', '\\\\ ')
        with open(tempCommentIssue, 'w') as outfile:
            json.dump(jsonInput, outfile)
        addComment(tempCommentIssue, '0')

def commitReviewToJIRA(configs, commentYaml):
    global workDir
    tempCreateIssue = os.path.join(workDir, 'coverityCheckToJIRA_create.json')
    tempUpdateIssue = os.path.join(workDir, 'coverityCheckToJIRA_update.json')
    tempCommentIssue = os.path.join(workDir, 'coverityCheckToJIRA_comment.json')
    tempAssignIssue = os.path.join(workDir, 'coverityCheckToJIRA_assignee.json')
    #utils.heavyLogging('coverityCheckToJIRA: {}'.format(commentYaml['analysis']))
    #utils.heavyLogging('coverityCheckToJIRA: {}'.format(commentYaml['final_patch']))
    with open(os.path.join(os.getenv('PF_ROOT'), 'templates', 'git-commit-coverity-check-JIRA'), 'r') as fpTemplate:
        tJIRA = fpTemplate.read()
    with open(os.path.join(os.getenv('PF_ROOT'), 'templates', 'git-commit-coverity-check-JIRA-patch'), 'r') as fpTemplate:
        tJIRAPatch = fpTemplate.read()
    allPatches = ''
    if 'exception' in commentYaml:
        allPatches = 'RealGPT exception: {}'.format(commentYaml['exception'])
    else:
        perFileReviews = commentYaml['patches']['refined_patches']
        for key in perFileReviews:
            allPatches = allPatches + Template(tJIRAPatch).safe_substitute(FILE=key, \
                                                            REFINED_PATCH=perFileReviews[key].replace('\\n', '\\\\ '))
    issueDescription = Template(tJIRA).safe_substitute(GERRIT_URL=os.getenv('GERRIT_CHANGE_URL'), \
                                                  BUILD_URL=os.getenv('BUILD_URL'),
                                                  PATCHES=allPatches)
    issueKey = None
    # query exist JIRA issues
    summary = 'git-commit-message-review: {}, change {}'.format(os.getenv('GERRIT_PROJECT'), os.getenv('GERRIT_CHANGE_NUMBER'))
    jqlCommand = "project={} and issuetype='{}' and summary ~ '{}'".format(configs['jira_project'], \
                                                                            configs['defects_issue_type'], \
                                                                            summary)
    queryIssues(os.getenv('JIRA_SITE'), jqlCommand, os.path.join(workDir, 'issues.json'))
    with open(os.path.join(workDir, 'issues.json'), 'r', encoding='utf-8') as f:
        existedIssues = json.load(f)
    if len(existedIssues) > 0:
        # update JIRA issue
        jsonInput = dict()
        jsonInput['key'] = existedIssues[0]['key']
        utils.heavyLogging('commitReviewToJIRA: update JIRA issue {}'.format(jsonInput['key']))
        jsonInput['fields'] = dict()
        jsonInput['fields']['description'] = issueDescription
        with open(tempUpdateIssue, 'w') as outfile:
            json.dump(jsonInput, outfile)
        updateIssue(tempUpdateIssue)
        issueKey = existedIssues[0]['key']
    else:
        # create JIRA issue
        jsonInput = dict()
        jsonInput['fields'] = dict()
        jsonInput['fields']['summary'] = summary
        jsonInput['fields']['description'] = issueDescription
        jsonInput['fields']['project'] = dict()
        jsonInput['fields']['project']['key'] = configs['jira_project']
        jsonInput['fields']['issuetype'] = dict()
        jsonInput['fields']['issuetype']['name'] = configs['defects_issue_type']
        with open(tempCreateIssue, 'w') as outfile:
            json.dump(jsonInput, outfile)
        retCreateIssue = createIssue(tempCreateIssue)
        if retCreateIssue != 'ERROR':
            # assign JIRA issue to uploader
            jsonInput = dict()
            jsonInput['key'] = retCreateIssue
            jsonInput['name'] = os.getenv('GERRIT_PATCHSET_UPLOADER_EMAIL')[:os.getenv('GERRIT_PATCHSET_UPLOADER_EMAIL').index('@')]
            with open(tempAssignIssue, 'w') as outfile:
                json.dump(jsonInput, outfile)
            assignIssue(tempAssignIssue)
            issueKey = retCreateIssue
    if issueKey is not None:
        # add GPT analysis comment
        jsonInput = dict()
        jsonInput['key'] = issueKey
        import yaml
        jsonInput['body'] = yaml.dump(commentYaml['patches']['overall_review'], default_flow_style=False)
        jsonInput['body'] = jsonInput['body'].replace('\\n', '\\\\ ')
        with open(tempCommentIssue, 'w') as outfile:
            json.dump(jsonInput, outfile)
        addComment(tempCommentIssue, '0')

def buildResultToJIRA(configs):
    global workDir

    if 'PF_CODEPROMPT_RESULT' in os.environ and os.getenv('PF_CODEPROMPT_RESULT') != 'PF_NONE':
        if os.path.isfile('gerritENV'):
            with open('gerritENV') as fpEnv:
                while True:
                    line = fpEnv.readline()
                    if not line:
                        break
                    if line.strip() != '':
                        tokens = line.split('=')
                        os.environ[tokens[0]] = tokens[1].strip()
                        utils.heavyLogging('buildResultToJIRA: export {}={}'.format(tokens[0], os.environ[tokens[0]]))
        if 'PF_CODEPROMPT_FUNCTION' not in os.environ:
            utils.heavyLogging('buildResultToJIRA: unknown PF_CODEPROMPT_FUNCTION')
            sys.exit(-1)
        # results = .pf-codeprompt-cov/result-0,.pf-codeprompt-cov/result-1,.pf-codeprompt-cov/result-2...
        inputFiles = utils.getCodetekPrompts(os.getenv('PF_CODEPROMPT_RESULT'))
        for inputfile in inputFiles:
            import yaml
            with open(inputfile) as fpYaml:
                outputYaml = yaml.safe_load(fpYaml)
            if os.getenv('PF_CODEPROMPT_FUNCTION') == 'git-commit-coverity-check':
                coverityCheckToJIRA(configs, outputYaml)
            elif os.getenv('PF_CODEPROMPT_FUNCTION') == 'git-commit-coverity-check-indiv':
                coverityCheckToJIRA(configs, outputYaml, outputYaml['corrected_file']['file'])
            elif os.getenv('PF_CODEPROMPT_FUNCTION') == 'git-commit-message-review':
                commitReviewToJIRA(configs, outputYaml)

    if configs['jira_issue_summary'] != '' or configs['jira_issue_description'] != '':
        jsonInput = dict()
        jsonInput['fields'] = dict()
        if configs['jira_issue_summary'] != '':
            jsonInput['fields']['summary'] = configs['jira_issue_summary']
        if configs['jira_issue_description'] != '':
            jsonInput['fields']['description'] = configs['jira_issue_description']
        if configs['jira_operation'] == 'CREATE':
            jsonInput['fields']['project'] = dict()
            jsonInput['fields']['project']['key'] = configs['jira_project']
            jsonInput['fields']['issuetype'] = dict()
            jsonInput['fields']['issuetype']['name'] = configs['jira_issue_type']
            with open(os.path.join(workDir, 'buildResultToJIRA_create.json'), 'w') as outfile:
                json.dump(jsonInput, outfile)
            retCreateIssue = createIssue(os.path.join(workDir, 'buildResultToJIRA_create.json'))
            if retCreateIssue != 'ERROR':
                jsonInput = dict()
                jsonInput["key"] = retCreateIssue
                jsonInput["name"] = configs['jira_issue_assignee']
                with open(os.path.join(workDir, 'buildResultToJIRA_assignee.json'), 'w') as outfile:
                    json.dump(jsonInput, outfile)
                assignIssue(os.path.join(workDir, 'buildResultToJIRA_assignee.json'))
        elif configs['jira_operation'] == 'UPDATE':
            jsonInput['key'] = configs['jira_issue_key']
            with open(os.path.join(workDir, 'buildResultToJIRA_update.json'), 'w') as outfile:
                json.dump(jsonInput, outfile)
            updateIssue(os.path.join(workDir, 'buildResultToJIRA_update.json'))
    else:
        utils.heavyLogging('buildResultToJIRA: empy jira_issue_summary, jira_issue_description')
    if configs['jira_issue_comment'] != '':
        commentId = '0'
        jsonInput = dict()
        jsonInput['key'] = configs['jira_issue_key']
        with open(os.path.join(workDir, 'buildResultToJIRA_comment.json'), 'w') as outfile:
            json.dump(jsonInput, outfile)
        if configs['jira_issue_comment_mode'].startswith('UPDATE:'):
            keyword = configs['jira_issue_comment_mode'][configs['jira_issue_comment_mode'].index(':')+1:]
            getComments(os.path.join(workDir, 'buildResultToJIRA_comment.json'), os.path.join(workDir, 'buildResultToJIRA_comments.json'))
            try:
                if os.path.isfile(os.path.join(workDir, 'buildResultToJIRA_comments.json')):
                    with open(os.path.join(workDir, 'buildResultToJIRA_comments.json'), 'r', encoding='utf-8') as fpComments:
                        jsonComments = json.load(fpComments)
                    for comment in jsonComments['comments']:
                        body = comment['body']
                        if body.startswith(keyword):
                            commentId = comment['id']
            except:
                utils.heavyLogging('buildResultToJIRA: cannot get comment from JIRA issue {}'.format(jsonInput['key']))
        jsonInput['body'] = configs['jira_issue_comment']
        with open(os.path.join(workDir, 'buildResultToJIRA_comment.json'), 'w') as outfile:
            json.dump(jsonInput, outfile)
        addComment(os.path.join(workDir, 'buildResultToJIRA_comment.json'), commentId)
    else:
        utils.heavyLogging('buildResultToJIRA: empy jira_issue_comment')

def copyRemoteArtifacts(targetDir):
    global workDir
    if 'PF_CODEPROMPT_RESULT' in os.environ:
        artifacts = utils.getCodetekPrompts(os.getenv('PF_CODEPROMPT_RESULT'))
        utils.heavyLogging('copyRemoteArtifacts: copy {}'.format(artifacts))
        for artifact in artifacts:
            if os.path.isfile(artifact):
                # local file
                utils.heavyLogging('copyRemoteArtifacts: skip local file {}'.format(artifact))
                continue
            cmdPieces = ['curl', '-k', '-s', '-w', '%{http_code}', '-X', 'GET', '-u', '{}:{}'.format(os.getenv('SDJENKINS_USER'), os.getenv('SDJENKINS_TOKEN')), \
                        '--url', '{}artifact/{}'.format(os.getenv('SDJENKINS_URL'), artifact), \
                        '-o', '{}/{}'.format(targetDir, artifact)]
            dirname = os.path.dirname(artifact)
            if dirname != '':
                os.makedirs(dirname, exist_ok=True)
            utils.heavyLogging('copyRemoteArtifacts: cmd {}'.format(cmdPieces))
            cmdCurl = sb.Popen(cmdPieces, stdout=sb.PIPE)
            cmdCurl.wait()
            while True:
                http_code = cmdCurl.stdout.readline()
                http_code = bytes.decode(http_code, 'utf-8')
                break
            if http_code == '200':
                utils.heavyLogging('copyRemoteArtifacts: got {}/{}'.format(targetDir, artifact))
            else:
                utils.heavyLogging('copyRemoteArtifacts: error({}) {}/{}'.format(http_code, targetDir, artifact))
    if 'DECRYPT_KEY' in os.environ:
        cmdCurl = sb.Popen(['curl', '-k', '-s', '-X', 'GET', '-u', '{}:{}'.format(os.getenv('SDJENKINS_USER'), os.getenv('SDJENKINS_TOKEN')), \
                        '--url', '{}artifact/encryptToken'.format(os.getenv('SDJENKINS_URL')), \
                        '-o', '{}/encryptToken'.format(targetDir)], stdout=sb.PIPE)
        cmdCurl.wait()
        from Crypto.PublicKey import RSA
        from Crypto.Cipher import PKCS1_OAEP
        privateKey = RSA.import_key(open(os.getenv('DECRYPT_KEY')).read())
        cipherRSA = PKCS1_OAEP.new(privateKey)
        plainToken = cipherRSA.decrypt(open('{}/encryptToken'.format(targetDir), 'rb').read())
        plainToken = bytes.decode(plainToken, 'utf-8')
        with open(os.path.join(workDir, 'env'), 'w') as fp:
            fp.write('JIRA_TOKEN={}\n'.format(plainToken))
    # copy gerritENV if available
    try:
        cmdCurl = sb.Popen(['curl', '-k', '-s', '-X', 'GET', '-u', '{}:{}'.format(os.getenv('SDJENKINS_USER'), os.getenv('SDJENKINS_TOKEN')), \
                        '--url', '{}artifact/gerritENV'.format(os.getenv('SDJENKINS_URL')), \
                        '-o', '{}/gerritENV'.format(targetDir)], stdout=sb.PIPE)
        cmdCurl.wait()
        utils.heavyLogging('copyRemoteArtifacts: copy gerritENV')
    except:
        utils.heavyLogging('copyRemoteArtifacts: gerritENV not available')

def main(argv):
    try:
        opts, args = getopt.getopt(argv[1:], 'i:w:d:f:c:v', ["input=", "work_dir=", "defects_dir=", "config=", "command=", "version"])
    except getopt.GetoptError:
        print('Invalid options')
        sys.exit()

    global workDir
    command = ''
    inputFile = ''
    configFile = ''
    defectsDir = '.'
    workDir = os.getcwd()
    for name, value in opts:
        if name in ('-v', '--version'):
            print("0.1")
            sys.exit(0)
        elif name in ('-c', '--command'):
            # override if --user
            command = value
        elif name in ('-i', '--input'):
            inputFile = os.path.abspath(value)
        elif name in ('-f', '--config'):
            configFile = value
            utils.translateConfig(configFile)
            configs = utils.loadConfigs(configFile)
        elif name in ('-d', '--defects_dir'):
            defectsDir = os.path.abspath(value)
        elif name in ('-w', '--work_dir'):
            if os.path.exists(value) == False:
                os.mkdir(value)
            workDir = value

    if os.path.isdir(workDir) == False:
        os.makedirs(workDir)
    logging.basicConfig(filename=os.path.join(workDir, 'jira.log'), level=logging.DEBUG, filemode='w')
    if inputFile == '' and configFile == '':
        sys.exit('Invalid input')
    utils.checkLicense(os.path.dirname(sys.argv[0]), configs, 'jira')
    if command == 'BUILD_TO_JIRA':
        buildResultToJIRA(configs)
        sys.exit(0)
    elif command == "COPY_REMOTE_ARTIFACTS":
        copyRemoteArtifacts(defectsDir)
        sys.exit(0)
    elif command == "CREATE_ISSUE":
        createIssue(inputFile)
        sys.exit(0)
    elif command == "UPDATE_ISSUE":
        updateIssue(inputFile)
        sys.exit(0)
    elif command == "ADD_WATCHER":
        addWatcher(inputFile)
        sys.exit(0)
    elif command == "ASSIGN_ISSUE":
        assignIssue(inputFile)
        sys.exit(0)
    elif command == "UPLOAD_ATTACH":
        uploadAttachment(inputFile)
        sys.exit(0)
    elif command == "QUERY_ISSUES":
        queryProjectIssues(inputFile)
        sys.exit(0)
    else:
        print('Invalid command {}'.format(command))

if __name__ == "__main__":
    main(sys.argv)