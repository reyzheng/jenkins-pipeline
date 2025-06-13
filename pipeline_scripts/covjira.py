# key comments
# initialliy triaged as ignore, will not be created as JIRA issue
# initialliy triaged as FP/Intentional, will be created as JIRA issue, and closed soon
# user triaged to ignore, issue will not be closed
# user triaged to FP/Intentional, issue will be closed

from datetime import date
import os, logging, time
import getopt, sys
import json, re
import urllib.parse
import subprocess as sb
import jira, utils, coverityapi
from string import Template

TRIAGES_TO_CLOSE = ['Intentional', 'False Positive', 'Ignore']
# label contains spaces which is invalid.
LABELS_TO_CLOSE = ['Intentional', 'FalsePositive', 'Ignore']
jsonGlobal = dict()

criticalFields = []
# all existed issues
# existedJiraIssues[CID]
# or
# existedJiraIssues[CID + component]
existedJiraIssues = dict()
detectedIssues = dict()
# TODO: dump issuesAtSpecificStream to file
issuesAtSpecificStream = dict()

def cleanhtml(raw_html):
  CLEANR = re.compile('{.*?}')
  cleantext = re.sub(CLEANR, '', raw_html)
  return cleantext

def extractCID(summary):
    tokens = re.split(r'\[|\]| ', summary)
    return tokens[1]

def getExistedJIRAIssues(jiraSite, jiraProject, jiraIssueType, outputFile):
    with open('epic.json', 'r', encoding='utf-8') as f:
        epicInfo = json.load(f)
    hasEPIC = True
    if epicInfo['total'] == 0:
        hasEPIC = False
    # coverity project as label or EPIC
    projectQuery = ''
    if hasEPIC == True:
        with open('epicKey.json', 'r', encoding='utf-8') as f:
            epicKey = json.load(f)
        projectQuery = "and 'Epic Link'='{}'".format(epicKey['key'])
    else:
        if jsonGlobal['coverity_project_name'] != jsonGlobal['defects_issue_epic']:
            projectQuery = "and labels='EPIC:{}'".format(jsonGlobal['defects_issue_epic'])
        else:
            projectQuery = "and labels='COVPRJ:{}'".format(jsonGlobal['coverity_project_name'])

    issueTypes = jira.jiraProjectIssueTypes(jiraSite, jiraProject)
    if jiraIssueType == 'Issue' and 'Issue' in issueTypes:
        jqlCommand = "project={} and (issuetype='Task' or issuetype='Issue' or issuetype='Sub-task') {}".format(jiraProject, projectQuery)
    else:
        jqlCommand = "project={} and (issuetype='Task' or issuetype='Sub-task') {}".format(jiraProject, projectQuery)
    jqlCommand = jqlCommand + "and labels!='SUMMARY'"
    
    utils.heavyLogging('getExistedJIRAIssues: {}'.format(jqlCommand))
    jira.queryIssues(jiraSite, jqlCommand, outputFile)

