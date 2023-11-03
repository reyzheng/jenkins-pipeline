import os, logging
import getopt, sys
import json
import urllib.parse
import subprocess as sb
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

def jiraGetProjectKey(jiraSite, projectKey):
    checkJIRACredentials()
    authPieces = getAuthPieces()
    utils.heavyLogging('jiraGetProjectKey: check project key {}'.format(projectKey))
    cmdCurl = sb.Popen(['curl', '-s', '-w', '%{http_code}', '-X', 'GET', '--url', \
                        'https://{}/rest/api/2/project/{}'.format(jiraSite, projectKey), \
                        '-H', 'Accept: application/json', '-o', 'getProject.json'] + authPieces, stdout=sb.PIPE)
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
        cmdCurl = sb.Popen(['curl', '-s', '-X', 'GET', '--url', \
                            'https://{}/rest/api/2/project'.format(jiraSite), \
                            '-H', 'Accept: application/json', '-o', 'allProjects.json'] + authPieces, stdout=sb.PIPE)
        cmdCurl.wait()
        with open('allProjects.json') as f:
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
    cmdCurl = sb.Popen(['curl', '-s', '-X', 'GET', '--url', \
                        'https://{}/rest/api/2/search?jql={}&startAt={}&maxResults={}'.format(jiraSite, urllib.parse.quote(jql), startAt, maxResults), \
                        '-H', 'Accept: application/json', '-o', output] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
    utils.lightLogging('jiraJQLSearch: jql {}'.format(jql))
    utils.lightLogging('jiraJQLSearch: jql encode {}'.format(urllib.parse.quote(jql)))

def jiraProjectIssueTypes(jiraSite, projectKey):
    checkJIRACredentials()
    authPieces = getAuthPieces()
    cmdCurl = sb.Popen(['curl', '-s', '-X', 'GET', '--url', \
                        'https://{}/rest/api/2/project/{}'.format(jiraSite, projectKey), \
                        '-H', 'Accept: application/json', '-o', 'projectInfo.json'] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
    ret = []
    with open('projectInfo.json') as f:
        projectInfo = json.load(f)
    if 'issueTypes' in projectInfo:
        for issueType in projectInfo['issueTypes']:
            ret.append(issueType['name'])
    utils.heavyLogging('jiraProjectIssueTypes: {}'.format(ret))
    return ret

def jiraCreateIssue(jiraSite, input, output):
    checkJIRACredentials()
    authPieces = getAuthPieces()
    cmdCurl = sb.Popen(['curl', '-s', '-w', '%{http_code}', '-X', 'POST', '--url', \
                        'https://{}/rest/api/2/issue'.format(jiraSite), \
                        '-H', 'Content-Type: application/json', \
                        '-H', 'Accept: application/json', '--data', '@{}'.format(input), '-o', output] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
    while True:
        http_code = cmdCurl.stdout.readline()
        http_code = bytes.decode(http_code, 'utf-8')
        break

    return http_code

def jiraUpdateIssue(jiraSite, idOrKey, input):
    checkJIRACredentials()
    authPieces = getAuthPieces()
    cmdCurl = sb.Popen(['curl', '-s', '-w', '%{http_code}', '-X', 'PUT', '--url', \
                        'https://{}/rest/api/2/issue/{}'.format(jiraSite, idOrKey), \
                        '-H', 'Content-Type: application/json', \
                        '-H', 'Accept: application/json', '--data', '@{}'.format(input)] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
    while True:
        http_code = cmdCurl.stdout.readline()
        http_code = bytes.decode(http_code, 'utf-8')
        break

    return http_code

def jiraAddComments(jiraSite, idOrKey, input):
    checkJIRACredentials()
    authPieces = getAuthPieces()
    cmdCurl = sb.Popen(['curl', '-s', '-w', '%{http_code}', '-X', 'POST', '--url', \
                        'https://{}/rest/api/2/issue/{}/comment'.format(jiraSite, idOrKey), \
                        '-H', 'Content-Type: application/json', \
                        '-H', 'Accept: application/json', '--data', '@{}'.format(input)] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
    while True:
        http_code = cmdCurl.stdout.readline()
        http_code = bytes.decode(http_code, 'utf-8')
        break
    
    return http_code

def jiraAddWatcher(jiraSite, idOrKey, userId):
    checkJIRACredentials()
    authPieces = getAuthPieces()
    cmdCurl = sb.Popen(['curl', '-s', '-w', '%{http_code}', '-X', 'POST', '--url', \
                        'https://{}/rest/api/2/issue/{}/watchers'.format(jiraSite, idOrKey), \
                        '-H', 'Content-Type: application/json', \
                        '-H', 'Accept: application/json', '--data', '"{}"'.format(userId)] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
    while True:
        http_code = cmdCurl.stdout.readline()
        http_code = bytes.decode(http_code, 'utf-8')
        break
    return http_code

def jiraUploadAttachment(jiraSite, idOrKey, filename):
    authPieces = getAuthPieces()
    cmdCurl = sb.Popen(['curl', '-s', '-X', 'POST', '--url', \
                        'https://{}/rest/api/2/issue/{}/attachments'.format(jiraSite, idOrKey), \
                        '-H', 'X-Atlassian-Token: no-check', \
                        '-H', 'Accept: application/json', '--form', 'file=@"{}"'.format(filename), \
                        '-o', 'uploadAttach-{}.json'.format(filename)] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
    logging.debug('jiraUploadAttachment: upload attachment {}'.format(filename))

def jiraQueryUser(jiraSite, userName, output):
    authPieces = getAuthPieces()
    cmdCurl = sb.Popen(['curl', '-s', '-X', 'GET', '--url', \
                        'https://{}/rest/api/2/user?username={}'.format(jiraSite, userName), \
                        '-H', 'Content-Type: application/json', \
                        '-H', 'Accept: application/json', '--data', '@{}'.format(input), '-o', output] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()

def jiraAssignIssue(jiraSite, idOrKey, input, output):
    authPieces = getAuthPieces()
    cmdCurl = sb.Popen(['curl', '-s', '-w', '%{http_code}', '-X', 'PUT', '--url', \
                        'https://{}/rest/api/2/issue/{}/assignee'.format(jiraSite, idOrKey), \
                        '-H', 'Content-Type: application/json', \
                        '-H', 'Accept: application/json', '--data', '@{}'.format(input), '-o', output] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
    while True:
        http_code = cmdCurl.stdout.readline()
        http_code = bytes.decode(http_code, 'utf-8')
        break
    return http_code

def jiraValidateUser(jiraSite, userName):
    authPieces = getAuthPieces()
    cmdCurl = sb.Popen(['curl', '-s', '-X', 'GET', '--url', \
                        'https://{}/rest/api/2/user?username={}'.format(jiraSite, userName), \
                        '-H', 'Accept: application/json', '-o', 'validate-{}.json'.format(userName)] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()

def jiraTransitStatus(jiraSite, issueKey, newStatus, resolution):
    checkJIRACredentials()
    authPieces = getAuthPieces()
    cmdCurl = sb.Popen(['curl', '-s', '-X', 'GET', '--url', \
                        'https://{}/rest/api/2/issue/{}'.format(jiraSite, issueKey), \
                        '-H', 'Accept: application/json', '-o', 'issue.json'] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
    with open('issue.json') as f:
        jiraIssue = json.load(f)
    jiraIssueStatus = jiraIssue['fields']['status']['name']
    if newStatus == "Close":
        if jiraIssueStatus.lower().startswith("close"):
            #print("DBG: skip transit ${issueIdOrKey} to Close")
            return
    elif newStatus == "Reopen":
        if jiraIssueStatus.lower().startswith("close") == False:
            #print("DBG: skip transit ${issueIdOrKey} to Reopen")
            return

    cmdCurl = sb.Popen(['curl', '-s', '-X', 'GET', '--url', \
                        'https://{}/rest/api/2/issue/{}/transitions'.format(jiraSite, issueKey), \
                        '-H', 'Accept: application/json', '-o', 'transitions.json'] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
    with open('transitions.json') as f:
        transitions = json.load(f)
        transitions = transitions['transitions']
    resolveStatusId = 0
    for j in range(len(transitions)):
        transition = transitions[j]
        if transition['name'].startswith(newStatus) or (newStatus == "Close" and transition['name'] == "Won't fix"):
            resolveStatusId = transition['id']
            break

    if resolveStatusId == 0:
        print("Cannot transit issue {}({}) to {}".format(issueKey, jiraIssueStatus, newStatus))
        return
    transitionInput = dict()
    transitionInput['transition'] = dict()
    transitionInput['transition']['id'] = resolveStatusId
    if resolution != '':
        transitionInput['fields'] = dict()
        transitionInput['fields']['resolution'] = dict()
        transitionInput['fields']['resolution']['name'] = resolution
    with open('transition.json', 'w') as fp:
        json.dump(transitionInput, fp)
    cmdCurl = sb.Popen(['curl', '-s', '-w', '%{http_code}', '-X', 'POST', '--url', \
                        'https://{}/rest/api/2/issue/{}/transitions'.format(jiraSite, issueKey), \
                        '-H', 'Content-Type: application/json', \
                        '-H', 'Accept: application/json', '--data', '@transition.json'] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
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
        cmdCurl = sb.Popen(['curl', '-s', '-w', '%{http_code}', '-X', 'POST', '--url', \
                            'https://{}/rest/api/2/issue/{}/transitions'.format(jiraSite, issueKey), \
                            '-H', 'Content-Type: application/json', \
                            '-H', 'Accept: application/json', '--data', '@transition.json'] + authPieces, stdout=sb.PIPE)
        cmdCurl.wait()

def getKeyFields(jiraSite, extraFields):
    checkJIRACredentials()
    authPieces = getAuthPieces()
    cmdCurl = sb.Popen(['curl', '-X', 'GET', '--url', \
                        'https://{}/rest/api/2/field'.format(jiraSite), \
                        '-H', 'Accept: application/json', '-o', 'fields.json'] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()

    with open('fields.json') as f:
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
        for fieldName in extraFields:
            if fieldName in siteFieldsIdMap:
                extraFieldsMap[fieldName] = dict()
                extraFieldsMap[fieldName]['id'] = siteFieldsIdMap[fieldName]
                # TODO: capturedValue
                if siteFieldsSchemaMap[fieldName] == 'array':
                    option = dict()
                    option['value'] = extraFields[fieldName]
                    extraFieldsMap[fieldName]['value'] = []
                    extraFieldsMap[fieldName]['value'] << option
                elif siteFieldsSchemaMap[fieldName] == "option":
                    option = dict()
                    option['value'] = extraFields[fieldName]
                    extraFieldsMap[fieldName]['value'] = option
                else:
                    extraFieldsMap[fieldName]['value'] = extraFields[fieldName]

    with open("extraFieldsMap.json", "w") as outfile:
        json.dump(extraFieldsMap, outfile)

def getEPICKey(jiraSite, jiraProject, jiraEPIC):
    if os.path.isfile('epicNameField.json') == False:
        print('Invalid epicNameField.json')
        sys.exit(1)
    epicKey = dict()
    jqlCommand = "project={} and issuetype='EPIC' and 'Epic Name'='{}'".format(jiraProject, jiraEPIC)
    jiraJQLSearch(jiraSite, jqlCommand, 0, 100, 'epic.json')
    with open('epic.json') as f:
        epicInfo = json.load(f)
    # epic not existed, try to create
    if epicInfo['total'] == 0:
        with open('epicNameField.json') as f:
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
            with open('extraFieldsMap.json') as f:
                userDefinedFields = json.load(f)
            for fieldsMapKey in userDefinedFields:
                jiraIssue['fields'][userDefinedFields[fieldsMapKey]['id']] = userDefinedFields[fieldsMapKey]['value']
        with open("newEpic.json", "w") as outfile:
            json.dump(jiraIssue, outfile)
        jiraCreateIssue(jiraSite, 'newEpic.json', 'epic.json')
        # {'id': '25920', 'key': 'CTCTESTCOV-380', 'self': 'https://jiraqa.realtek.com/rest/api/2/issue/25920'}
        # {'errorMessages': [], 'errors': {'QQ': "Field 'QQ' cannot be set. It is not on the appropriate screen, or unknown."}}
        with open('epic.json') as f:
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
        with open('epic.json') as f:
            newEpicOutput = json.load(f)
        epicKey['id'] = '0'
        epicKey['key'] = '0'
        if 'id' in newEpicOutput:
            epicKey['id'] = newEpicOutput['id']
        if 'key' in newEpicOutput:
            epicKey['key'] = newEpicOutput['key']
    else:
        # ["issues"][0]["key"]
        # ["issues"][0]["id"]
        epicKey['id'] = epicInfo['issues'][0]['id']
        epicKey['key'] = epicInfo['issues'][0]['key']
    with open("epicKey.json", "w") as outfile:
        json.dump(epicKey, outfile)
    utils.heavyLogging('getEPICKey: got EPIC key {}'.format(epicKey['key']))

def createIssue(inputFile):
    checkJIRACredentials()
    output = os.path.join(workDir, '.createIssue.json')
    jiraCreateIssue(os.getenv('JIRA_SITE'), inputFile, output)
    with open(output) as f:
        createIssue = json.load(f)
    if "errorMessages" not in createIssue:
        logging.debug('createIssue: create issue {}'.format(createIssue['key']))
    else:
        logging.debug('createIssue: create issue failed {}'.format(createIssue['errors']))

def updateIssue(inputFile):
    checkJIRACredentials()
    with open(inputFile) as f:
        issue = json.load(f)
    if 'key' not in issue:
        logging.debug('updateIssue: invalid input {}'.format(inputFile))
    retCode = jiraUpdateIssue(os.getenv('JIRA_SITE'), issue['key'], inputFile)
    logging.debug('updateIssue: code {}'.format(retCode))

def addWatcher(inputFile):
    checkJIRACredentials()
    with open(inputFile) as f:
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
    with open(inputFile) as f:
        issue = json.load(f)
    if 'key' not in issue:
        logging.debug('updateIssue: invalid input {}'.format(inputFile))
    retCode = jiraAssignIssue(os.getenv('JIRA_SITE'), issue['key'], inputFile, '.assignIssue.json')
    logging.debug('assignIssue: code {}'.format(retCode))

def uploadAttachment(inputFile):
    checkJIRACredentials()
    with open(inputFile) as f:
        params = json.load(f)
    if not os.path.isfile(params['attach']):
        logging.debug('uploadAttachment: invalid file {}'.format(params['attach']))
    jiraUploadAttachment(os.getenv('JIRA_SITE'), params['key'], params['attach'])

def queryIssues(inputFile):
    checkJIRACredentials()
    with open(inputFile) as f:
        params = json.load(f)
    jqlCommand = "project={} and issuetype='{}'".format(params['project'], params['issuetype'])
    if 'labels' in params:
        for label in params['labels']:
            jqlCommand = jqlCommand + ' and labels=\'{}\''.format(label)
    
    issues = []
    for i in range(100):
        jiraJQLSearch(os.getenv('JIRA_SITE'), jqlCommand, i*1000, 1000, 'issues.json')
        with open('issues.json') as f:
            ret = json.load(f)
        issues = issues + ret['issues']
        if len(ret['issues']) < 1000:
            break
    with open("issues.json", "w") as outfile:
        json.dump(issues, outfile)

def main(argv):
    try:
        opts, args = getopt.getopt(argv[1:], 'i:w:f:c:v', ["input=", "work_dir=", "config=", "command=", "version"])
    except getopt.GetoptError:
        print('Invalid options')
        sys.exit()

    global workDir
    command = ''
    inputFile = ''
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
        elif name in ('-w', '--work_dir'):
            if os.path.exists(value) == False:
                os.mkdir(value)
            workDir = value

    if os.path.isdir(workDir) == False:
        os.makedirs(workDir)
    logging.basicConfig(filename=os.path.join(workDir, 'jira.log'), level=logging.DEBUG, filemode='w')
    if inputFile == '':
        sys.exit('Invalid input')
    configs = dict()
    utils.checkLicense(os.path.dirname(sys.argv[0]), configs, 'jira')
    if command == "CREATE_ISSUE":
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
        queryIssues(inputFile)
        sys.exit(0)
    else:
        print('Invalid command {}'.format(command))

if __name__ == "__main__":
    main(sys.argv)