def getComponentsMap():
    jira.checkJIRACredentials()
    authPieces = jira.getAuthPieces()
    cmdCurl = sb.Popen(['curl', '-k', '-s', '-X', 'GET', '--url', \
                        'https://{}/rest/api/2/project/{}/components'.format(jsonGlobal['site_name'], jsonGlobal['defects_jira_project']), \
                        '-H', 'Accept: application/json', '-o', 'components.json'] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
    resultMap = dict()
    with open('components.json', 'r', encoding='utf-8') as f:
        components = json.load(f)
    for component in components:
        resultMap[component['name']] = component
    # check user defined components
    if 'PF_ROOT' in os.environ:
        userDefinedComponentMap = os.path.join(os.getenv('PF_ROOT'), 'scripts', 'jiraComponents')
        if 'WORKSPACE' in os.environ:
            userDefinedComponentMap = os.path.join(os.getenv('WORKSPACE'), userDefinedComponentMap)
        if os.path.isfile(userDefinedComponentMap):
            fpUsrComponent = open(userDefinedComponentMap, 'r')
            while True:
                line = fpUsrComponent.readline()
                if not line:
                    break
                tokens = line.split()
                if tokens[0] in resultMap:
                    resultMap[tokens[0]]['lead']['name'] = tokens[1]
                    utils.heavyLogging('getComponentsMap: user defined component lead {}({})'.format(tokens[1], tokens[0]))
            fpUsrComponent.close()
    with open('componentsMap.json', 'w') as outfile:
        json.dump(resultMap, outfile)

def updateDetectedDefectsToJiraIssues():
    with open('epic.json', 'r', encoding='utf-8') as f:
        epicInfo = json.load(f)
    hasEPIC = True
    if epicInfo['total'] == 0:
        hasEPIC = False

    if hasEPIC == True:
        with open('epicKey.json', 'r', encoding='utf-8') as f:
            epicKey = json.load(f)
        with open('epicLinkField.json', 'r', encoding='utf-8') as f:
            field = json.load(f)
        epicLinkFieldId = field["id"]
    with open('extraFieldsMap.json', 'r', encoding='utf-8') as f:
        fieldsMap = json.load(f)
    with open('componentsMap.json', 'r', encoding='utf-8') as f:
        componentsMap = json.load(f)

    jiraIssuesToClose = dict()
    jiraIssuesToClose["count"] = 0
    jiraIssuesToClose["issues"] = []
    jiraIssuesToReopen = dict()
    jiraIssuesToCreate = dict()
    jiraIssuesToCreate["count"] = 0
    jiraIssuesToCreate["issues"] = []
    count = 0
    for key in detectedIssues:
        detectedIssue = detectedIssues[key]
        issueComponent = detectedIssue["component"]
        if jsonGlobal['defects_assign_policy'] == 'component' and issueComponent not in componentsMap:
            utils.heavyLogging('updateDetectedDefectsToJiraIssues: skip issue cid: {} (unknown componet {})'.format(key, issueComponent))
            continue
        if detectedIssue['type'] == 'update':
            utils.heavyLogging('updateDetectedDefectsToJiraIssues: update issue cid, {}'.format(key))
            # user triaged to FP/Intentional, issue will be closed
            if detectedIssue['triage'] in TRIAGES_TO_CLOSE:
                jiraIssuesToClose['count'] = jiraIssuesToClose['count'] + 1
                issueToClose = dict()
                issueToClose['issueId'] = detectedIssue['issueId']
                issueToClose['issueKey'] = detectedIssue['issueKey']
                issueToClose['cid'] = key
                newLabels = []
                existedLabels = detectedIssue['labels']
                for existedLabel in existedLabels:
                    if existedLabel not in LABELS_TO_CLOSE:
                        newLabels.append(existedLabel)
                newLabels.append(detectedIssue['triage'].replace(' ', ''))
                issueToClose['labels'] = newLabels
                utils.lightLogging('updateDetectedDefectsToJiraIssues: close issue {}'.format(issueToClose['issueKey']))
                utils.lightLogging('updateDetectedDefectsToJiraIssues: existed labels {}'.format(existedLabels))
                utils.lightLogging('updateDetectedDefectsToJiraIssues: new labels {}'.format(newLabels))
                jiraIssuesToClose['issues'].append(issueToClose)
            else:
                updatedIssue = dict()
                updatedIssue['component'] = issueComponent
                updatedIssue['mergeKey'] = detectedIssue['mergeKey']
                updatedIssue['fields'] = dict()
                updatedIssue['fields']['summary'] = detectedIssue['summary']
                updatedIssue['fields']['labels'] = detectedIssue['labels']
                updatedIssue['fields']['description'] = detectedIssue['description_url'] + '\n' + detectedIssue['description_streams_str']
                updatedIssue['co-authors'] = detectedIssue['co-authors']
                for fieldsMapKey in fieldsMap:
                    fieldId = fieldsMap[fieldsMapKey]['id']
                    if fieldsMap[fieldsMapKey]['value'] is None:
                        fieldValue = ""
                    else:
                        fieldValue = fieldsMap[fieldsMapKey]['value']
                    updatedIssue['fields'][fieldId] = fieldValue
                if 'assignee' in detectedIssue:
                    updatedIssue['fields']['assignee'] = dict()
                    updatedIssue['fields']['assignee']['name'] = detectedIssue['assignee']
                jiraIssuesToReopen[detectedIssue['issueId']] = updatedIssue
        elif detectedIssue['type'] == 'update_comment':
            updatedIssue = dict()
            updatedIssue['update_comment_only'] = True
            updatedIssue['mergeKey'] = detectedIssue['mergeKey']
            jiraIssuesToReopen[detectedIssue['issueId']] = updatedIssue
        else:
            utils.heavyLogging('updateDetectedDefectsToJiraIssues: create issue cid {}'.format(key))
            jiraIssue = dict()
            jiraIssue['component'] = issueComponent
            jiraIssue['fields'] = dict()
            jiraIssue['fields']['project'] = dict()
            jiraIssue['fields']['project']['key'] = jsonGlobal['defects_jira_project']
            jiraIssue['fields']['summary'] = detectedIssue["summary"]
            jiraIssue['fields']['description'] = detectedIssue['description_url'] + "\n" + detectedIssue['description_streams_str']
            jiraIssue['co-authors'] = detectedIssue['co-authors']
            jiraIssue['fields']['labels'] = detectedIssue["labels"]
            if hasEPIC == True:
                jiraIssue['fields'][epicLinkFieldId] = epicKey['key']
            for fieldsMapKey in fieldsMap:
                fieldId = fieldsMap[fieldsMapKey]['id']
                fieldValue = fieldsMap[fieldsMapKey]['value']
                jiraIssue['fields'][fieldId] = fieldValue
            jiraIssueToCreate = dict()
            if 'subTask' in detectedIssue:
                jiraIssueToCreate['subTask'] = 1
            jiraIssueToCreate['issue'] = jiraIssue
            jiraIssueToCreate['cid'] = extractCID(jiraIssue['fields']['summary'])
            jiraIssueToCreate['mergeKey'] = detectedIssue['mergeKey']
            jiraIssueToCreate['close'] = False
            # initialliy triaged as FP/Intentional, will be created as JIRA issue, and closed soon
            utils.lightLogging('updateDetectedDefectsToJiraIssues: triage {}'.format(detectedIssue['triage']))
            utils.lightLogging('updateDetectedDefectsToJiraIssues: defects_assign_policy {}'.format(jsonGlobal['defects_assign_policy']))
            if detectedIssue['triage'] in TRIAGES_TO_CLOSE:
                jiraIssue['fields']['labels'].append(detectedIssue['triage'].replace(' ', ''))
                jiraIssueToCreate['close'] = True
            else:
                assignee = ""
                assigneeFull = ""
                if jsonGlobal['defects_assign_policy'] == "default":
                    assignee = jsonGlobal['defects_default_assignee']
                elif jsonGlobal['defects_assign_policy'] == "author":
                    assignee = detectedIssue['assignee']
                    assigneeFull = detectedIssue['assigneefull']
                elif jsonGlobal['defects_assign_policy'] == 'component':
                    # component mode: assignee is temporally assigned, component lead will assign issue to specified user
                    # therefore, add component lead to watcher also.
                    if issueComponent in componentsMap:
                        assignee = componentsMap[issueComponent]['lead']['name']
                    else:
                        assignee = jsonGlobal['defects_default_assignee']
                jiraIssueToCreate['assignee'] = assignee
                jiraIssueToCreate['assigneeFull'] = assigneeFull
            jiraIssuesToCreate["issues"].append(jiraIssueToCreate)
            jiraIssuesToCreate["count"] = jiraIssuesToCreate["count"] + 1
        count = count + 1
        #if jsonGlobal['defects_number_limit'] != 0 and count >= jsonGlobal['defects_number_limit']:
        #    break
    with open('jiraIssuesToClose.json', 'w') as fp:
        json.dump(jiraIssuesToClose, fp)
    with open('jiraIssuesToReopen.json', 'w') as fp:
        json.dump(jiraIssuesToReopen, fp)
    with open('jiraIssuesToCreate.json', 'w') as fp:
        json.dump(jiraIssuesToCreate, fp)

def parseExistedJIRAIssues():
    with open('existedJiraIssues_RAW.json', 'r', encoding='utf-8') as f:
        jsonIssues = json.load(f)
    countMergeKey = 0
    countCID = 0
    for jiraIssue in jsonIssues:
        summary = jiraIssue['fields']['summary']
        CID = extractCID(summary)
        description = jiraIssue['fields']['description']
        mergeKey = ''
        if description.startswith('mergeKey:'):
            lines = description.splitlines()
            mergeKey = lines[0].split(':')[1]
        if mergeKey == '':
            mapKey = CID
            if jiraIssue['fields']['status']['name'].lower() == 'closed':
                # trick, for closed JIRA issue, do not add countCID for closed JIRA issue
                # to avoid 'unnormalized JIRA issue description' exception
                pass
            else:
                if mapKey.isnumeric():
                    countCID = countCID + 1
                else:
                    # component issue (of group mode)
                    pass
        else:
            mapKey = mergeKey
            countMergeKey = countMergeKey + 1
        if jsonGlobal["defects_assign_policy"] == 'component':
            if "CN3SD8" in jsonGlobal["defects_customization"]:
                # For CN3SD8, parse component from summary 
                tokens = re.split(r'\[|\]| ', summary)
                mapKey += tokens[5]
            else:
                if (len(jiraIssue["fields"]['components']) > 0):
                    mapKey += jiraIssue["fields"]['components'][0]["name"]
                else:
                    # intentionally fail for invalid component configuration
                    mapKey += "ERR_UNKNOWN"
                    logging.debug('parseExistedJIRAIssues: invalid component {}'.format(CID))
        existedJiraIssues[mapKey] = jiraIssue
        utils.lightLogging('parseExistedJIRAIssues: existed JIRA issue mapKey {}'.format(mapKey))
    utils.heavyLogging('parseExistedJIRAIssues: cid count {}, mergeKey count {}'.format(countCID, countMergeKey))
    if countCID > 0 and countMergeKey > 0:
        utils.heavyLogging('parseExistedJIRAIssues: unnormalized JIRA issue description')
        sys.exit(1)
    elif countMergeKey > 0:
        return 'mergeKey'
    else:
        return 'CID'

# For RSIPCAM, CN3SD7 special usage
# RSIPCAM: component, CN3SD7: group_by_author
def reconstructDefects(defectReportObject, jiraIssueKeyCategory):
    defectsByComponet = dict()
    defects = defectReportObject["defects"]
    for key in defects:
        CID = key
        mergeKey = defects[key]['mergeKey']
        if defectReportObject['assignPolicy'] == 'component':
            groupKey = defects[key]['components'][0]
        else:
            # author-{coverityProject} as issue key
            groupKey = 'unknown-{}'.format(defectReportObject['coverityProject'])
            assignee = 'unknown'
            assigneeFull = 'unknown@realtek.com'
            # take first author as groupKey
            for event in defects[key]['events']:
                if event['author'] != '':
                    groupKey = '{}-{}'.format(event['author'], defectReportObject['coverityProject'])
                    assignee = event['author']
                    assigneeFull = event['authorfull']
                    break
        # init a new defect by issueComponent
        if groupKey not in defectsByComponet:
            #defectsByComponet[issueComponent] = defects[key]
            defectsByComponet[groupKey] = dict()
            defectsByComponet[groupKey]['mainIssue'] = True
            if defectReportObject['assignPolicy'] == 'group_by_author':
                defectsByComponet[groupKey]['assignee'] = assignee
                defectsByComponet[groupKey]['assigneeFull'] = assigneeFull
            defectsByComponet[groupKey]['triage'] = defects[key]['triage']
            defectsByComponet[groupKey]['components'] = defects[key]['components']
            defectsByComponet[groupKey]['events'] = []
            defectsByComponet[groupKey]['mergeKey'] = groupKey
        # modify ['triage']["classification"]
        if defects[key]['triage']['classification'] != "False Positive" and defects[key]['triage']['classification'] != "Intentional":
            # mark Unclassified if any issue in the component not FP/Intentional
            defectsByComponet[groupKey]['triage']['classification'] = "Unclassified"
            event = dict()
            # take CID, subcategoryShortDescription as filePathname, functionDisplayName
            if jiraIssueKeyCategory == 'CID':
                event['filePathname'] = CID
            else:
                event['filePathname'] = mergeKey
            event['functionDisplayName'] = defects[key]['subcategoryShortDescription']
            defectsByComponet[groupKey]["events"].append(event)
    return defectsByComponet

def transExtraSummary(pattern, issue):
    summary = ''
    pieces = re.split(r'( |\]|\[)', pattern)
    count = 0
    for piece in pieces:
        if piece != '':
            if piece.startswith('key:'):
                key = piece[4:]
                if key in issue:
                    summary = summary + issue[key]
                else:
                    utils.lightLogging('transExtraSummary: invalid pattern {}'.format(key))
            elif '$' in  piece or '%' in piece:
                extracted = utils.extractScriptedParameter(piece, 'issue-summary-{}'.format(count))
                summary = summary + extracted
                count = count + 1
            else:
                summary = summary + piece
    return summary

def getHeadCommitter(assignPolicy, issue):
    ret = dict()

    if assignPolicy == 'component' and 'mainIssue' in issue:
        headCommitter = 'COMPONENT'
        headCommitterFull = 'COMPONENT'
    elif assignPolicy == 'group_by_author' and 'mainIssue' in issue:
        headCommitter = issue['assignee']
        headCommitterFull = issue['assigneeFull']
    else:
        headCommitter = ''
        if assignPolicy == 'committer':
            for event in issue["events"]:
                if event['committer'] != '':
                    headCommitter = event['committer']
                    headCommitterFull = event['committerfull']
                    break
        else:
            for event in issue["events"]:
                if event['committer'] != '':
                    headCommitter = event['author']
                    headCommitterFull = event['authorfull']
                    break
        # headCommitter == "" -> caused by non-realtek user or invalid file path
        # check covanalyze.py defectsAnalyzer()
        if headCommitter == '':
            with open('componentsMap.json', 'r', encoding='utf-8') as f:
                componentsMap = json.load(f)
            if issue['components'][0] in componentsMap:
                headCommitter = componentsMap[issue['components'][0]]['lead']['name']
            else:
                headCommitter = jsonGlobal['defects_default_assignee']
            headCommitterFull = '{}@realtek.com'.format(headCommitter)
            utils.heavyLogging('getHeadCommitter: empty headCommitter, assign to {}'.format(headCommitter))
    ret['headCommitter'] = headCommitter
    ret['headCommitterFull'] = headCommitterFull

    return ret

# report -> preview-report-committer.json
# output -> detectedIssues
def parseCoverityDefetcs(reportPath, report, suffix, jiraIssueKeyCategory):
    with open('epic.json', 'r', encoding='utf-8') as f:
        epicInfo = json.load(f)
    hasEPIC = True
    if epicInfo['total'] == 0:
        hasEPIC = False

    report = os.path.join(reportPath, report)
    if not os.path.isfile(report):
        utils.heavyLogging("updateDetectedDefects: invalid defects report {}({})".format(report, os.getcwd()))
        return
    utils.heavyLogging("updateDetectedDefects: got defects report {}".format(report))
    with open(report, 'r', encoding='utf-8') as f:
        defectReportObject = json.load(f)
    issuesAtSpecificStream[defectReportObject["coverityStream"]] = []
    if defectReportObject['assignPolicy'] == 'component' or defectReportObject['assignPolicy'] == 'group_by_author':
        if defectReportObject['assignPolicy'] == 'component':
            # create a JIRA component issue, and create defects as JIRA sub-tasks under the "JIRA component issue"
            for key in defectReportObject['defects']:
                defectReportObject['defects'][key]['subTask'] = 1
        else:
            # create a JIRA author issue (with coverity project as issue title) -> [reycheng CTCSOC_test]
            pass
        defects = reconstructDefects(defectReportObject, jiraIssueKeyCategory)
        if defectReportObject['assignPolicy'] == 'component':
            # sub-tasks
            defects.update(defectReportObject['defects'])
        else:
            # CN3SD7 says that sub-tasks is not required
            pass
    else:
        defects = defectReportObject['defects']

    jiraExcludes = []
    if 'PF_ROOT' in os.environ:
        fileExcludes = os.path.join(os.getenv('WORKSPACE'), '{}/scripts/jira_excludes'.format(os.getenv('PF_ROOT')))
        if os.path.exists(fileExcludes):
            logging.debug('Read excludes list: {}'.format(fileExcludes))
            with open(fileExcludes) as fp:
                while True:
                    line = fp.readline()
                    if not line:
                        break
                    jiraExcludes.append(line.strip())
        utils.heavyLogging('updateDetectedDefects: got excludes list: {}'.format(jiraExcludes))

    groupMode = False
    if defectReportObject['assignPolicy'] == 'component' or defectReportObject['assignPolicy'] == 'group_by_author':
        groupMode = True
    host = defectReportObject["host"]
    port = defectReportObject["port"]
    coverityURL = 'http://{}:{}/query/defects.htm?project={}'.format(host, port, jsonGlobal["coverity_project_name"])
    fpCovUrl = open('.coverity-url', 'w')
    fpCovUrl.write(coverityURL)
    fpCovUrl.close()
    cidsIgnored = []
    # key is CID or component
    for key in defects:
        issue = defects[key]
        CID = key
        # TODO: remove clause 'mergeKey' in issue
        if jiraIssueKeyCategory == 'mergeKey' and 'mergeKey' in issue:
            mapKey = issue['mergeKey']
        else:
            # take CID or component(component assignPolicy) as mapKey
            mapKey = CID
        # TODO: sorry, we deal with the first coverity component only
        issueComponent = issue['components'][0]
        if jsonGlobal['defects_assign_policy'] == 'component':
            mapKey += issueComponent
        utils.lightLogging('updateDetectedDefects: mapKey {}'.format(mapKey))
        if "CN3SD8" in jsonGlobal["defects_customization"]:
            sdkVersion = jsonGlobal["coverity_project_name"].split("_")
            preConfig = defectReportObject["coverityStream"][defectReportObject["coverityStream"].index(sdkVersion[1]) + len(sdkVersion[1]) + 1:]
            issueSummary = "[{}][{}][{}][{}] {}".format(key, sdkVersion[1], issueComponent, preConfig, issue["subcategoryShortDescription"])
        elif groupMode == True and 'mainIssue' in issue:
            issueSummary = "[{}]".format(key)
        else:
            # general issue or subTask
            if 'defects_extra_summary' in jsonGlobal and jsonGlobal['defects_extra_summary'] != '':
                extraSummary = transExtraSummary(jsonGlobal['defects_extra_summary'], issue)
                issueSummary = "[{}]{} {}".format(key, extraSummary, issue["subcategoryShortDescription"])
            else:
                issueSummary = "[{}] {}".format(key, issue["subcategoryShortDescription"])

        if groupMode == True and 'mainIssue' in issue:
            issueURL = '{}'.format(coverityURL)
        else:
            issueURL = '{}&cid={}'.format(coverityURL, CID)
        issueDescription = "coverity stream {}, snapshot: {}".format(defectReportObject["coverityStream"], defectReportObject["snapshot"])
        if "MORE_DESCRIPTION" in jsonGlobal["defects_customization"]:
            if defectReportObject["snapshotVersion"] != "null" or defectReportObject["snapshotDescription"] != "null":
                if defectReportObject["snapshotVersion"] != "null":
                    issueDescription += ", version: {}".format(defectReportObject["snapshotVersion"])
                if defectReportObject["snapshotDescription"] != "null":
                    issueDescription += ", description: {}".format(defectReportObject["snapshotDescription"])

        if groupMode == True and 'mainIssue' in issue:
            for event in issue["events"]:
                file = event['filePathname']
                func = event["functionDisplayName"]
                issueDescription += "\n{}: {}".format(file, func)
        else:
            if "MORE_DESCRIPTION" in jsonGlobal["defects_customization"]:
                issueDescription += '\n||file||function||line||commit||author||committer||'
            else:
                issueDescription += '\n||file||function||line||commit||'
            for event in issue["events"]:
                file = event['filePathname']
                func = event["functionDisplayName"]
                line = event["lineNumber"]
                commithash = event['commithash']
                author = event['author']
                committer = event['committer']
                if func == '':
                    func = 'u/a'
                if commithash == '':
                    commithash = 'u/a'
                if author == '':
                    author = 'u/a'
                if committer == '':
                    committer = 'u/a'
                if "MORE_DESCRIPTION" in jsonGlobal["defects_customization"]:
                    if 'description' in event:
                        eventDescription = event['description'].encode('latin1').decode('unicode-escape').encode('latin1').decode('utf-8')
                        issueDescription += "\n||{}||{}||{}({})||{}||{}||{}||".format(file, func, line, eventDescription, commithash, author, committer)
                    else:
                        issueDescription += "\n||{}||{}||{}||{}||{}||{}||".format(file, func, line, commithash, author, committer)
                else:
                    #issueDescription += "\n{}: {}: {}".format(file, func, line)
                    issueDescription += "\n||{}||{}||{}||{}||".format(file, func, line, commithash)
            issueDescription += "\n, {color:#FF0000}status: open{color}"

        labels_project = []
        labels_streams = []
        labels_security = []
        if hasEPIC == True:
            # For CN3SD4, append coverity_project_name to label if necessary
            if jsonGlobal['coverity_project_name'] != jsonGlobal['defects_issue_epic']:
                labels_project.append('COVPRJ:' + jsonGlobal['coverity_project_name'])
        else:
            labels_project.append('COVPRJ:' + jsonGlobal["coverity_project_name"])
            if jsonGlobal['coverity_project_name'] != jsonGlobal['defects_issue_epic']:
                labels_project.append('EPIC:' + jsonGlobal['defects_issue_epic'])
        labels_streams.append(defectReportObject["coverityStream"])
        if 'impact' in issue:
            labels_security.append("Impact:{}".format(issue["impact"]))
        if 'LABEL_IMPACT_ONLY' in jsonGlobal["defects_customization"]:
            pass
        else:
            if 'cwe' in issue and issue["cwe"] == True:
                labels_security.append("CWE_Top_25")
            if 'owasp' in issue and issue["owasp"] == True:
                labels_security.append("OWASP_Top_10")
            if 'cvss' in issue:
                labels_security.append("CVSS:{}".format(issue["cvss"]))
            if 'severity' in issue and issue["severity"] != "":
                labels_security.append("Severity:{}".format(issue["severity"].replace(" ", "")))

        # create or update jira issue
        committers = getHeadCommitter(defectReportObject['assignPolicy'], issue)

        if ("IGNORE_EXCLUDES" in jsonGlobal["defects_customization"] and 
                jsonGlobal["defects_assign_policy"] == "author"):
            excludedCommitter = False
            if committers['headCommitter'] in jiraExcludes:
                excludedCommitter = True
            if excludedCommitter == True:
                print('Exclude committer {}({})'.format(CID, committers['headCommitter']))
                cidsIgnored.append(CID)
                continue

        # move issue to issuesAtSpecificStream iff author found
        issuesAtSpecificStream[defectReportObject["coverityStream"]].append(mapKey)
        if mapKey in detectedIssues:
            utils.heavyLogging("updateDetectedDefects: update defect({}): {}".format(defectReportObject["coverityStream"], mapKey))
        else:
            utils.heavyLogging("updateDetectedDefects: create defect({}): {}".format(defectReportObject["coverityStream"], mapKey))
            detectedIssues[mapKey] = dict()
            if defectReportObject['assignPolicy'] == 'group_by_author':
                detectedIssues[mapKey]['force_update'] = True
            if 'subTask' in issue:
                detectedIssues[mapKey]['subTask'] = 1
            #detectedIssues[mapKey]["description_stream"] = set()
            detectedIssues[mapKey]['labels'] = []
            detectedIssues[mapKey]['labels_project'] = []
            detectedIssues[mapKey]['labels_streams'] = []
            detectedIssues[mapKey]['labels_security'] = []
            detectedIssues[mapKey]['description_streams'] = dict()
            detectedIssues[mapKey]['description_streams_str'] = ''
        detectedIssues[mapKey]['summary'] = issueSummary
        detectedIssues[mapKey]['mergeKey'] = issue['mergeKey']
        if jiraIssueKeyCategory == 'mergeKey':
            detectedIssues[mapKey]['description_url'] = composeRTKIssueDescriptionURL([issueURL], issue['mergeKey'])
        else:
            detectedIssues[mapKey]['description_url'] = composeRTKIssueDescriptionURL([issueURL], '')
        detectedIssues[mapKey]['pure_url'] = issueURL
        for label_project in labels_project:
            detectedIssues[mapKey]["labels_project"].append(label_project)
        for label_streams in labels_streams:
            detectedIssues[mapKey]["labels_streams"].append(label_streams)
        for label_security in labels_security:
            detectedIssues[mapKey]["labels_security"].append(label_security)
        coverity_stream = re.split(',| ', issueDescription)[2]
        detectedIssues[mapKey]["description_streams"][coverity_stream] = issueDescription
        detectedIssues[mapKey]['assignee'] = committers['headCommitter']
        detectedIssues[mapKey]['assigneefull'] = committers['headCommitterFull']
        detectedIssues[mapKey]['co-authors'] = []
        detectedIssues[mapKey]['triage'] = issue['triage']['classification']
        # user triaged to ignore, issue will not be closed
        # TRIAGES_TO_CLOSE checks 'triage' attribute only
        detectedIssues[mapKey]['action'] = issue['triage']['action']
        detectedIssues[mapKey]["CID"] = CID
        detectedIssues[mapKey]["component"] = issueComponent
    attribute = dict()
    attribute['attributeName'] = 'Action'
    attribute['attributeValue'] = 'Ignore'
    ignoredPayload = dict()
    ignoredPayload['cids'] = cidsIgnored
    ignoredPayload['attributeValuesList'] = [attribute]
    with open('ignored-payload-{}'.format(suffix), 'w') as fpPayload:
        fpPayload.write(json.dumps(ignoredPayload))
    # curl --location -X PUT 'http://172.21.15.146:8080/api/v2/issues/triage?locale=en_us&triageStoreName=CN2SD5_Luna_G3' 
    # -H 'Content-Type: application/json' -H 'Accept: application/json' --user cn2sd5.0:cn2sd5.0 -d @ignored-raw-custom
    # TODO: handle this at RJIRA
    if len(cidsIgnored) > 0  and 'COV_AUTH_KEY' in os.environ and 'PF_COV_HOST' in os.environ:
        COV_AUTH_KEY = os.getenv('COV_AUTH_KEY')
        fpCovAuthKey = open(COV_AUTH_KEY)
        data = json.load(fpCovAuthKey)
        fpCovAuthKey.close()

        #utils.heavyLogging("debug coverityapi 568 reviewed")
        coverityapi.triageCoverityIssues(data["username"], data["key"], \
                                            'http://{}:{}'.format(os.getenv('PF_COV_HOST'), os.getenv('PF_COV_PORT')), \
                                            jsonGlobal['coverity_project_name'], 'ignored-payload-{}'.format(suffix))
        print("JIRA: triage defects(ignored-payload) ignored")
        print(cidsIgnored)

def mergeDict(existed, detected):
    mergedDict = dict()
    for key_stream in existed:
        mergedDict[key_stream] = existed[key_stream]
    for key_stream in detected:
        mergedDict[key_stream] = detected[key_stream]

    return mergedDict

def parseRTKIssueDescription(description):
    descriptions = dict()
    descriptions['mergeKey'] = ''
    descriptions['url'] = []
    descriptions['streams'] = dict()

    searchUrls = True
    searchStreams = False
    description_stream = ''
    for line in description.splitlines():
        if line.startswith('mergeKey:'):
            tokens = line.split(':')
            descriptions['mergeKey'] = tokens[1]
            continue
        if searchUrls == True:
            # line.startswith('http') -> old simple style, http://172.21.15.146:8080/query/defects.htm...
            # else, new table style
            if line.startswith('http') and 'defects.htm' in line:
                descriptions['url'].append(line.strip())
            elif line.startswith('coverity links:') or line.startswith('||project||'):
                pass
            elif line.startswith('||'):
                tokens = line.split('||')
                urls = tokens[2].split('|')
                descriptions['url'].append(urls[0][1:])
            else:
                # \n or coverity stream...
                searchUrls = False
                searchStreams = True
        if searchStreams == True:
            if line.startswith('coverity stream '):
                if description_stream != "":
                    descriptions['streams'][coverity_stream] = description_stream
                description_stream = line
                coverity_stream = re.split(',| ', description_stream)[2]
            elif line.startswith("----"):
                # horizontal ruler
                break
            elif description_stream != "":
                description_stream += "\n" + line
    if description_stream != '':
        descriptions['streams'][coverity_stream] = description_stream

    return descriptions

def composeRTKIssueDescriptionURL(urls, mergeKey):
    if mergeKey == '':
        result = ''
    else:
        result = 'mergeKey:{}\n'.format(mergeKey)
    result += 'coverity links:\n'
    result += '||project||link||\n'
    for url in urls:
        url = url.strip()
        tokens = url.split('&')
        coverityProject = tokens[0][tokens[0].index('=') + 1:]
        result += '||{}||[{}|{}]||\n'.format(coverityProject, url, url)
    return result

def queryExistedJIRAIssueWatchers(existedJiraIssue):
    ret = []
    if 'watches' in existedJiraIssue['fields']:
        url = existedJiraIssue['fields']['watches']['self']
        jira.jiraGeneralURLQuery(url, 'watchers.json')
        watchers = dict()
        with open('watchers.json', 'r', encoding='utf-8') as f:
            watchers = json.load(f)
        if 'watchers' in watchers:
            for watcher in watchers['watchers']:
                ret.append(watcher['name'])
    return ret

def compareSummary(newSummary, oldSummary):
    newSummaryCIDExcluded = newSummary[newSummary.index(']'):]
    oldSummaryCIDExcluded = oldSummary[oldSummary.index(']'):]
    if oldSummaryCIDExcluded != newSummaryCIDExcluded:
        return True
    return False

# parse and analyze
#     existedJiraIssues: existedJiraIssues_RAW.json
#     detectedIssues: preview-report-committer-${BRANCH}.json
# result detectedIssues, that indicates issue should be add or update
def parseExistedJIRAIssuesUpdateDetectedIssues(jiraIssueKeyCategory):
    with open('componentsMap.json', 'r', encoding='utf-8') as f:
        componentsMap = json.load(f)
    if len(componentsMap) == 0:
        jiraProjectComponetDefined = False
    else:
        jiraProjectComponetDefined = True

    for key in existedJiraIssues:
        existedJiraIssue = existedJiraIssues[key]
        existedJiraIssue["fields"]["labels_project"] = []
        existedJiraIssue["fields"]["labels_streams"] = []
        existedJiraIssues[key]["fields"]["streams_to_remove"] = []
        existedJiraIssues[key]["fields"]['toremove'] = "false"
        existedJiraIssue["fields"]["labels_security"] = []
        for label in existedJiraIssue["fields"]["labels"]:
            if (label == "CWE_Top_25" or
                    label == "OWASP_Top_10" or 
                    label.startswith("Impact:") or
                    label.startswith("CVSS:") or
                    label.startswith("Severity:")):
                existedJiraIssue["fields"]["labels_security"].append(label)
            elif ':' in label:
                # labels_project or user define labels
                existedJiraIssue["fields"]["labels_project"].append(label)
            elif label in LABELS_TO_CLOSE:
                pass
            else:
                existedJiraIssue["fields"]["labels_streams"].append(label)
        existedJiraIssue["fields"]["description_streams"] = dict()
        parsedDescription = parseRTKIssueDescription(existedJiraIssue['fields']['description'])
        existedJiraIssue['fields']['mergeKey'] = parsedDescription['mergeKey']
        existedJiraIssue['fields']['description_url'] = parsedDescription['url']
        existedJiraIssue['fields']["description_streams"] = parsedDescription['streams']

        # compute if issues resolved at specific stream
        # and re-construct description
        streams = existedJiraIssue["fields"]["labels_streams"]
        existedJiraIssue['fields']['description'] = composeRTKIssueDescriptionURL(existedJiraIssue['fields']['description_url'], existedJiraIssue['fields']['mergeKey']) + '\n'
        for stream in existedJiraIssue["fields"]["description_streams"]:
            if stream in issuesAtSpecificStream and key not in issuesAtSpecificStream[stream]:
                # the coverity stream is analyzed this time, and not found
                if stream in streams:
                    existedJiraIssues[key]["fields"]["streams_to_remove"].append(stream)
                    utils.heavyLogging("commitIssues: issue resolved {}({})".format(key, stream))
                if stream in existedJiraIssue["fields"]["description_streams"]:
                    # stupid code here, to handle endswith neither 'open' or 'fixed'
                    descStream = existedJiraIssue["fields"]["description_streams"][stream]
                    descStream = cleanhtml(descStream.strip())
                    if descStream.endswith(', status: open') or descStream.endswith(', status: fixed'):
                        existedJiraIssue["fields"]["description_streams"][stream] = descStream[:descStream.rfind(',')]
                    existedJiraIssue["fields"]["description_streams"][stream] += ", status: fixed"
            existedJiraIssue['fields']['description'] += existedJiraIssue["fields"]["description_streams"][stream] + "\n"
        # check if remains unfixed streams
        remainStreams = []
        for label in existedJiraIssues[key]["fields"]["labels"]:
            if (label == 'CWE_Top_25' or
                    label == 'OWASP_Top_10' or
                    label in LABELS_TO_CLOSE):
                pass
            elif ':' in label:
                # ex)
                # COVPRJ:CTCSOC_test
                # USER_DEFINED:CHIP_NAME
                pass
            else:
                if label not in existedJiraIssues[key]["fields"]["streams_to_remove"]:
                    remainStreams.append(label)
        if len(remainStreams) == 0 and key not in detectedIssues:
            existedJiraIssues[key]["fields"]['toremove'] = True

    # issues required to add or update
    for key in detectedIssues:
        if key in existedJiraIssues:
            utils.lightLogging('commitIssues: compare with existed CID {}'.format(key))
            existedJiraIssue = existedJiraIssues[key]
            # parse summary
            summary = existedJiraIssue["fields"]["summary"]
            # parse description
            detectedIssues[key]['type'] = "ignore"
            detectedIssues[key]['issueId'] = existedJiraIssue["id"]
            detectedIssues[key]['issueKey'] = existedJiraIssue["key"]

            # compare component iff jiraProjectComponetDefined
            if jiraProjectComponetDefined == True and detectedIssues[key]['component'] in componentsMap:
                if len(existedJiraIssue['fields']['components']) == 0 or \
                    existedJiraIssue['fields']['components'][0]['name'] != detectedIssues[key]['component']:
                    utils.lightLogging('commitIssues: component differ')
                    detectedIssues[key]['type'] = 'update'
            detectedIssues[key]["labels"] = existedJiraIssue["fields"]["labels"]
            detectedIssues[key]['description'] = existedJiraIssue['fields']['description']
            updateAssignee = False
            if existedJiraIssue['fields']['assignee'] is None:
                utils.lightLogging('commitIssues: invalid assignee')
                updateAssignee = True
                detectedIssues[key]['type'] = 'update'
            elif 'CO-AUTHOR' in jsonGlobal['defects_extra_watcher'] and \
                    detectedIssues[key]['assignee'] != existedJiraIssue['fields']['assignee']['name']:
                # for PC2SD3, JIRA issue already assigned, add new assignee to watchers
                # (defect owned by different author at different coverity stream)
                watchers = queryExistedJIRAIssueWatchers(existedJiraIssue)
                if detectedIssues[key]['assignee'] not in watchers:
                    detectedIssues[key]['type'] = 'update'
                    detectedIssues[key]['co-authors'].append(detectedIssues[key]['assignee'])
                    utils.lightLogging('commitIssues: add co-author({}) to watchers({})'.format(detectedIssues[key]['assignee'], watchers))
            #if detectedIssues[key]['summary'] != summary:
            if compareSummary(detectedIssues[key]['summary'], summary) == True:
                utils.lightLogging('commitIssues: summary differ')
                detectedIssues[key]['type'] = 'update'
            existedDescriptionUrl = existedJiraIssue['fields']['description_url']
            if detectedIssues[key]['pure_url'] not in existedDescriptionUrl:
                detectedIssues[key]['type'] = 'update'
                utils.lightLogging('commitIssues: description_url differ')
                utils.lightLogging('commitIssues: before {}'.format(existedDescriptionUrl))
                existedDescriptionUrl.append(detectedIssues[key]['pure_url'])
                utils.lightLogging('commitIssues: after {}'.format(existedDescriptionUrl))
            # TODO: remove clause 'mergeKey' in detectedIssues[key]
            if jiraIssueKeyCategory == 'mergeKey' and 'mergeKey' in detectedIssues[key]:
                detectedIssues[key]['description_url'] = composeRTKIssueDescriptionURL(existedDescriptionUrl, detectedIssues[key]['mergeKey'])
            else:
                # component issue (of group mode)
                detectedIssues[key]['description_url'] = composeRTKIssueDescriptionURL(existedDescriptionUrl, '')
            if set(detectedIssues[key]["labels_security"]).issubset(existedJiraIssue["fields"]["labels_security"]) == False:
                utils.lightLogging("commitIssues: labels_security differ")
                detectedIssues[key]['type'] = 'update'
                detectedIssues[key]["labels_security"] = list(dict.fromkeys(existedJiraIssue["fields"]["labels_security"] + detectedIssues[key]["labels_security"]))
            if set(detectedIssues[key]["labels_streams"]).issubset(existedJiraIssue["fields"]["labels_streams"]) == False:
                utils.lightLogging("commitIssues: labels_streams differ")
                detectedIssues[key]['type'] = 'update'
                detectedIssues[key]["labels_streams"] = list(dict.fromkeys(existedJiraIssue["fields"]["labels_streams"] + detectedIssues[key]["labels_streams"]))
            if set(detectedIssues[key]["labels_project"]).issubset(existedJiraIssue["fields"]["labels_project"]) == False:
                utils.lightLogging("commitIssues: labels_project differ")
                detectedIssues[key]['type'] = 'update'
                detectedIssues[key]["labels_project"] = list(dict.fromkeys(existedJiraIssue["fields"]["labels_project"] + detectedIssues[key]["labels_project"]))
            if 'force_update' in detectedIssues[key]:
                utils.lightLogging("commitIssues: force update")
                detectedIssues[key]['type'] = 'update'
            # Mark FP/Intentional to update to reopen
            if detectedIssues[key]['triage'] in TRIAGES_TO_CLOSE:
                if "close" not in existedJiraIssue["fields"]["status"]["name"].lower():
                    utils.lightLogging("commitIssues: close FP/Int./Ignore {}".format(key))
                    detectedIssues[key]['type'] = 'update'
                else:
                    # do not update issue that already closed
                    detectedIssues[key]['type'] = 'ignore'
            else:
                # Reopen closed/resolved issues
                issueStatus = existedJiraIssue['fields']['status']['name'].lower()
                if "close" in issueStatus or "resolved" in issueStatus:
                    utils.lightLogging("commitIssues: reopen closed/resolved issues {}".format(key))
                    detectedIssues[key]['type'] = 'update'

            if detectedIssues[key]['type'] == 'update':
                # update assignee iff ['assignee'] is None
                if updateAssignee == False and 'assignee' in detectedIssues[key]:
                    # if updateAssignee == True, preserve 'assignee' in detectedIssues[key], and fill updatedIssue['fields']['assignee']['name']
                    # if updateAssignee == False, delete 'assignee' in detectedIssues[key], and fill updatedIssue['fields']['assignee']['name']
                    # check updateDetectedDefectsToJiraIssues()
                    del detectedIssues[key]['assignee']
                utils.heavyLogging('commitIssues: LESS_NOTIFICATION and update {}'.format(key))
                detectedIssues[key]["description_streams"] = mergeDict(existedJiraIssue["fields"]["description_streams"], detectedIssues[key]["description_streams"])
            # Temporarily disable 'update_comment' due to RealGPT's performance issues.
            #else:
                # no other updates, only RealGPT comments
            #    if issueHasRealGPTComment(existedJiraIssue) == False:
            #        detectedIssues[key]['type'] = 'update_comment'

            # labels_project should be identical, otherwise...
            if detectedIssues[key]['type'] == "ignore":
                # initialliy triaged as ignore, will not be created as JIRA issue
                utils.lightLogging("commitIssues: identical defect {}".format(key))
            else:
                utils.lightLogging("commitIssues: changed defect {}".format(key))
        else:
            # add
            detectedIssues[key]['type'] = 'add'
            utils.lightLogging('commitIssues: new issue CID {}'.format(key))
            if 'CO-AUTHOR' in jsonGlobal['defects_extra_watcher'] and jsonGlobal['defects_assign_policy'] != 'author':
                # add defects author to JIRA issue watchers
                detectedIssues[key]['co-authors'].append(detectedIssues[key]['assignee'])
                utils.lightLogging('commitIssues: add author({}) to watchers'.format(detectedIssues[key]['assignee']))
        for label_project in detectedIssues[key]["labels_project"]:
            detectedIssues[key]["labels"].append(label_project)
        for label_streams in detectedIssues[key]["labels_streams"]:
            detectedIssues[key]["labels"].append(label_streams)
        for label_security in detectedIssues[key]["labels_security"]:
            detectedIssues[key]["labels"].append(label_security)
        for key_stream in detectedIssues[key]["description_streams"]:
            detectedIssues[key]["description_streams_str"] += detectedIssues[key]["description_streams"][key_stream] + "\n"

def assignJIRAIssue(idOrKey, committer, committerFullname, issueComponent, notifyUser):
    if committer == 'COMPONENT':
        # skip COMPONENT issue
        return
    assignee = dict()
    assignee['name'] = committer
    with open('assignee.json', 'w') as fp:
        json.dump(assignee, fp)
    utils.heavyLogging('assignJIRAIssue: assign {} to {}'.format(idOrKey, committer))
    http_code = jira.jiraAssignIssue(jsonGlobal['site_name'], idOrKey, 'assignee.json', 'assignResult.json')
    if http_code == '400':
        # assign to default assignee or component lead if failed
        with open('componentsMap.json', 'r', encoding='utf-8') as f:
            componentsMap = json.load(f)
        if issueComponent in componentsMap:
            assignee['name'] = componentsMap[issueComponent]['lead']['name']
        else:
            assignee['name'] = jsonGlobal['defects_default_assignee']
        with open('assignee.json', 'w') as fp:
            json.dump(assignee, fp)
        jira.jiraAssignIssue(jsonGlobal['site_name'], idOrKey, 'assignee.json', 'assignResult.json')
        print("Assign issue to {} failed, assign to {}".format(committer, jsonGlobal['defects_default_assignee']))

        comment = dict()
        comment['body'] = "Assign issue to {}({}) failed".format(committer, committerFullname)
        with open('comment.json', 'w') as fp:
            json.dump(comment, fp)
        jira.jiraAddComments(jsonGlobal['site_name'], idOrKey, 'comment.json', notifyUser)

def mergeSummaryDescription(existedSummary, newSummary):
    if existedSummary.startswith('Stream: ') == True:
        summaries = dict()
        lines = existedSummary.splitlines()
        for line in lines:
            if line.startswith('Stream: ') == True:
                stream = line.split()[1]
                summaries[stream] = '{}\n'.format(line)
            else:
                summaries[stream] += '{}\n'.format(line)
        lines = newSummary.splitlines()
        for line in lines:
            if line.startswith('Stream: ') == True:
                stream = line.split()[1]
                summaries[stream] = '{}\n'.format(line)
            else:
                summaries[stream] += '{}\n'.format(line)
        newSummary = ''
        for stream in summaries:
            newSummary += summaries[stream]
    return newSummary

def publishSummary(issueType, extraLabels, publishResult, notifyUser):
    with open('epic.json', 'r', encoding='utf-8') as f:
        epicInfo = json.load(f)
    with open('componentsMap.json', 'r', encoding='utf-8') as f:
        componentsMap = json.load(f)
    hasEPIC = True
    if epicInfo['total'] == 0:
        hasEPIC = False

    covJIRASummary = dict()
    covJIRASummary['fields'] = dict()
    covJIRASummary['fields']['summary'] = 'Build Summary {}'.format(jsonGlobal['coverity_project_name'])
    covJIRASummary['fields']['project'] = dict()
    covJIRASummary['fields']['project']['key'] = jsonGlobal['defects_jira_project']
    covJIRASummary['fields']['labels'] = extraLabels
    covJIRASummary['fields']['labels'].append('COVPRJ:{}'.format(jsonGlobal['coverity_project_name']))
    # TODO: WORKAROUND for CN2SD6 COVNTA JIRA project, ['other', 'common'] maybe insufficient
    for key in componentsMap:
        if key.lower() in ['other', 'common']:
            components = []
            components.append(componentsMap[key])
            covJIRASummary['fields']['components'] = components
            break
    if hasEPIC == True:
        with open('epicKey.json', 'r', encoding='utf-8') as f:
            epicKey = json.load(f)
        with open('epicLinkField.json', 'r', encoding='utf-8') as f:
            epicLinkField = json.load(f)
        covJIRASummary['fields'][epicLinkField['id']] = epicKey['key']
    else:
        if jsonGlobal['coverity_project_name'] != jsonGlobal['defects_issue_epic']:
            covJIRASummary['fields']['labels'].append('EPIC:{}'.format(jsonGlobal['defects_issue_epic']))
    covJIRASummary['fields']['labels'].append('SUMMARY')

    with open('extraFieldsMap.json', 'r', encoding='utf-8') as f:
        fieldsMap = json.load(f)
    for fieldsMapKey in fieldsMap:
        fieldId = fieldsMap[fieldsMapKey]['id']
        fieldValue = fieldsMap[fieldsMapKey]['value']
        covJIRASummary['fields'][fieldId] = fieldValue

    covJIRASummary['fields']['issuetype'] = dict()
    covJIRASummary['fields']['issuetype']['name'] = issueType
    with open('.coverity-url') as f:
        coverityURL = f.read()

    coverityStream = "Multiple"
    if 'buildBranches' not in jsonGlobal or len(jsonGlobal['buildBranches']) == 0:
        # analyze one stream only once
        with open(os.path.join(os.getenv('WORKSPACE'), 'preview-report-committer.json'), 'r', encoding='utf-8') as fpPreviewReportCommitter:
            previewReportCommitter = json.load(fpPreviewReportCommitter)
            coverityStream = previewReportCommitter['coverityStream']
    else:
        # analyze multiple streams
        pass

    covJIRASummary['fields']['description'] = 'Stream: {}\n'.format(coverityStream)
    if 'SDJENKINS_URL' in os.environ:
        # RJIRA
        covJIRASummary['fields']['description'] = '{}Build URL: {}Pipeline_20Reports/'.format(covJIRASummary['fields']['description'], os.getenv('SDJENKINS_URL'))
    elif 'BUILD_URL' in os.environ:
        # OA JIRA
        covJIRASummary['fields']['description'] = '{}Build URL: {}Pipeline_20Reports/'.format(covJIRASummary['fields']['description'], os.getenv('BUILD_URL'))
    maxDescriptionLength = 5000
    unpublishedDesc = ''
    for item in publishResult['unpublished_new']:
        unpublishedDesc += '{}&cid={} \\\\'.format(coverityURL, item)
        if len(unpublishedDesc) > maxDescriptionLength:
            break
    covJIRASummary['fields']['description'] += '\nnew defects: {}\n'.format(publishResult['newCIDs'])
    covJIRASummary['fields']['description'] += 'fixed defects: {}\n'.format(publishResult['fixedCIDs'])
    covJIRASummary['fields']['description'] += 'ignored defects: {}\n'.format(publishResult['ignoredCIDs'])
    covJIRASummary['fields']['description'] += '||operation||detail||\n'
    covJIRASummary['fields']['description'] += '|Created|{} |\n'.format(','.join(publishResult['published_new']))
    covJIRASummary['fields']['description'] += '|Closed(traige)|{} |\n'.format(','.join(publishResult['published_close']))
    covJIRASummary['fields']['description'] += '|Updated(reopen)|{} |\n'.format(','.join(publishResult['published_update']))
    covJIRASummary['fields']['description'] += '|Updated(fixed)|{} |\n'.format(','.join(publishResult['updated_issue']))
    covJIRASummary['fields']['description'] += '|Create(incomplete)|{} |\n'.format(unpublishedDesc)
    covJIRASummary['fields']['description'] += '|Close(incomplete-triage)|{} |\n'.format(','.join(publishResult['unpublished_close']))
    covJIRASummary['fields']['description'] += '|Updated(incomplete-reopen)|{} |\n'.format(','.join(publishResult['unpublished_update']))
    covJIRASummary['fields']['description'] += '|Updated(incomplete-fixed)|{} |\n'.format(','.join(publishResult['unupdated_issue']))
    with open('covJIRASummary.json', 'w') as fp:
        json.dump(covJIRASummary, fp)
    # create or update
    jqlCommand = "project={} and issuetype='{}' and labels='{}' and labels='SUMMARY'".format(jsonGlobal['defects_jira_project'], \
                    issueType, 'COVPRJ:{}'.format(jsonGlobal['coverity_project_name']))
    if hasEPIC == True:
        jqlCommand = jqlCommand + " and 'Epic Link'='{}'".format(epicKey['key'])
    else:
        if jsonGlobal['coverity_project_name'] != jsonGlobal['defects_issue_epic']:
            jqlCommand = jqlCommand + " and labels='EPIC:{}'".format(jsonGlobal['defects_issue_epic'])

    jira.jiraJQLSearch(jsonGlobal['site_name'], jqlCommand, 0, 100, 'summary.json')
    with open('summary.json', 'r', encoding='utf-8') as f:
        summaryInfo = json.load(f)
    if 'errorMessages' in summaryInfo:
        utils.heavyLogging('publishSummary: error search SUMMARY')
    else:
        if summaryInfo['total'] > 0:
            existedSummaryDescription = summaryInfo['issues'][0]['fields']['description']
            covJIRASummary['fields']['description'] = mergeSummaryDescription(existedSummaryDescription, covJIRASummary['fields']['description'])
            with open('covJIRASummary.json', 'w') as fp:
                json.dump(covJIRASummary, fp)
            jira.jiraUpdateIssue(jsonGlobal['site_name'], summaryInfo['issues'][0]['key'], 'covJIRASummary.json', notifyUser)
            summaryKey = summaryInfo['issues'][0]['key']
        else:
            jira.jiraCreateIssue(jsonGlobal['site_name'], 'covJIRASummary.json', 'createSummary.json', notifyUser)
            with open('createSummary.json', 'r', encoding='utf-8') as f:
                createSummary = json.load(f)
            if 'errors' in createSummary:
                utils.heavyLogging('publishSummary: failure, {}'.format(createSummary['errors']))
                sys.exit(1)
            else:
                summaryKey = createSummary['key']
    if 'defects_summary_attachment' in jsonGlobal and jsonGlobal['defects_summary_attachment'] != '':
        if 'WORKSPACE' in os.environ:
            workspace = os.getenv('WORKSPACE')
            if jsonGlobal['defects_summary_attachment'].startswith(workspace) == False:
                jsonGlobal['defects_summary_attachment'] = os.path.join(workspace, jsonGlobal['defects_summary_attachment'])
        jira.jiraUploadAttachment(jsonGlobal['site_name'], summaryKey, jsonGlobal['defects_summary_attachment'], attachMode='REPLACE')

def issueHasRealGPTComment(issue):
    hasRealGPTComment = False
    dstFile = '{}-comments'.format(issue['key'])
    retCode = jira.jiraGetComments(jsonGlobal['site_name'], issue['key'], dstFile)
    if retCode == '200':
        with open(dstFile, 'r', encoding='utf-8') as f:
            comments = json.load(f)
            for comment in comments['comments']:
                if comment['body'].startswith('h1. RealGPT review result'):
                    hasRealGPTComment = True
                    break
    return hasRealGPTComment

def checkRealGPTComment(jiraIssueKey, mergeKey):
    if 'PF_CODEPROMPT_RESULT' not in os.environ or 'PF_CODETEK_COV_ANALYSIS_ADVISE' not in os.environ:
        return
    import codetek, covhtmlparser
    ret = dict()
    if 'buildBranches' in jsonGlobal and len(jsonGlobal['buildBranches']) > 0:
        branches = jsonGlobal['buildBranches']
    else:
        branches = ['PF_NONE']
    utils.heavyLogging('coverityAnalysisAdvise: branches {}'.format(branches))
    for branch in branches:
        if branch == 'PF_NONE':
            previewReport = os.path.join(os.getenv('WORKSPACE'), 'preview-report-committer.json')
        else:
            previewReport = os.path.join(os.getenv('WORKSPACE'), 'preview-report-committer-{}.json'.format(branch))
        with open(previewReport) as fpPreviewReport:
            jsonReport = json.load(fpPreviewReport)
            for cid in jsonReport['defects']:
                if jsonReport['defects'][cid]['mergeKey'] == mergeKey:
                    events = []
                    for event in jsonReport['defects'][cid]['events']:
                        events.append(int(event['lineNumber']))
                    codetek.generateCoverityAnalysisAdvisePrompt(ret, '', mergeKey, events, branch)

    comments = []
    idx = 0
    for key in ret:
        for promptInfo in ret[key]:
            ret = codetek.realgpt(promptInfo['prompt'], '', 'coverity-analysis-advise-full', '')
            outputFile = 'coverityAnalysisAdvise-{}-{}.result'.format(mergeKey, idx)
            with open(outputFile, 'w') as file:
                file.write(ret)
            result = covhtmlparser.coverityAnalysisAdviseParser(outputFile)
            if result['status'] == 'failure':
                # skip invalid analysis result
                continue
            with open(os.path.join(os.getenv('WORKSPACE'), os.getenv('PF_ROOT'), 'templates', 'jira-comment-coverity-advise'), 'r') as fpTemplate:
                tComments = fpTemplate.read()
                if 'BUILD_URL' in os.environ and 'apiproxy' in os.getenv('BUILD_URL'):
                    from html_to_jira.converter import html_to_jira
                    result['coverityAnalysis'] = html_to_jira(result['coverityAnalysis']).replace('{', '\\{').replace('}', '\\}')
                else:
                    result['coverityAnalysis'] = '{{html}}\n{}\n{{html}}'.format(result['coverityAnalysis'])
                comments.append(Template(tComments).safe_substitute(IDX=idx, \
                                                                    FILE=result['filename'], \
                                                                    COVERITY_ANALYSIS_RESULT=result['coverityAnalysis'], \
                                                                    REALGPT_ADVISE=result['advise'], \
                                                                    COMMENT=result['reasoning']))
                idx = idx + 1
        comment = dict()
        comment['body'] = ' \n----\n'.join(comments)
        comment['body'] = 'h1. RealGPT review result \n{}'.format(comment['body'])
        with open('comment-gpt.json', 'w') as fp:
            json.dump(comment, fp)
        jira.jiraAddComments(jsonGlobal['site_name'], jiraIssueKey, 'comment-gpt.json')

def createJIRAIssues(jiraIssuesToCreate, issueType, extraLabels, componentsMap, notifyUser):
    if issueType == 'Sub-task':
        getExistedJIRAIssues(jsonGlobal['site_name'], jsonGlobal['defects_jira_project'], jsonGlobal['defects_issue_type'], 'existedJIRAIssues_Ref.json')
        with open('existedJIRAIssues_Ref.json', 'r', encoding='utf-8') as f:
            existedJIRAIssues = json.load(f)
    result = dict()
    result['newCIDs'] = []
    result['published'] = []
    result['unpublished'] = []
    countLimit = jiraIssuesToCreate['count']
    jsonGlobal['defects_number_limit'] = int(jsonGlobal['defects_number_limit'])
    jsonGlobal['defects_hard_limit'] = int(jsonGlobal['defects_hard_limit'])
    if jsonGlobal['defects_number_limit'] != 0 and countLimit > jsonGlobal['defects_number_limit']:
        countLimit = jsonGlobal['defects_number_limit']
        utils.heavyLogging('createIssuesToJIRA: user defined limit {}'.format(countLimit))

    excludedProjects = ['WIFISDIV']
    if jsonGlobal['defects_jira_project'] in excludedProjects:
        utils.heavyLogging('createIssuesToJIRA: excluded JIRA project {}'.format(jsonGlobal['defects_jira_project']))
    else:
        jqlCommand = "project={} and issuetype='{}' and Status!='Closed' \
                        and labels!='SUMMARY' and labels='COVPRJ:{}'".format(jsonGlobal['defects_jira_project'], issueType, jsonGlobal['coverity_project_name'])
        jira.jiraJQLSearch(jsonGlobal['site_name'], jqlCommand, 0, 0, 'openissues.json')
        with open('openissues.json', 'r', encoding='utf-8') as f:
            openissues = json.load(f)
        utils.heavyLogging('createIssuesToJIRA: open issues {}(COVPRJ:{})'.format(openissues['total'], jsonGlobal['coverity_project_name']))
        quota = max(0, jsonGlobal['defects_hard_limit'] - openissues['total'])
        if countLimit > quota:
            countLimit = quota
            utils.heavyLogging('createIssuesToJIRA: system limit {}'.format(countLimit))

    published = 0
    freeOperations = queryJIRAOperationAll('create_issue')
    for i in range(jiraIssuesToCreate['count']):
        jiraIssueToCreate = jiraIssuesToCreate["issues"][i]
        result['newCIDs'].append(jiraIssueToCreate['cid'])
        if hasMoreJIRAOperations(freeOperations) < 0 or published >= countLimit:
            utils.heavyLogging('createIssuesToJIRA: skip CID {}, no more JIRA operations available/exceeds limit'.format(jiraIssueToCreate['cid']))
            result['unpublished'].append(jiraIssueToCreate['cid'])
            continue
        jiraIssueToCreate['issue']['fields']['labels'] = jiraIssueToCreate['issue']['fields']['labels'] + extraLabels
        jiraIssueToCreate['issue']['fields']['issuetype'] = dict()
        jiraIssueToCreate['issue']['fields']['issuetype']['name'] = issueType
        issueComponent = jiraIssueToCreate["issue"]["component"]
        componentLead = ''
        if issueComponent in componentsMap:
            if 'lead' in componentsMap[issueComponent]:
                componentLead = componentsMap[issueComponent]['lead']['name']
            components = []
            components.append(componentsMap[issueComponent])
            jiraIssueToCreate['issue']['fields']['components'] = components
        if issueType == 'Sub-task':
            for existedJIRAIssue in existedJIRAIssues:
                if existedJIRAIssue['fields']['summary'] == '[{}]'.format(issueComponent):
                    jiraIssueToCreate['issue']['fields']['parent'] = dict()
                    jiraIssueToCreate['issue']['fields']['parent']['key'] = existedJIRAIssue['key']
        if 'defects_extra_description' in jsonGlobal and jsonGlobal['defects_extra_description'] != '':
            jiraIssueToCreate['issue']['fields']['description'] = jiraIssueToCreate['issue']['fields']['description'] + '----\n{}'.format(jsonGlobal['defects_extra_description'])
        if 'defects_issue_reporter' in jsonGlobal and jsonGlobal['defects_issue_reporter'] != '':
            if os.path.isfile('reporter.json'):
                with open('reporter.json', 'r', encoding='utf-8') as f:
                    reporter = json.load(f)
                jiraIssueToCreate['issue']['fields']['reporter'] = reporter
        with open('issueToCreate.json', 'w') as fp:
            json.dump(jiraIssueToCreate['issue'], fp)
        retCreateIssue = jira.jiraCreateIssue(jsonGlobal['site_name'], 'issueToCreate.json', 'createIssue.json', notifyUser)
        # 3 issues per second
        time.sleep(300/1000)
        if retCreateIssue != '201':
            utils.heavyLogging('createIssuesToJIRA: create issue failed {}'.format(jiraIssueToCreate['issue']['fields']['summary']))
            continue
        else:
            utils.heavyLogging('createIssuesToJIRA: create issue success {} ({}/{})'.format(jiraIssueToCreate['issue']['fields']['summary'], i, countLimit))
            published = published + 1
        with open('createIssue.json', 'r', encoding='utf-8') as f:
            createIssue = json.load(f)
        if "errorMessages" not in createIssue:
            issueId = createIssue['key']
            checkRealGPTComment(issueId, jiraIssueToCreate['mergeKey'])
            result['published'].append(issueId)
            if 'assignee' in jiraIssueToCreate and jiraIssueToCreate['assignee'] != '':
                assignJIRAIssue(issueId, jiraIssueToCreate['assignee'], jiraIssueToCreate['assigneeFull'], issueComponent, notifyUser)
            for coAuthor in jiraIssueToCreate['issue']['co-authors']:
                utils.lightLogging('createJIRAIssues: add watcher {}'.format(coAuthor))
                jira.jiraAddWatcher(jsonGlobal['site_name'], issueId, coAuthor)
            if len(jiraIssueToCreate['issue']['co-authors']) > 0 :
                # add a dummy comment here, to notify watcher that he/she has been added to issue watchers
                comment = dict()
                comment['body'] = 'publishIssuesToJIRA: add issue watchers {}'.format(jiraIssueToCreate['issue']['co-authors'])
                with open('comment.json', 'w') as fp:
                    json.dump(comment, fp)
                jira.jiraAddComments(jsonGlobal['site_name'], issueId, 'comment.json')
            # rest api watcher limitation, The account ID of the user. Note that username cannot be used due to privacy changes.
            if jsonGlobal['defects_extra_watcher'] != '':
                for watcher in jsonGlobal['defects_extra_watcher'].split(','):
                    watcher = watcher.strip()
                    if watcher == 'CO-AUTHOR':
                        continue
                    if watcher == 'COMPONENT_LEAD':
                        if componentLead == '':
                            utils.lightLogging('createJIRAIssues: ignore unknown component lead')
                            continue
                        else:
                            watcher = componentLead
                    http_code = jira.jiraAddWatcher(jsonGlobal['site_name'], issueId, watcher)
                    if http_code == '204':
                        utils.heavyLogging('createIssuesToJIRA: {} add watcher {}'.format(issueId, watcher))
                    else:
                        utils.heavyLogging('createIssuesToJIRA: {} add watcher {} failed({})'.format(issueId, watcher, http_code))

            if jiraIssueToCreate['close'] == True:
                # tips: first time "Intentional" or "False Positive", transit to close
                # and no attach available caused by cov-format-error skipped that
                utils.heavyLogging('createIssuesToJIRA: create and close {}'.format(issueId))
                jira.jiraTransitStatus(jsonGlobal['site_name'], issueId, 'Close', "Won't Do", notifyUser)
                published = published - 1
        consumeJIRAOperations(freeOperations)
    commitJIRAOperations(freeOperations, 'create_issue')
    return result

def updateIssue(key, issue, componentsMap, notifyUser):
    issueComponent = issue['component']
    if issueComponent in componentsMap:
        components = []
        components.append(componentsMap[issueComponent])
        issue['fields']['components'] = components
    if 'defects_extra_description' in jsonGlobal and jsonGlobal['defects_extra_description'] != '':
        issue['fields']['description'] = issue['fields']['description'] + '----\n{}'.format(jsonGlobal['defects_extra_description'])
    utils.heavyLogging('updateIssue: update {}'.format(key))
    jira.jiraTransitStatus(jsonGlobal['site_name'], key, 'Reopen', '', notifyUser)
    with open('issueToReopen.json', 'w') as fp:
        json.dump(issue, fp)
    jira.jiraUpdateIssue(jsonGlobal['site_name'], key, 'issueToReopen.json', notifyUser)
    for coAuthor in issue['co-authors']:
        utils.lightLogging('updateIssue: add watcher {}'.format(coAuthor))
        jira.jiraAddWatcher(jsonGlobal['site_name'], key, coAuthor)
    if len(issue['co-authors']) > 0 :
        # add a dummy comment here, to notify watcher that he/she has been added to issue watchers
        comment = dict()
        comment['body'] = 'updateIssue: add issue watchers {}'.format(issue['co-authors'])
        with open('comment.json', 'w') as fp:
            json.dump(comment, fp)
        jira.jiraAddComments(jsonGlobal['site_name'], key, 'comment.json')

def publishIssuesToJIRA():
    jira.checkJIRACredentials()
    with open('componentsMap.json', 'r', encoding='utf-8') as f:
        componentsMap = json.load(f)
    with open('jiraIssuesToClose.json', 'r', encoding='utf-8') as f:
        jiraIssuesToClose = json.load(f)
    with open('jiraIssuesToReopen.json', 'r', encoding='utf-8') as f:
        jiraIssuesToReopen = json.load(f)
    with open('jiraIssuesToCreate.json', 'r', encoding='utf-8') as f:
        jiraIssuesToCreate = json.load(f)

    notifyUser = True
    if 'notify_users' in jsonGlobal and jsonGlobal['notify_users'] == False:
        isAdmin = jira.jiraIsAdministrator(jsonGlobal['site_name'], jsonGlobal['defects_jira_project'])
        if isAdmin == True:
            utils.heavyLogging('publishIssuesToJIRA: disable JIRA rest api notification')
            notifyUser = False
        else:
            utils.heavyLogging('publishIssuesToJIRA: cannot disable JIRA rest api notification')
            sys.exit(1)

    with open('publishResult.json', 'r', encoding='utf-8') as f:
        publishResult = json.load(f)
    publishResult['published_close'] = []
    publishResult['published_update'] = []
    publishResult['published_new'] = []
    publishResult['unpublished_close'] = []
    publishResult['unpublished_update'] = []
    publishResult['unpublished_new'] = []
    publishResult['newCIDs'] = []
    publishResult['ignoredCIDs'] = []
    freeOperations = queryJIRAOperationAll('ALL')
    for i in range(jiraIssuesToClose["count"]):
        if hasMoreJIRAOperations(freeOperations) < 0:
            utils.heavyLogging('publishIssuesToJIRA: skip {}, no more JIRA operations available'.format(jiraIssuesToClose["issues"][i]['issueKey']))
            publishResult['unpublished_close'].append(jiraIssuesToClose["issues"][i]['issueKey'])
            continue
        utils.heavyLogging('publishIssuesToJIRA: close {}'.format(jiraIssuesToClose["issues"][i]['issueKey']))
        publishResult['published_close'].append(jiraIssuesToClose["issues"][i]['issueKey'])
        publishResult['ignoredCIDs'].append(jiraIssuesToClose["issues"][i]['cid'])
        updates = dict()
        updates['fields'] = dict()
        updates['fields']['labels'] = jiraIssuesToClose['issues'][i]['labels']
        with open('updates.json', 'w') as fp:
            json.dump(updates, fp)
        jira.jiraUpdateIssue(jsonGlobal['site_name'], jiraIssuesToClose["issues"][i]['issueId'], 'updates.json', notifyUser)
        jira.jiraTransitStatus(jsonGlobal['site_name'], jiraIssuesToClose["issues"][i]['issueId'], 'Close', "Won't Do", notifyUser)
        consumeJIRAOperations(freeOperations)
    commitJIRAOperations(freeOperations, "update_issue,get_issue_info,do_transitions")

    freeOperations = queryJIRAOperationAll('ALL')
    for key in jiraIssuesToReopen:
        if hasMoreJIRAOperations(freeOperations) < 0:
            utils.heavyLogging('publishIssuesToJIRA: skip {}, no more JIRA operations available'.format(key))
            publishResult['unpublished_update'].append(key)
            continue
        jiraIssueToReopen = jiraIssuesToReopen[key]
        # Temporarily disable 'update_comment' due to RealGPT's performance issues.
        #if 'update_comment_only' in jiraIssueToReopen:
        #    pass
        #else:
        #    updateIssue(key, jiraIssueToReopen, componentsMap, notifyUser)
        updateIssue(key, jiraIssueToReopen, componentsMap, notifyUser)
        checkRealGPTComment(key, jiraIssueToReopen['mergeKey'])
        publishResult['published_update'].append(key)
        consumeJIRAOperations(freeOperations)
    commitJIRAOperations(freeOperations, "get_issue_info,do_transitions,update_issue")

    # prepare issueType, extraLabels
    issueType = 'Issue'
    issueTypes = jira.jiraProjectIssueTypes(jsonGlobal['site_name'], jsonGlobal['defects_jira_project'])
    if 'Issue' not in issueTypes:
        issueType = 'Task'
    utils.heavyLogging('publishIssuesToJIRA: create issue with type {}'.format(issueType))
    extraLabels = []
    if 'defects_extra_labels' in jsonGlobal:
        tokens = jsonGlobal['defects_extra_labels'].split(',')
        for token in tokens:
            extraLabels.append(token)
    utils.heavyLogging('publishIssuesToJIRA: create issue with extra label {}'.format(extraLabels))

    # create JIRA issue
    jiraIssuesToCreateMain = dict()
    jiraIssuesToCreateSubTask = dict()
    jiraIssuesToCreateMain['count'] = 0
    jiraIssuesToCreateSubTask['count'] = 0
    jiraIssuesToCreateMain['issues'] = []
    jiraIssuesToCreateSubTask['issues'] = []
    for issue in jiraIssuesToCreate['issues']:
        if 'subTask' in issue:
            jiraIssuesToCreateSubTask['issues'].append(issue)
            jiraIssuesToCreateSubTask['count'] = jiraIssuesToCreateSubTask['count'] + 1
        else:
            jiraIssuesToCreateMain['issues'].append(issue)
            jiraIssuesToCreateMain['count'] = jiraIssuesToCreateMain['count'] + 1
    resultMain = createJIRAIssues(jiraIssuesToCreateMain, issueType, extraLabels, componentsMap, notifyUser)
    resultSubTask = createJIRAIssues(jiraIssuesToCreateSubTask, 'Sub-task', extraLabels, componentsMap, notifyUser)
    publishResult['unpublished_new'] = resultMain['unpublished'] + resultSubTask['unpublished']
    publishResult['published_new'] = resultMain['published'] + resultSubTask['published']
    publishResult['newCIDs'] = resultMain['newCIDs'] + resultSubTask['newCIDs']

    # publish summary
    with open('publishResult.json', 'w') as fp:
        json.dump(publishResult, fp)
    publishSummary(issueType, extraLabels, publishResult, notifyUser)

def dashboardStatistics():
    statisticsInput = dict()
    if jsonGlobal['site_name'] == 'rjira.rtkbf.com':
        statisticsInput['jiraSite'] = "RJIRA"
    elif jsonGlobal['site_name'] == 'jiraqa.realtek.com':
        statisticsInput['jiraSite'] = "JIRAQA"
    else:
        statisticsInput['jiraSite'] = "JIRA"
    statisticsInput['jiraKey'] = jsonGlobal['defects_jira_project']
    statisticsInput['coverityProject'] = jsonGlobal['coverity_project_name']
    statisticsInput['data'] = dict()

    authPieces = jira.getAuthPieces()
    cmdEnv = dict(os.environ)
    # search all
    jql = 'project={} and labels="COVPRJ:{}" and labels not in (SUMMARY)'.format(jsonGlobal['defects_jira_project'], jsonGlobal['coverity_project_name'])
    cmdPieces = ['curl', '-k', '-s', '-X', 'GET', '--url', \
                    'https://{}/rest/api/2/search?jql={}&startAt=0&maxResults=1'.format(jsonGlobal['site_name'], urllib.parse.quote(jql)), \
                    '-H', 'Accept: application/json', '-o', '{}-{}-all.json'.format(jsonGlobal['defects_jira_project'], jsonGlobal['coverity_project_name'])] + authPieces
    utils.popenWithStdout(cmdPieces, cmdEnv)
    # search resolved/closed
    jql = 'project={} and status in (Resolved, Closed) and labels="COVPRJ:{}" and labels not in (SUMMARY)'.format(jsonGlobal['defects_jira_project'], jsonGlobal['coverity_project_name'])
    cmdPieces = ['curl', '-k', '-s', '-X', 'GET', '--url', \
                    'https://{}/rest/api/2/search?jql={}&startAt=0&maxResults=1'.format(jsonGlobal['site_name'], urllib.parse.quote(jql)), \
                    '-H', 'Accept: application/json', '-o', '{}-{}-fixed.json'.format(jsonGlobal['defects_jira_project'], jsonGlobal['coverity_project_name'])] + authPieces
    utils.popenWithStdout(cmdPieces, cmdEnv)

    with open('{}-{}-all.json'.format(jsonGlobal['defects_jira_project'], jsonGlobal['coverity_project_name']), 'r', encoding='utf-8') as fpAll:
        resultAll = json.load(fpAll)
    with open('{}-{}-fixed.json'.format(jsonGlobal['defects_jira_project'], jsonGlobal['coverity_project_name']), 'r', encoding='utf-8') as fpFixed:
        resultFixed = json.load(fpFixed)
    statisticsInput['data']['all'] = resultAll['total']
    statisticsInput['data']['fixed'] = resultFixed['total']
    print('statisticsInput: {}'.format(statisticsInput))
    with open('statisticsInput.json', 'w') as fp:
        json.dump(statisticsInput, fp, indent=2)
    devopsSite = 'devops.realtek.com'
    if 'BUILD_URL' in os.environ and ('-infra' in os.getenv('BUILD_URL') or 'apiproxy' in os.getenv('BUILD_URL')):
        devopsSite = 'devops-infra.rtkbf.com'
    cmdPieces = ['curl', '-k', '-X', 'POST', '--url', \
                            'https://{}/cicd/jira/coverity-to-jira'.format(devopsSite), \
                            '-H', 'Content-Type: application/json',
                            '-H', 'Accept: application/json', '-d', '@statisticsInput.json']
    utils.popenWithStdout(cmdPieces, cmdEnv)

def updateUndetectedDefectsLabel():
    notifyUser = True
    if 'notify_users' in jsonGlobal and jsonGlobal['notify_users'] == False:
        isAdmin = jira.jiraIsAdministrator(jsonGlobal['site_name'], jsonGlobal['defects_jira_project'])
        if isAdmin == True:
            utils.heavyLogging('publishIssuesToJIRA: disable JIRA rest api notification')
            notifyUser = False
        else:
            utils.heavyLogging('publishIssuesToJIRA: cannot disable JIRA rest api notification')
            sys.exit(1)

    with open('existedJiraIssues_UPDATED.json', 'r', encoding='utf-8') as f:
        jiraIssues = json.load(f)
    with open('jiraIssuesToReopen.json', 'r', encoding='utf-8') as f:
        jiraIssuesToReopen = json.load(f)

    publishResult = dict()
    publishResult['fixedCIDs'] = []
    publishResult['unupdated_issue'] = []
    publishResult['updated_issue'] = []
    freeOperations = queryJIRAOperationAll('ALL')
    for key in jiraIssues:
        hasJIRAOperation = False
        jiraIssue = jiraIssues[key]
        cid = extractCID(jiraIssue['fields']['summary'])
        if len(jiraIssue['fields']['streams_to_remove']) > 0:
            publishResult['fixedCIDs'].append('{}({})'.format(cid, ','.join(jiraIssue['fields']['streams_to_remove'])))
        else:
            # fixed by TRIAGES_TO_CLOSE, not really fixed
            pass
        if hasMoreJIRAOperations(freeOperations) < 0:
            utils.heavyLogging('updateUndetectedDefectsLabel: skip {}, no more JIRA operations available'.format(jiraIssue['key']))
            publishResult['unupdated_issue'].append(jiraIssue['key'])
            continue
        if len(jiraIssue['fields']['streams_to_remove']) > 0:
            jiraIssueId = jiraIssue['id']
            jiraIssue['fields']['labels'] = list(set(jiraIssue['fields']['labels']) - set(jiraIssue['fields']['streams_to_remove']))
            updatedIssue = dict()
            updatedIssue['fields'] = dict()
            updatedIssue['fields']['labels'] = jiraIssue['fields']['labels']

            if jiraIssueId in jiraIssuesToReopen:
                # decription already updated in 'existedJiraIssues_UPDATED.json'
                # update labels only, otherwise, new stream's description would be overwritten
                # (new stream's description is existed in 'existedJiraIssues_UPDATED.json' only)
                utils.heavyLogging('updateUndetectedDefectsLabel: update labels only: {}'.format(jiraIssue['key']))
            else:
                updatedIssue['fields']['description'] = jiraIssue['fields']['description']
                utils.heavyLogging('updateUndetectedDefectsLabel: update labels and description: {}'.format(jiraIssue['key']))

            with open('issueToUpdate.json', 'w') as fp:
                json.dump(updatedIssue, fp)
            jira.jiraUpdateIssue(jsonGlobal['site_name'], jiraIssue['id'], 'issueToUpdate.json', notifyUser)
            publishResult['updated_issue'].append(jiraIssue['key'])
            hasJIRAOperation = True
        # if len(remainStreams) == 0 and key not in detectedIssues:
        if jiraIssue['fields']['toremove'] == True:
            if 'status' in jiraIssue['fields'] and jiraIssue['fields']['status']['name'].lower() == 'closed':
                utils.lightLogging('updateUndetectedDefectsLabel: close {}(closed already)'.format(jiraIssue['key']))
                pass
            else:
                utils.heavyLogging('updateUndetectedDefectsLabel: close {}'.format(jiraIssue['key']))
                jira.jiraTransitStatus(jsonGlobal['site_name'], jiraIssue['id'], 'Close', 'Fixed', notifyUser)
                hasJIRAOperation = True
        if hasJIRAOperation == True:
            consumeJIRAOperations(freeOperations)
    commitJIRAOperations(freeOperations, "update_issue,get_issue_info,do_transitions")
    with open('publishResult.json', 'w') as fp:
        json.dump(publishResult, fp)

def getQuota(userKey, userName):
    today = str(date.today())
    jiraSite = "JIRA"
    if 'jiraqa' in jsonGlobal['site_name']:
        jiraSite = "JIRAQA"
    elif 'rjira' in jsonGlobal['site_name']:
        jiraSite = "RJIRA"

    #if 'BUILD_URL' in os.environ and 'apiproxy' in os.getenv('BUILD_URL'):
    #    if os.path.isfile('/var/jenkins_home/JIRA_QUOTA/{}_{}_{}.json'.format(jiraSite, today, userKey)):
    #        shutil.copy('/var/jenkins_home/JIRA_QUOTA/{}_{}_{}.json'.format(jiraSite, today, userKey), 'quota{}.json'.format(userName))
    #    else:
    #        errorMessage = dict()
    #        with open('quota{}.json'.format(userName), 'w') as fp:
    #            json.dump(errorMessage, fp)
    #else:
    devopsSite = 'devops.realtek.com'
    if 'BUILD_URL' in os.environ and ('-infra' in os.getenv('BUILD_URL') or 'apiproxy' in os.getenv('BUILD_URL')):
        devopsSite = 'devops-infra.rtkbf.com'
    # query dashboard
    cmds = ['curl', '-k', '-s', '-X', 'GET', '--url', \
                    'https://{}/cicd/jira/current-quota?site={}&date={}&userKey={}'.format(devopsSite, jiraSite, today, userKey), \
                    '-H', 'Content-Type: application/json', '-H', 'Accept: application/json', '-o', 'quota{}.json'.format(userName)]
    cmdEnv = dict(os.environ)
    utils.popenWithStdout(cmds, cmdEnv)
    # put quota if empty
    with open('quota{}.json'.format(userName), encoding='utf-8') as fpQuota:
        updateQuota = json.load(fpQuota)
        if 'userKey' not in updateQuota:
            utils.heavyLogging('getQuota: init quota of {}'.format(userName))
            putQuota(userKey, userName, '')
            getQuota(userKey, userName)

def putQuota(userKey, userName, inputFile):
    today = str(date.today())
    jiraSite = "JIRA"
    if 'jiraqa' in jsonGlobal['site_name']:
        jiraSite = "JIRAQA"
    elif 'rjira' in jsonGlobal['site_name']:
        jiraSite = "RJIRA"

    if inputFile == '':
        updateQuota = dict()
        updateQuota['site'] = jiraSite
        updateQuota['userKey'] = userKey
        updateQuota['name'] = userName
        updateQuota['operations'] = []
        emptyOp = dict()
        emptyOp['get_issue_info'] = 0
        updateQuota['operations'].append(emptyOp)
        emptyOp = dict()
        emptyOp['jql_search'] = 0
        updateQuota['operations'].append(emptyOp)
        emptyOp = dict()
        emptyOp['update_issue'] = 0
        updateQuota['operations'].append(emptyOp)
        emptyOp = dict()
        emptyOp['do_transitions'] = 0
        updateQuota['operations'].append(emptyOp)
        emptyOp = dict()
        emptyOp['create_issue'] = 0
        updateQuota['operations'].append(emptyOp)
        updateQuota['date'] = today
        with open('updateQuota.json', 'w') as fp:
            json.dump(updateQuota, fp)
        inputFile = 'updateQuota.json'

    #if 'BUILD_URL' in os.environ and 'apiproxy' in os.getenv('BUILD_URL'):
    #    shutil.copy(inputFile, '/var/jenkins_home/JIRA_QUOTA/{}_{}_{}.json'.format(jiraSite, today, userKey))
    #else:
    devopsSite = 'devops.realtek.com'
    if 'BUILD_URL' in os.environ and ('-infra' in os.getenv('BUILD_URL') or 'apiproxy' in os.getenv('BUILD_URL')):
        devopsSite = 'devops-infra.rtkbf.com'
    cmds = ['curl', '-k', '-s', '-X', 'POST', '--url', \
                        'https://{}/cicd/jira/update-quota'.format(devopsSite), \
                        '-H', 'Content-Type: application/json', \
                        '-H', 'Accept: application/json', '--data', '@{}'.format(inputFile)]
    cmdEnv = dict(os.environ)
    utils.popenWithStdout(cmds, cmdEnv)

def queryJIRAOperation(jiraCredential, specificOp):
    userKey = jiraCredential['key']
    userName = jiraCredential['name']

    getQuota(userKey, userName)
    fpQuota = open('quota{}.json'.format(userName))
    updateQuota = json.load(fpQuota)
    opCounts = []
    for operationInfo in updateQuota['operations']:
        for operation in operationInfo:
            if specificOp == 'ALL':
                opCounts.append(operationInfo[operation])
            else:
                if specificOp == operation:
                    opCounts.append(operationInfo[operation])
    opCountMax = max(opCounts)
    utils.lightLogging('queryJIRAOperation: existed query, {}({})'.format(updateQuota['name'], updateQuota['operations']))
    utils.heavyLogging('queryJIRAOperation: existed query, {}({})'.format(updateQuota['name'], opCountMax))

    remainCount = max(0, jsonGlobal['defects_credentials_limit'] - opCountMax)
    #utils.heavyLogging('queryJIRAOperation: updateQuota remains {}'.format(remainCount))
    return remainCount

def queryJIRAOperationAll(specificOp):
    fpCredentials = open('credentials.json')
    jiraCreds = json.load(fpCredentials)
    freeOperations = []
    for i in range(len(jiraCreds)):
        freeOperation = dict()
        freeOperation['index'] = i
        freeOperation['credentials'] = jiraCreds[i]['name']
        freeOperation['origin'] = queryJIRAOperation(jiraCreds[i], specificOp)
        freeOperation['remain'] = freeOperation['origin']
        freeOperations.append(freeOperation)

    utils.heavyLogging('queryJIRAOperationAll: freeOperations {}'.format(freeOperations))
    return freeOperations

def consumeJIRAOperations(freeOperations):
    for freeOperation in freeOperations:
        if freeOperation['index'] == int(os.getenv('JIRA_CRED_ITE')):
            freeOperation['remain'] = freeOperation['remain'] - 1
            utils.heavyLogging('consumeJIRAOperations: consume {}'.format(os.getenv('JIRA_CRED_ITE')))

def commitJIRAOperations(freeOperations, ops):
    for freeOperation in freeOperations:
        opCount = freeOperation['origin'] - freeOperation['remain']
        if opCount > 0:
            # update dashboard
            fpCredentials = open('credentials.json')
            jiraCreds = json.load(fpCredentials)
            userKey = jiraCreds[freeOperation['index']]['key']
            userName = jiraCreds[freeOperation['index']]['name']
            # query first
            getQuota(userKey, userName)
            fpQuota = open('quota{}.json'.format(userName))
            updateQuota = json.load(fpQuota)
            # then update
            newops = ops.split(',')
            for newop in newops:
                for operation in updateQuota['operations']:
                    if newop in operation:
                        operation[newop] = operation[newop] + opCount
            with open('updateQuota.json', 'w') as fp:
                json.dump(updateQuota, fp)
            putQuota(userKey, userName, 'updateQuota.json')
            utils.heavyLogging('commitJIRAOperations: {}, {}'.format(userName, updateQuota))

    os.environ['JIRA_CRED_ITE'] = os.getenv('JIRA_CRED_ITE')
    envToExport = dict()
    envToExport['JIRA_CRED_ITE'] = os.getenv('JIRA_CRED_ITE')
    with open('env', 'w') as fp:
        for envExport in envToExport:
            fp.write('{}={}\n'.format(envExport, envToExport[envExport]))

def hasMoreJIRAOperations(freeOperations):
    for freeOperation in freeOperations:
        if freeOperation['remain'] > 0:
            utils.heavyLogging('hasMoreJIRAOperations: found avaiable creds {}({}), {}'.format(freeOperation['credentials'], freeOperation['index'], freeOperation['remain']))
            os.environ['JIRA_CRED_ITE'] = str(freeOperation['index'])
            if os.getenv('JIRA_CRED_TYPE') == 'TOKEN':
                os.environ['JIRA_TOKEN'] = os.getenv('JIRA_TOKEN_{}'.format(freeOperation['index']))
            else:
                os.environ['JIRA_USER'] = os.getenv('JIRA_USER_{}'.format(freeOperation['index']))
                os.environ['JIRA_PASSWORD'] = os.getenv('JIRA_PASSWORD_{}'.format(freeOperation['index']))
            return freeOperation['index']

    return -1

def initCredentials(projectKey):
    envToExport = dict()
    if 'JIRA_TOKEN' in os.environ:
        tokenCredentials = True
        os.environ['JIRA_CRED_TYPE'] = 'TOKEN'
        os.environ['JIRA_TOKEN_0'] = os.getenv('JIRA_TOKEN')
        envToExport['JIRA_CRED_TYPE'] = 'TOKEN'
        envToExport['JIRA_TOKEN_0'] = os.getenv('JIRA_TOKEN')
    else:
        tokenCredentials = False
        os.environ['JIRA_CRED_TYPE'] = 'PASSWORD'
        os.environ['JIRA_USER_0'] = os.getenv('JIRA_USER')
        os.environ['JIRA_PASSWORD_0'] = os.getenv('JIRA_PASSWORD')
        envToExport['JIRA_CRED_TYPE'] = 'PASSWORD'
        envToExport['JIRA_USER_0'] = os.getenv('JIRA_USER')
        envToExport['JIRA_PASSWORD_0'] = os.getenv('JIRA_PASSWORD')

    jiraCreds = []
    utils.heavyLogging('initCredentials: credentials 0')
    jiraCred = jira.jiraMyself(jsonGlobal['site_name'], 'myself-{}.json'.format(0))
    if jiraCred['name'] != 'INVALID':
        jiraCreds.append(jiraCred)
        jira.jiraMyPermissions(jsonGlobal['site_name'], projectKey, 0)
    for i in range(20):
        if tokenCredentials == True and 'JIRA_TOKEN_{}'.format(i + 1) in os.environ:
            os.environ['JIRA_TOKEN'] = os.getenv('JIRA_TOKEN_{}'.format(i + 1))
            os.environ['JIRA_TOKEN_{}'.format(i + 1)] = os.getenv('JIRA_TOKEN_{}'.format(i + 1))
            envToExport['JIRA_TOKEN_{}'.format(i + 1)] = os.getenv('JIRA_TOKEN_{}'.format(i + 1))
        elif tokenCredentials == False and 'JIRA_USER_{}'.format(i + 1) in os.environ:
            os.environ['JIRA_USER'] = os.getenv('JIRA_USER_{}'.format(i + 1))
            os.environ['JIRA_PASSWORD'] = os.getenv('JIRA_PASSWORD_{}'.format(i + 1))
            os.environ['JIRA_USER_{}'.format(i + 1)] = os.getenv('JIRA_USER_{}'.format(i + 1))
            os.environ['JIRA_PASSWORD_{}'.format(i + 1)] = os.getenv('JIRA_PASSWORD_{}'.format(i + 1))
            envToExport['JIRA_USER_{}'.format(i + 1)] = os.getenv('JIRA_USER_{}'.format(i + 1))
            envToExport['JIRA_PASSWORD_{}'.format(i + 1)] = os.getenv('JIRA_PASSWORD_{}'.format(i + 1))
        else:
            utils.heavyLogging('initCredentials: invalid jira credentials {}'.format(i + 1))
            break
        utils.heavyLogging('initCredentials: credentials {}'.format(i + 1))
        jiraCred = jira.jiraMyself(jsonGlobal['site_name'], 'myself-{}.json'.format(i + 1))
        if jiraCred['name'] != 'INVALID':
            jiraCreds.append(jiraCred)
            jira.jiraMyPermissions(jsonGlobal['site_name'], projectKey, i + 1)
    if len(jiraCreds) == 0:
        utils.heavyLogging('initCredentials: no valid credentials')
        sys.exit(1)

    if tokenCredentials == True:
        os.environ['JIRA_TOKEN'] = envToExport['JIRA_TOKEN_0']
    else:
        os.environ['JIRA_USER'] = envToExport['JIRA_USER_0']
        os.environ['JIRA_PASSWORD'] = envToExport['JIRA_PASSWORD_0']
    utils.heavyLogging('initCredentials: jira credentials {}'.format(jiraCreds))
    os.environ['JIRA_CRED_ITE'] = '0'
    envToExport['JIRA_CRED_ITE'] = '0'
    with open('credentials.json', 'w') as fp:
        json.dump(jiraCreds, fp)
    with open('env', 'w') as fp:
        for envExport in envToExport:
            fp.write('{}={}\n'.format(envExport, envToExport[envExport]))
    # get reporter info
    if 'defects_issue_reporter' in jsonGlobal and jsonGlobal['defects_issue_reporter'] != '':
        jira.jiraQueryUser(jsonGlobal['site_name'], jsonGlobal['defects_issue_reporter'], 'reporter.json')
        with open('reporter.json', 'r', encoding='utf-8') as f:
            reporter = json.load(f)
            if 'errorMessages' in reporter:
                utils.heavyLogging('initCredentials: invalid reporter {}'.format(jsonGlobal['defects_issue_reporter']))
                sys.exit(-1)

def getRemoteArtifactsCodetekInfo():
    try:
        cmdCurl = sb.Popen(['curl', '-k', '-s', '-X', 'GET', '-u', '{}:{}'.format(os.getenv('SDJENKINS_USER'), os.getenv('SDJENKINS_TOKEN')), \
                    '--url', '{}artifact/codetekInfo.json'.format(os.getenv('SDJENKINS_URL')), \
                    '-o', 'codetekInfo.json'], stdout=sb.PIPE)
        cmdCurl.wait()
    except:
        pass
    try:
        # the HTML result will be returned if the remote does not have codetekInfo
        with open('codetekInfo.json') as f:
            codetekInfo = json.load(f)
    except:
        codetekInfo = dict()
        codetekInfo['function'] = ''
    return codetekInfo

def getRemoteArtifactsParallelInfo():
    cmdCurl = sb.Popen(['curl', '-k', '-s', '-X', 'GET', '-u', '{}:{}'.format(os.getenv('SDJENKINS_USER'), os.getenv('SDJENKINS_TOKEN')), \
                '--url', '{}artifact/parallelInfo.json'.format(os.getenv('SDJENKINS_URL')), \
                '-o', 'remoteParallelInfo.json'], stdout=sb.PIPE)
    cmdCurl.wait()
    utils.heavyLogging('copyRemoteArtifactsParallelInfo: copy {}artifact/parallelInfo.json'.format(os.getenv('SDJENKINS_URL')))
    with open('remoteParallelInfo.json') as f:
        parallelInfo = json.load(f)
    return parallelInfo

def copyRemoteArtifactsFilePattern(targetDir, filePattern, branches):
    # filePattern:
    #  preview-report-committer.json
    #  preview-report-committer-{branch}.json
    #  coverityReport-0.zip
    #  coverityReport-0-{branch}.zip
    if len(branches) == 0:
        branches = ['']
    utils.heavyLogging('copyRemoteArtifactsFilePattern: branches {}'.format(branches))
    for branch in branches:
        if branch == '':
            report = filePattern
        else:
            filename, fileExtension = os.path.splitext(filePattern)
            report = '{}-{}{}'.format(filename, branch, fileExtension)
        cmdCurl = sb.Popen(['curl', '-k', '-s', '-w', '%{http_code}', '-X', 'GET', '-u', '{}:{}'.format(os.getenv('SDJENKINS_USER'), os.getenv('SDJENKINS_TOKEN')), \
                    '--url', '{}artifact/{}'.format(os.getenv('SDJENKINS_URL'), report), \
                    '-o', '{}/{}'.format(targetDir, report)], stdout=sb.PIPE)
        cmdCurl.wait()
        while True:
            http_code = cmdCurl.stdout.readline()
            http_code = bytes.decode(http_code, 'utf-8')
            break
        if http_code == '200':
            utils.heavyLogging('copyRemoteArtifactsFilePattern: got {}/{}'.format(targetDir, report))
            # unzip
            if filePattern == 'coverityReport-0.zip':
                import zipfile
                utils.heavyLogging('copyRemoteArtifactsFilePattern: extract {} to {}'.format(os.path.join(targetDir, report), os.path.join('html', branch)))
                with zipfile.ZipFile(os.path.join(targetDir, report), 'r') as zip_ref:
                    zip_ref.extractall(os.path.join('html', branch))
        else:
            utils.heavyLogging('copyRemoteArtifactsFilePattern: error {}/{}'.format(targetDir, report))
            os.remove(os.path.join(targetDir, report))

def copyRemoteArtifacts(targetDir):
    envs = dict()
    if 'PF_REMOTE_PARALLEL_BUILD' not in os.environ:
        return
    # trigger by remote jenkins job, copy remote artifacts
    codetekInfo = getRemoteArtifactsCodetekInfo()
    if os.getenv('PF_REMOTE_PARALLEL_BUILD') == '1':
        parallelInfo = getRemoteArtifactsParallelInfo()
        branches = parallelInfo['branches']
    else:
        if os.getenv('PF_REMOTE_PARALLEL_BUILD') == '0':
            branches = []
        else:
            # ugly, take PF_REMOTE_PARALLEL_BUILD as BUILD_BRANCH is confused
            branches = [os.getenv('PF_REMOTE_PARALLEL_BUILD')]
    copyRemoteArtifactsFilePattern(targetDir, 'preview-report-committer.json', branches)
    if codetekInfo['function'] == 'coverity-analysis-advise-full':
        copyRemoteArtifactsFilePattern(targetDir, 'coverityReport-0.zip', branches)
        envs['PF_CODEPROMPT_RESULT'] = 'PF_CODEPROMPT_RESULTS'
        envs['PF_CODETEK_COV_ANALYSIS_ADVISE'] = '1'
        # TODO: ugly
        if len(branches) == 0:
            envs['PF_COV_DETAILED_HTML_REPORT_DIR'] = os.path.join(os.getenv('WORKSPACE'), jsonGlobal['WORK_DIR'], 'html', 'detailed')
        else:
            for branch in branches:
                envs['BR{}_PF_COV_DETAILED_HTML_REPORT_DIR'.format(branch)] = os.path.join(os.getenv('WORKSPACE'), jsonGlobal['WORK_DIR'], 'html', branch, 'detailed')
    if 'DECRYPT_KEY' in os.environ:
        copyRemoteArtifactsFilePattern(targetDir, 'encryptToken', [])
        from Crypto.PublicKey import RSA
        from Crypto.Cipher import PKCS1_OAEP
        privateKey = RSA.import_key(open(os.getenv('DECRYPT_KEY')).read())
        cipherRSA = PKCS1_OAEP.new(privateKey)
        plainToken = cipherRSA.decrypt(open('{}/encryptToken'.format(targetDir), 'rb').read())
        plainToken = bytes.decode(plainToken, 'utf-8')
        envs['JIRA_TOKEN'] = plainToken
    with open('env', 'w') as fp:
        for key in envs:
            fp.write('{}={}\n'.format(key, envs[key]))

def updateExcludes():
    if jsonGlobal['defects_assignee_excluded'] == '':
        utils.heavyLogging('updateExcludes: defects_assignee_excluded {}'.format(jsonGlobal['defects_assignee_excluded']))
        return
    utils.makeEmptyDirectory('ldap')
    cmdEnv = dict(os.environ)
    cmdEnv['GIT_SSL_NO_VERIFY'] = 'true'
    cmdGit = sb.Popen(['git', 'clone', 'https://mirror.rtkbf.com/gerrit/sdlc/ldap', \
                        '--depth', '1', 'ldap'], stdout=sb.PIPE, env=cmdEnv)
    cmdGit.wait()

    txt = []
    excludes = jsonGlobal['defects_assignee_excluded'].split(',')
    for exclude in excludes:
        if os.path.isfile('ldap/{}'.format(exclude)):
            fpLdap = open('ldap/{}'.format(exclude), 'r')
            txt = txt + fpLdap.readlines()
            fpLdap.close()
    filePathJIRAExcludes = os.path.join(os.getenv('WORKSPACE'), '{}/scripts/jira_excludes'.format(os.getenv('PF_ROOT')))
    if os.path.isfile(filePathJIRAExcludes):
        fpPredefined = open(filePathJIRAExcludes, 'r')
        txt = txt + fpPredefined.readlines()
        fpPredefined.close()
    fpResult = open(filePathJIRAExcludes, 'w')
    fpResult.writelines(txt)
    fpResult.close()
    logging.debug('All excludes:')
    logging.debug(txt)

def defectsToJIRAIssues(defectsDir):
    jiraIssueKeyCategory = parseExistedJIRAIssues()
    utils.heavyLogging('defectsToJIRAIssues: jiraIssueKeyCategory {}'.format(jiraIssueKeyCategory))
    # var detectedIssues
    if 'buildBranches' not in jsonGlobal or len(jsonGlobal['buildBranches']) == 0:
        parseCoverityDefetcs(defectsDir, 'preview-report-committer.json', 'all', jiraIssueKeyCategory)
    else:
        for buildBranch in jsonGlobal['buildBranches']:
            parseCoverityDefetcs(defectsDir, 'preview-report-committer-{}.json'.format(buildBranch), buildBranch, jiraIssueKeyCategory)
    parseExistedJIRAIssuesUpdateDetectedIssues(jiraIssueKeyCategory)
    with open('detectedIssues_.json', 'w') as fp:
        json.dump(detectedIssues, fp, indent=2)
    for k in list(detectedIssues.keys()):
        if detectedIssues[k]['type'] == "ignore":
            del detectedIssues[k]
    updateDetectedDefectsToJiraIssues()
    with open('existedJiraIssues_PREUPDATED.json', 'w') as fp:
        json.dump(existedJiraIssues, fp)
    for k in list(existedJiraIssues.keys()):
        if len(existedJiraIssues[k]["fields"]["streams_to_remove"]) > 0:
            for stream_to_remove in existedJiraIssues[k]["fields"]["streams_to_remove"]:
                existedJiraIssues[k]["fields"]["labels"].remove(stream_to_remove)
    with open('existedJiraIssues_UPDATED.json', 'w') as fp:
        json.dump(existedJiraIssues, fp)

def validateCoverityProject(configFile, workDir):
    with open(configFile, 'r', encoding='utf-8') as f:
        jsonConfig = json.load(f)
    if jsonGlobal['coverity_project_name'] == '' and (jsonGlobal['defects_to_jira'] == True or jsonGlobal['defects_to_jira'] == 'true'):
        # get coverity_project_name from preview-report-committer.json
        if 'PF_REMOTE_PARALLEL_BUILD' in os.environ and os.getenv('PF_REMOTE_PARALLEL_BUILD') == '1':
            # assume all branches in same coverity project
            with open(os.path.join(workDir, 'remoteParallelInfo.json'), 'r', encoding='utf-8') as f:
                parallelInfo = json.load(f)
            for buildBranch in parallelInfo['branches']:
                reportFile = 'preview-report-committer-{}.json'.format(buildBranch)
        elif 'buildBranches' in jsonConfig and len(jsonConfig['buildBranches']) > 0:
            for buildBranch in jsonConfig['buildBranches']:
                reportFile = 'preview-report-committer-{}.json'.format(buildBranch)
        else:
            reportFile = 'preview-report-committer.json'
        with open(reportFile) as fpPreviewReport:
            jsonPreviewReport = json.load(fpPreviewReport)
        if 'coverityProject' in jsonPreviewReport and jsonPreviewReport['coverityProject'] != '':
            jsonGlobal['coverity_project_name'] = jsonPreviewReport['coverityProject']
            with open(os.path.join(configFile), 'w') as outfile:
                json.dump(jsonGlobal, outfile, indent=2)
            utils.heavyLogging('validateCoverityProject: coverity project {}'.format(jsonGlobal['coverity_project_name']))
        else:
            utils.heavyLogging('validateCoverityProject: coverity project undefined')
            sys.exit(-1)

def validateProjectKey(key, workDir):
    # validate project key
    projectKey = jira.jiraGetProjectKey(jsonGlobal['site_name'], jsonGlobal[key], workDir)
    if projectKey == '':
        utils.heavyLogging('validateProjectKey: invalid project {}'.format(jsonGlobal[key]))
        utils.heavyLogging('validateProjectKey: please check JIRA project, permission or credentials'.format(jsonGlobal[key]))
        sys.exit(-1)
    else:
        jsonGlobal[key] = projectKey
        with open(os.path.join(jsonGlobal['config_file_name']), 'w') as outfile:
            json.dump(jsonGlobal, outfile, indent=2)
        utils.heavyLogging('validateProjectKey: JIRA project key {}({})'.format(jsonGlobal[key], key))

# stageConfig.json: jira configurations
# preview-report-committer.json: defects detected
# issues.json: existed jira issues
def main(argv):
    try:
        opts, args = getopt.getopt(argv[1:], 'i:w:d:f:c:v', ["input=", "work_dir=", "defects_dir=", "config=", "command=", "version"])
    except getopt.GetoptError:
        print('Invalid options')
        sys.exit()

    command = "MAIN"
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
        elif name in ('-f', '--config'):
            configFile = value
        elif name in ('-d', '--defects_dir'):
            defectsDir = os.path.abspath(value)
        elif name in ('-w', '--work_dir'):
            if os.path.exists(value) == False:
                os.mkdir(value)
            workDir = value

    if os.path.isdir(workDir) == False:
        os.makedirs(workDir)
    if command == "FLUSH_LOG":
        logging.basicConfig(filename=os.path.join(workDir, 'covjira.log'), format='%(asctime)s %(levelname)-8s %(message)s', level=logging.DEBUG, filemode='w')
        logging.debug('Flush log {}'.format(os.path.join(workDir, 'covjira.log')))
        sys.exit(0)
    else:
        logging.basicConfig(filename=os.path.join(workDir, 'covjira.log'), format='%(asctime)s %(levelname)-8s %(message)s', level=logging.DEBUG, filemode='a')
    global jsonGlobal
    global detectedIssues
    global existedJiraIssues
    if configFile == "":
        with open(os.path.join(workDir, 'stageConfig.json'), 'r', encoding='utf-8') as f:
            jsonGlobal = json.load(f)
            jsonGlobal['config_file_name'] = 'stageConfig.json'
    else:
        with open(configFile, 'r', encoding='utf-8') as f:
            jsonGlobal = json.load(f)
            jsonGlobal['config_file_name'] = configFile
    f.close()

    if jsonGlobal['site_name'].startswith('http'):
        jsonGlobal['site_name'] = jsonGlobal['site_name'][jsonGlobal['site_name'].index(':') + 3:]
    if jsonGlobal['site_name'].endswith('/'):
        jsonGlobal['site_name'] = jsonGlobal['site_name'][:-1]
    if jsonGlobal['defects_issue_epic'] == "":
        jsonGlobal['defects_issue_epic'] = jsonGlobal['coverity_project_name']

    jsonGlobal['WORK_DIR'] = workDir
    pwd = os.getcwd()
    os.chdir(workDir)

    if command == 'CHECK_ENV':
        # chdir(workDir) already
        utils.checkSingularity('')
    elif command == 'VAL_PROJECT_KEY':
        # validate JIRA project, coverity project
        os.chdir(pwd)
        if jsonGlobal['defects_jira_project'] != '':
            validateProjectKey('defects_jira_project', workDir)
        if jsonGlobal['jira_project'] != '':
            validateProjectKey('jira_project', workDir)
        validateCoverityProject(configFile, workDir)
    elif command == "INIT_CREDENTIALS":
        initCredentials(jsonGlobal['defects_jira_project'])
    elif command == "GET_JIRA_INFO":
        jira.getKeyFields(jsonGlobal['site_name'], jsonGlobal['defects_extra_fields'])
        sys.exit(0)
    elif command == "GET_JIRA_EPIC":
        jira.getEPICKey(jsonGlobal['site_name'], jsonGlobal['defects_jira_project'], jsonGlobal['defects_issue_epic'], autoCreate=False)
        sys.exit(0)
    elif command == "COPY_REMOTE_ARTIFACTS":
        copyRemoteArtifacts(defectsDir)
        sys.exit(0)
    elif command == "UPDATE_EXCLUDES":
        updateExcludes()
        sys.exit(0)
    elif command == "GET_JIRA_ISSUES":
        getExistedJIRAIssues(jsonGlobal['site_name'], jsonGlobal['defects_jira_project'], jsonGlobal['defects_issue_type'], 'existedJiraIssues_RAW.json')
        sys.exit(0)
    elif command == "GET_JIRA_COMPONENT":
        getComponentsMap()
        sys.exit(0)
    elif command == "DEFECTS_TO_JIRA":
        defectsToJIRAIssues(defectsDir)
        sys.exit(0)
    elif command == "PUBLISH":
        publishIssuesToJIRA()
        dashboardStatistics()
        sys.exit(0)
    elif command == "UPDATE_UNDECTED":
        updateUndetectedDefectsLabel()
        sys.exit(0)
    elif command == "MAIN":
        jira.getKeyFields(jsonGlobal['site_name'], jsonGlobal['defects_extra_fields'])
        jira.getEPICKey(jsonGlobal['site_name'], jsonGlobal['defects_jira_project'], jsonGlobal['defects_issue_epic'], autoCreate=False)
        initCredentials(jsonGlobal['defects_jira_project'])
        copyRemoteArtifacts(defectsDir)
        updateExcludes()
        getExistedJIRAIssues(jsonGlobal['site_name'], jsonGlobal['defects_jira_project'], jsonGlobal['defects_issue_type'], 'existedJiraIssues_RAW.json')
        getComponentsMap()
        defectsToJIRAIssues(defectsDir)
        updateUndetectedDefectsLabel()
        publishIssuesToJIRA()
        sys.exit(0)
    else:
        print('Invalid command {}'.format(command))

if __name__ == "__main__":
    main(sys.argv)
