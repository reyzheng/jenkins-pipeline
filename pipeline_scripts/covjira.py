import os, shutil, logging
import getopt, sys
import json
import re
import subprocess as sb
import jira, utils

TRIAGES_TO_CLOSE = ['Intentional', 'False Positive', 'Ignore']
# label contains spaces which is invalid.
LABELS_TO_CLOSE = ['Intentional', 'FalsePositive', 'Ignore']
PF_ROOT = ""
jsonGlobal = dict()

criticalFields = []
# all existed issues
# existedJiraIssues[CID]
# or
# existedJiraIssues[CID + component]
existedJiraIssues = dict()
detectedIssues = dict()
issuesAtSpecificStream = dict()

def extractCID(summary):
    tokens = re.split('\[|\]| ', summary)
    return tokens[1]

def getExistedJIRAIssues(jiraSite, jiraProject, jiraIssueType, jiraLabel):
    with open('epicKey.json') as f:
        epicKey = json.load(f)
    issueTypes = jira.jiraProjectIssueTypes(jiraSite, jiraProject)
    if jiraIssueType == 'Issue' and 'Issue' in issueTypes:
        jqlCommand = "project={} and (issuetype='Task' or issuetype='Issue') and 'Epic Link'='{}'".format(jiraProject, epicKey['key'])
    else:
        jqlCommand = "project={} and issuetype='Task' and 'Epic Link'='{}'".format(jiraProject, epicKey['key'])
    if jiraLabel != '':
        jqlCommand = jqlCommand + ' and labels=\'{}\''.format(jiraLabel)
    
    issues = []
    utils.heavyLogging('getExistedJIRAIssues: {}'.format(jqlCommand))
    for i in range(100):
        jira.jiraJQLSearch(jiraSite, jqlCommand, i*1000, 1000, 'issues.json')
        with open('issues.json') as f:
            ret = json.load(f)
        issues = issues + ret['issues']
        if len(ret['issues']) < 1000:
            break
    with open("issues.json", "w") as outfile:
        json.dump(issues, outfile)

def getComponentsMap():
    jira.checkJIRACredentials()
    authPieces = jira.getAuthPieces()
    cmdCurl = sb.Popen(['curl', '-s', '-X', 'GET', '--url', \
                        'https://{}/rest/api/2/project/{}/components'.format(jsonGlobal['site_name'], jsonGlobal['defects_jira_project']), \
                        '-H', 'Accept: application/json', '-o', 'components.json'] + authPieces, stdout=sb.PIPE)
    cmdCurl.wait()
    resultMap = dict()
    with open('components.json') as f:
        components = json.load(f)
    for component in components:
        resultMap[component['name']] = component
    with open("componentsMap.json", "w") as outfile:
        json.dump(resultMap, outfile)

def updateDetectedDefectsToJiraIssues():
    with open('epicKey.json') as f:
        epicKey = json.load(f)
    with open('extraFieldsMap.json') as f:
        fieldsMap = json.load(f)
    with open('componentsMap.json') as f:
        componentsMap = json.load(f)
    with open('epicLinkField.json') as f:
        field = json.load(f)
    epicLinkFieldId = field["id"]

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
        if jsonGlobal['defects_assign_policy'] == "component" and issueComponent not in componentsMap:
            print("JIRA: skip issue cid: {} (unknown componet {})".format(key, issueComponent))
            continue
        if detectedIssue["type"] == "update":
            print("JIRA: update issue cid: {}".format(key))
            if detectedIssue['triage'] in TRIAGES_TO_CLOSE:
                jiraIssuesToClose["count"] = jiraIssuesToClose["count"] + 1
                issueToClose = dict()
                issueToClose['key'] = detectedIssue['issueKey']
                newLabels = []
                existedLabels = detectedIssue['labels']
                for existedLabel in existedLabels:
                    if existedLabel not in LABELS_TO_CLOSE:
                        newLabels.append(existedLabel)
                newLabels.append(detectedIssue['triage'].replace(' ', ''))
                issueToClose['labels'] = newLabels
                utils.lightLogging('updateDetectedDefectsToJiraIssues: close issue {}'.format(issueToClose['key']))
                utils.lightLogging('updateDetectedDefectsToJiraIssues: existed labels {}'.format(existedLabels))
                utils.lightLogging('updateDetectedDefectsToJiraIssues: new labels {}'.format(newLabels))
                jiraIssuesToClose["issues"].append(issueToClose)
            else:
                updatedIssue = dict()
                updatedIssue['component'] = issueComponent
                updatedIssue['fields'] = dict()
                updatedIssue['fields']['summary'] = detectedIssue['summary']
                updatedIssue['fields']['labels'] = detectedIssue['labels']
                updatedIssue['fields']['description'] = detectedIssue['description_url'] + detectedIssue['description_streams_str']
                for fieldsMapKey in fieldsMap:
                    fieldId = fieldsMap[fieldsMapKey]['id']
                    if fieldsMap[fieldsMapKey]['value'] is None:
                        fieldValue = ""
                    else:
                        fieldValue = fieldsMap[fieldsMapKey]['value']
                    updatedIssue['fields'][fieldId] = fieldValue
                jiraIssuesToReopen[detectedIssue["issueKey"]] = updatedIssue
        else:
            logging.debug("updateDetectedDefectsToJiraIssues: create issue cid: {}".format(key))
            jiraIssue = dict()
            jiraIssue['component'] = issueComponent
            jiraIssue['fields'] = dict()
            jiraIssue['fields']['project'] = dict()
            jiraIssue['fields']['project']['key'] = jsonGlobal['defects_jira_project']
            jiraIssue['fields']['summary'] = detectedIssue["summary"]
            jiraIssue['fields']['description'] = detectedIssue["description_url"] + "\n" + detectedIssue["description_streams_str"]
            jiraIssue['fields'][epicLinkFieldId] = epicKey['key']
            jiraIssue['fields']['labels'] = detectedIssue["labels"]
            #jiraIssue['fields']['issuetype'] = dict()
            #jiraIssue['fields']['issuetype']['name'] = jsonGlobal['defects_issue_type']
            for fieldsMapKey in fieldsMap:
                fieldId = fieldsMap[fieldsMapKey]['id']
                fieldValue = fieldsMap[fieldsMapKey]['value']
                jiraIssue['fields'][fieldId] = fieldValue
            jiraIssueToCreate = dict()
            jiraIssueToCreate["issue"] = jiraIssue
            jiraIssueToCreate["close"] = False
            if detectedIssue['triage'] in TRIAGES_TO_CLOSE:
                jiraIssue['fields']['labels'].append(detectedIssue['triage'].replace(' ', ''))
                jiraIssueToCreate["close"] = True
            else:
                assignee = ""
                assigneeFull = ""
                if jsonGlobal['defects_assign_policy'] == "default":
                    assignee = jsonGlobal['defects_default_assignee']
                elif jsonGlobal['defects_assign_policy'] == "author":
                    assignee = detectedIssue["assignee"]
                    assigneeFull = detectedIssue["assigneefull"]
                elif jsonGlobal['defects_assign_policy'] == "component":
                    # component mode: assignee is temporally assigned, component lead will assign issue to specified user
                    # therefore, add component lead to watcher also.
                    if issueComponent in componentsMap:
                        assignee = componentsMap[issueComponent]['lead']['name']
                    else:
                        assignee = jsonGlobal['defects_default_assignee']
                jiraIssueToCreate["assignee"] = assignee
                jiraIssueToCreate["assigneeFull"] = assigneeFull
            jiraIssuesToCreate["issues"].append(jiraIssueToCreate)
            jiraIssuesToCreate["count"] = jiraIssuesToCreate["count"] + 1
        count = count + 1
        if jsonGlobal['defects_number_limit'] != 0 and count >= jsonGlobal['defects_number_limit']:
            break
    with open('jiraIssuesToClose.json', 'w') as fp:
        json.dump(jiraIssuesToClose, fp)
    with open('jiraIssuesToReopen.json', 'w') as fp:
        json.dump(jiraIssuesToReopen, fp)
    with open('jiraIssuesToCreate.json', 'w') as fp:
        json.dump(jiraIssuesToCreate, fp)

def parseExistedIssues():
    with open('issues.json') as f:
        jsonIssues = json.load(f)
    for jiraIssue in jsonIssues:
        summary = jiraIssue["fields"]["summary"]
        CID = extractCID(summary)
        mapKey = CID
        if jsonGlobal["defects_assign_policy"] == "component":
            if "CN3SD8" in jsonGlobal["defects_customization"]:
                # For CN3SD8, parse component from summary 
                tokens = re.split('\[|\]| ', summary)
                mapKey += tokens[5]
            else:
                if (len(jiraIssue["fields"]["components"]) > 0):
                    mapKey += jiraIssue["fields"]["components"][0]["name"]
                else:
                    # intentionally fail for invalid component configuration
                    mapKey += "ERR_UNKNOWN"
                    logging.debug('parseExistedIssues: invalid component {}'.format(CID))
        existedJiraIssues[mapKey] = jiraIssue

# For RSIPCAM special usage
def reconstructDefects(defectReportObject):
    defectsByComponet = dict()
    defects = defectReportObject["defects"]
    for key in defects:
        CID = key
        issueComponent = defects[key]["components"][0]
        # init a new defect by issueComponent
        if issueComponent not in defectsByComponet:
            #defectsByComponet[issueComponent] = defects[key]
            defectsByComponet[issueComponent] = dict()
            defectsByComponet[issueComponent]["triage"] = defects[key]["triage"]
            defectsByComponet[issueComponent]["components"] = defects[key]["components"]
            defectsByComponet[issueComponent]["events"] = []
        # modify ["triage"]["classification"]
        if defects[key]["triage"]["classification"] != "False Positive" and defects[key]["triage"]["classification"] != "Intentional":
            # mark Unclassified if any issue in the component not FP/Intentional
            defectsByComponet[issueComponent]["triage"]["classification"] = "Unclassified"
            event = dict()
            # take CID, subcategoryShortDescription as filePathname, functionDisplayName
            event["filePathname"] = CID
            event["functionDisplayName"] = defects[key]["subcategoryShortDescription"]
            defectsByComponet[issueComponent]["events"].append(event)
    return defectsByComponet

def transExtraSummary(pattern, issue):
    summary = ''
    pieces = re.split('( |\]|\[)', pattern)
    for piece in pieces:
        if piece != '':
            if piece.startswith('key:'):
                key = piece[4:]
                if key in issue:
                    summary = summary + issue[key]
                else:
                    utils.lightLogging('transExtraSummary: invalid pattern {}'.format(key))
            else:
                summary = summary + piece
    return summary

def updateDetectedDefects(reportPath, report, suffix):
    report = os.path.join(reportPath, report)
    if not os.path.isfile(report):
        utils.heavyLogging("updateDetectedDefects: invalid defects report {}".format(report))
        return
    utils.heavyLogging("updateDetectedDefects: got defects report {}".format(report))
    with open(report) as f:
        defectReportObject = json.load(f)
    issuesAtSpecificStream[defectReportObject["coverityStream"]] = []
    if defectReportObject["assignPolicy"] == "component":
        defects = reconstructDefects(defectReportObject)
    else:
        defects = defectReportObject["defects"]

    fileExcludes = '{}/scripts/jira_excludes'.format(PF_ROOT)
    jiraExcludes = []
    if os.path.exists(fileExcludes):
        logging.debug('Read excludes list: {}'.format(fileExcludes))
        with open(fileExcludes) as fp:
            while True:
                line = fp.readline()
                if not line:
                    break
                jiraExcludes.append(line.strip())
    logging.debug('Got excludes list: ')
    logging.debug(jiraExcludes)

    cidsIgnored = []
    for key in defects:
        issue = defects[key]
        CID = key
        mapKey = CID
        # TODO: sorry, we deal with the first coverity component only
        issueComponent = issue["components"][0]
        if jsonGlobal["defects_assign_policy"] == "component":
            mapKey += issueComponent

        if "CN3SD8" in jsonGlobal["defects_customization"]:
            sdkVersion = jsonGlobal["coverity_project_name"].split("_")
            preConfig = defectReportObject["coverityStream"][defectReportObject["coverityStream"].index(sdkVersion[1]) + len(sdkVersion[1]) + 1:]
            issueSummary = "[{}][{}][{}][{}] {}".format(key, sdkVersion[1], issueComponent, preConfig, issue["subcategoryShortDescription"])
        elif defectReportObject["assignPolicy"] == "component":
            issueSummary = "[{}]".format(key)
        else:
            if 'defects_extra_summary' in jsonGlobal and jsonGlobal['defects_extra_summary'] != '':
                extraSummary = transExtraSummary(jsonGlobal['defects_extra_summary'], issue)
                issueSummary = "[{}]{} {}".format(key, extraSummary, issue["subcategoryShortDescription"])
            else:
                issueSummary = "[{}] {}".format(key, issue["subcategoryShortDescription"])

        host = defectReportObject["host"]
        port = defectReportObject["port"]
        if defectReportObject["assignPolicy"] == "component":
            issueURL = "http://{}:{}/query/defects.htm?project={}\n".format(host, port, jsonGlobal["coverity_project_name"])
        else:
            issueURL = "http://{}:{}/query/defects.htm?project={}&cid={}\n".format(host, port, jsonGlobal["coverity_project_name"], CID)
        issueDescription = "coverity stream {}, snapshot: {}".format(defectReportObject["coverityStream"], defectReportObject["snapshot"])
        if "MORE_DESCRIPTION" in jsonGlobal["defects_customization"]:
            if defectReportObject["snapshotVersion"] != "null" or defectReportObject["snapshotDescription"] != "null":
                if defectReportObject["snapshotVersion"] != "null":
                    issueDescription += ", version: {}".format(defectReportObject["snapshotVersion"])
                if defectReportObject["snapshotDescription"] != "null":
                    issueDescription += ", description: {}".format(defectReportObject["snapshotDescription"])

        if defectReportObject["assignPolicy"] == "component":
            for event in issue["events"]:
                file = event["filePathname"]
                func = event["functionDisplayName"]
                issueDescription += "\n{}: {}".format(file, func)
        else:
            for event in issue["events"]:
                file = event["filePathname"]
                func = event["functionDisplayName"]
                line = event["lineNumber"]
                if "MORE_DESCRIPTION" in jsonGlobal["defects_customization"]:
                    issueDescription += "\n{}: {}: {}, author: {}, committer: {}".format(file, func, line, event["author"], event["committer"])
                else:
                    issueDescription += "\n{}: {}: {}".format(file, func, line)
            issueDescription += ", status: open"

        labels_project = []
        labels_streams = []
        labels_security = []
        # For CN3SD4, append coverity_project_name to label if necessary
        if jsonGlobal["coverity_project_name"] != jsonGlobal["defects_issue_epic"]:
            labels_project.append("COVPRJ:" + jsonGlobal["coverity_project_name"])
        labels_streams.append(defectReportObject["coverityStream"])
        if "impact" in issue:
            labels_security.append("Impact:{}".format(issue["impact"]))
        if "cwe" in issue and issue["cwe"] == True:
            labels_security.append("CWE_Top_25")
        if "owasp" in issue and issue["owasp"] == True:
            labels_security.append("OWASP_Top_10")
        if "cvss" in issue:
            labels_security.append("CVSS:{}".format(issue["cvss"]))
        if "severity" in issue and issue["severity"] != "":
            labels_security.append("Severity:{}".format(issue["severity"].replace(" ", "")))

        # create or update jira issue
        if defectReportObject["assignPolicy"] == "component":
            headCommitter = "COMPONENT"
            headCommitterFull = "COMPONENT"
        else:
            headCommitter = ''
            if defectReportObject["assignPolicy"] == 'committer':
                for event in issue["events"]:
                    if event['committer'] != '':
                        headCommitter = event["committer"]
                        headCommitterFull = event["committerfull"]
                        break
            else:
                for event in issue["events"]:
                    if event['committer'] != '':
                        headCommitter = event["author"]
                        headCommitterFull = event["authorfull"]
                        break
            # headCommitter == "" -> caused by non-realtek user or invalid file path
            # check covanalyze.py defectsAnalyzer()
            if headCommitter == '':
                headCommitter = jsonGlobal['defects_default_assignee']
                headCommitterFull = '{}@realtek.com'.format(headCommitter)
                utils.heavyLogging('updateDetectedDefects: empty headCommitter {}, assign to {}'.format(mapKey, headCommitter))

        if ("IGNORE_EXCLUDES" in jsonGlobal["defects_customization"] and 
                jsonGlobal["defects_assign_policy"] == "author"):
            excludedCommitter = False
            if headCommitter in jiraExcludes:
                excludedCommitter = True
            if excludedCommitter == True:
                print('Exclude committer {}({})'.format(CID, headCommitter))
                cidsIgnored.append(CID)
                continue

        # move issue to issuesAtSpecificStream iff author found
        issuesAtSpecificStream[defectReportObject["coverityStream"]].append(mapKey)
        if mapKey in detectedIssues:
            print("JIRA: update defect({}): {}".format(defectReportObject["coverityStream"], mapKey))
        else:
            print("JIRA: create defect({}): {}".format(defectReportObject["coverityStream"], mapKey))
            detectedIssues[mapKey] = dict()
            #detectedIssues[mapKey]["description_stream"] = set()
            detectedIssues[mapKey]["labels"] = []
            detectedIssues[mapKey]["labels_project"] = []
            detectedIssues[mapKey]["labels_streams"] = []
            detectedIssues[mapKey]["labels_security"] = []
            detectedIssues[mapKey]["description_streams"] = dict()
            detectedIssues[mapKey]["description_streams_str"] = ""
        detectedIssues[mapKey]["summary"] = issueSummary
        detectedIssues[mapKey]["description_url"] = issueURL
        #detectedIssues[mapKey]["description_stream"].add(issueDescription)
        for label_project in labels_project:
            detectedIssues[mapKey]["labels_project"].append(label_project)
        for label_streams in labels_streams:
            detectedIssues[mapKey]["labels_streams"].append(label_streams)
        for label_security in labels_security:
            detectedIssues[mapKey]["labels_security"].append(label_security)
        coverity_stream = re.split(',| ', issueDescription)[2]
        detectedIssues[mapKey]["description_streams"][coverity_stream] = issueDescription
        detectedIssues[mapKey]["assignee"] = headCommitter
        detectedIssues[mapKey]["assigneefull"] = headCommitterFull
        detectedIssues[mapKey]["triage"] = issue["triage"]["classification"]
        detectedIssues[mapKey]["action"] = issue["triage"]["action"]
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
        covuser = data["username"]
        covpass = data["key"]
        cmdCurl = sb.Popen(['curl', '-s', '-X', 'PUT', '--url', \
                    'http://{}:{}/api/v2/issues/triage?locale=en_us&triageStoreName={}'.format(os.getenv('PF_COV_HOST'), os.getenv('PF_COV_PORT'), jsonGlobal['coverity_project_name']), \
                    '-H', 'Content-Type: application/json', '-H', 'Accept: application/json', \
                    '--user', '{}:{}'.format(covuser, covpass), '-d', '@ignored-payload-{}'.format(suffix)], stdout=sb.PIPE)
        cmdCurl.wait()
        print("JIRA: triage defects(ignored-payload) ignored")
        print(cidsIgnored)

def mergeDict(existed, detected):
    mergedDict = dict()
    for key_stream in existed:
        mergedDict[key_stream] = existed[key_stream]
    for key_stream in detected:
        mergedDict[key_stream] = detected[key_stream]

    return mergedDict

def commitIssues():
    # existedJiraIssues: issues.json
    # detectedIssues: preview-report-committer-${BRANCH}.json
    # parse existed issues
    for key in existedJiraIssues:
        existedJiraIssue = existedJiraIssues[key]
        existedJiraIssue["fields"]["labels_project"] = []
        existedJiraIssue["fields"]["labels_streams"] = []
        existedJiraIssues[key]["fields"]["streams_to_remove"] = []
        existedJiraIssues[key]["fields"]["toremove"] = "false"
        existedJiraIssue["fields"]["labels_security"] = []
        for label in existedJiraIssue["fields"]["labels"]:
            #if label == jsonGlobal["coverity_project_name"]:
            if label.startswith("COVPRJ:"):
                existedJiraIssue["fields"]["labels_project"].append(label)
            elif (label == "CWE_Top_25" or
                    label == "OWASP_Top_10" or 
                    label.startswith("Impact:") or
                    label.startswith("CVSS:") or
                    label.startswith("Severity:")):
                existedJiraIssue["fields"]["labels_security"].append(label)
            else:
                existedJiraIssue["fields"]["labels_streams"].append(label)
        existedJiraIssue["fields"]["description_streams"] = dict()
        description = existedJiraIssue["fields"]["description"]
        count = 0
        description_stream = ""
        coverity_stream = ""
        for line in description.splitlines():
            if count == 0:
                description_url = line
                # skip description_url
            elif line.startswith("coverity stream "):
                if description_stream != "":
                    existedJiraIssue["fields"]["description_streams"][coverity_stream] = description_stream
                description_stream = line
                coverity_stream = re.split(',| ', description_stream)[2]
            elif description_stream != "":
                description_stream += "\n" + line
            count = count + 1
        if description_stream != "":
            existedJiraIssue["fields"]["description_streams"][coverity_stream] = description_stream
        #print("description_streams: ")
        #print((existedJiraIssue["fields"]["description_streams"]))

        # compute if issues resolved at specific stream
        # and re-construct description
        streams = existedJiraIssue["fields"]["labels_streams"]
        existedJiraIssue["fields"]["description"] = description_url + "\n"
        for stream in existedJiraIssue["fields"]["description_streams"]:
            if stream in issuesAtSpecificStream and key not in issuesAtSpecificStream[stream]:
                # the coverity stream is analyzed this time, and not found
                if stream in streams:
                    existedJiraIssues[key]["fields"]["streams_to_remove"].append(stream)
                    print("Issue resolved {}({})".format(key, stream))
                if stream in existedJiraIssue["fields"]["description_streams"]:
                    # stupid code here, to handle endswith neither 'open' or 'fixed'
                    if existedJiraIssue["fields"]["description_streams"][stream].endswith(', status: open'):
                        existedJiraIssue["fields"]["description_streams"][stream] = existedJiraIssue["fields"]["description_streams"][stream][:-14]
                    elif existedJiraIssue["fields"]["description_streams"][stream].endswith(', status: fixed'):
                        existedJiraIssue["fields"]["description_streams"][stream] = existedJiraIssue["fields"]["description_streams"][stream][:-15]
                    existedJiraIssue["fields"]["description_streams"][stream] += ", status: fixed"
            existedJiraIssue["fields"]["description"] += existedJiraIssue["fields"]["description_streams"][stream] + "\n"
        # check if remains unfixed streams
        remainStreams = []
        for label in existedJiraIssues[key]["fields"]["labels"]:
            #if label == jsonGlobal["coverity_project_name"]:
            if label.startswith("COVPRJ:"):
                pass
            elif (label == "CWE_Top_25" or
                    label == "OWASP_Top_10" or
                    str(label).startswith("Impact:") or
                    str(label).startswith("CVSS:") or
                    str(label).startswith("Severity:")):
                pass
            else:
                if label not in existedJiraIssues[key]["fields"]["streams_to_remove"]:
                    remainStreams.append(label)
        if len(remainStreams) == 0 and key not in detectedIssues:
            #print("Issue toremoved {}", key)
            existedJiraIssues[key]["fields"]["toremove"] = True
            #print("remove "+key)

    # issues required to add or update
    for key in detectedIssues:
        if key in existedJiraIssues:
            print("JIRA: compare with existed {}".format(key))
            existedJiraIssue = existedJiraIssues[key]
            # parse summary
            summary = existedJiraIssue["fields"]["summary"]
            # parse description
            description = existedJiraIssue["fields"]["description"]
            #description_url = description.partition('\n')[0]
            #count = 0
            #description_stream_arr = []
            #description_stream = ""
            #for line in description.splitlines():
            #    if count == 0:
            #        description_url = line
            #    elif line.startswith("coverity stream "):
            #        if description_stream != "":
            #            description_stream_arr << description_stream
            #        description_stream = line
            #    elif description_stream != "":
            #        description_stream += line
            # update or ignore
            detectedIssues[key]["type"] = "ignore"
            detectedIssues[key]["issueKey"] = existedJiraIssue["id"]
            detectedIssues[key]["component"] = ""
            # TODO: necessary to apply existed componet?
            if (len(existedJiraIssue["fields"]["components"]) > 0):
                detectedIssues[key]["component"] = existedJiraIssue["fields"]["components"][0]["name"]
            detectedIssues[key]["labels"] = existedJiraIssue["fields"]["labels"]
            detectedIssues[key]["description"] = existedJiraIssue["fields"]["description"]
            if detectedIssues[key]["summary"] != summary:
                print("JIRA: summary differ")
                detectedIssues[key]["type"] = "update"
            # CN3SD4 multiple projects in one epic, remove this rule
            #if detectedIssues[key]["description_url"].strip() != description_url.strip():
            #    print("description_url differ")
            #    detectedIssues[key]["type"] = "update"
            if set(detectedIssues[key]["labels_security"]).issubset(existedJiraIssue["fields"]["labels_security"]) == False:
                print("JIRA: labels_security differ")
                detectedIssues[key]["type"] = "update"
                detectedIssues[key]["labels_security"] = list(dict.fromkeys(existedJiraIssue["fields"]["labels_security"] + detectedIssues[key]["labels_security"]))
            if set(detectedIssues[key]["labels_streams"]).issubset(existedJiraIssue["fields"]["labels_streams"]) == False:
                print("JIRA: labels_streams differ")
                detectedIssues[key]["type"] = "update"
                detectedIssues[key]["labels_streams"] = list(dict.fromkeys(existedJiraIssue["fields"]["labels_streams"] + detectedIssues[key]["labels_streams"]))
            if set(detectedIssues[key]["labels_project"]).issubset(existedJiraIssue["fields"]["labels_project"]) == False:
                print("JIRA: labels_project differ")
                detectedIssues[key]["type"] = "update"
                detectedIssues[key]["labels_project"] = list(dict.fromkeys(existedJiraIssue["fields"]["labels_project"] + detectedIssues[key]["labels_project"]))
            # Mark FP/Intentional to update to reopen
            if detectedIssues[key]['triage'] in TRIAGES_TO_CLOSE:
                if "close" not in existedJiraIssue["fields"]["status"]["name"].lower():
                    print("JIRA: close FP/Int./Ignore {}".format(key))
                    detectedIssues[key]["type"] = "update"
            else:
                # Reopen closed/resolved issues
                issueStatus = existedJiraIssue["fields"]["status"]["name"].lower()
                if "close" in issueStatus or "resolved" in issueStatus:
                    detectedIssues[key]["type"] = "update"
            if "LESS_NOTIFICATION" not in jsonGlobal["defects_customization"]:
                # comparison is trivial, would be diff. always caused by snapshotid
                #if set(detectedIssues[key]["description_streams"]).issubset(existedJiraIssue["fields"]["description_streams"]) == False:
                print("JIRA: labels_description differ")
                detectedIssues[key]["type"] = "update"
                detectedIssues[key]["description_streams"] = mergeDict(existedJiraIssue["fields"]["description_streams"], detectedIssues[key]["description_streams"])
            else:
                # "LESS_NOTIFICATION" in jsonGlobal["defects_customization"]:
                if detectedIssues[key]["type"] == "update":
                    logging.debug('commitIssues: LESS_NOTIFICATION and update {}'.format(key))
                    detectedIssues[key]["description_streams"] = mergeDict(existedJiraIssue["fields"]["description_streams"], detectedIssues[key]["description_streams"])
            # labels_project should be identical, otherwise...
            if detectedIssues[key]["type"] == "ignore":
                logging.debug("JIRA: identical defect {}".format(key))
            else:
                logging.debug("JIRA: changed defect {}".format(key))
        else:
            # add
            detectedIssues[key]["type"] = "add"
            print("JIRA: new issue {}".format(key))
        for label_project in detectedIssues[key]["labels_project"]:
            detectedIssues[key]["labels"].append(label_project)
        for label_streams in detectedIssues[key]["labels_streams"]:
            detectedIssues[key]["labels"].append(label_streams)
        for label_security in detectedIssues[key]["labels_security"]:
            detectedIssues[key]["labels"].append(label_security)
        #if jsonGlobal["coverity_project_name"] != jsonGlobal["defects_issue_epic"]:
        #    print ("244")
        #    detectedIssues[key]["labels"].append(jsonGlobal["coverity_project_name"])
        for key_stream in detectedIssues[key]["description_streams"]:
            detectedIssues[key]["description_streams_str"] += detectedIssues[key]["description_streams"][key_stream] + "\n"


def updateIssueComponents(issueId, components):
    updatedIssue = dict()
    updatedIssue['fields'] = dict()
    updatedIssue['fields']['components'] = components
    with open('updatedIssue.json', 'w') as fp:
        json.dump(updatedIssue, fp)
    jira.jiraUpdateIssue(jsonGlobal['site_name'], issueId, 'updatedIssue.json')

def assignJIRAIssue(idOrKey, committer, committerFullname):
    assignee = dict()
    assignee['name'] = committer
    with open('assignee.json', 'w') as fp:
        json.dump(assignee, fp)
    http_code = jira.jiraAssignIssue(jsonGlobal['site_name'], idOrKey, 'assignee.json', 'assignResult.json')
    if http_code == '400':
        assignee['name'] = jsonGlobal['defects_default_assignee']
        with open('assignee.json', 'w') as fp:
            json.dump(assignee, fp)
        # assign to default assignee if failed
        jira.jiraAssignIssue(jsonGlobal['site_name'], idOrKey, 'assignee.json', 'assignResult.json')
        print("Assign issue to {} failed, assign to {}".format(committer, jsonGlobal['defects_default_assignee']))

        comment = dict()
        comment['body'] = "Assign issue to {}({}) failed".format(committer, committerFullname)
        with open('comment.json', 'w') as fp:
            json.dump(comment, fp)
        jira.jiraAddComments(jsonGlobal['site_name'], idOrKey, 'comment.json')

def publishIssuesToJIRA():
    jira.checkJIRACredentials()
    with open('componentsMap.json') as f:
        componentsMap = json.load(f)
    with open('jiraIssuesToClose.json') as f:
        jiraIssuesToClose = json.load(f)
    with open('jiraIssuesToReopen.json') as f:
        jiraIssuesToReopen = json.load(f)
    with open('jiraIssuesToCreate.json') as f:
        jiraIssuesToCreate = json.load(f)

    for i in range(jiraIssuesToClose["count"]):
        utils.heavyLogging('publishIssuesToJIRA: close {}'.format(jiraIssuesToClose["issues"][i]))

        updates = dict()
        updates['fields'] = dict()
        updates['fields']['labels'] = jiraIssuesToClose['issues'][i]['labels']
        with open('updates.json', 'w') as fp:
            json.dump(updates, fp)
        jira.jiraUpdateIssue(jsonGlobal['site_name'], jiraIssuesToClose["issues"][i]['key'], 'updates.json')

        jira.jiraTransitStatus(jsonGlobal['site_name'], jiraIssuesToClose["issues"][i]['key'], "Close", "Won't Do")
    for key in jiraIssuesToReopen:
        jiraIssueToReopen = jiraIssuesToReopen[key]
        issueComponent = jiraIssueToReopen["component"]
        jira.jiraTransitStatus(jsonGlobal['site_name'], key, "Reopen", "")
        with open('issueToReopen.json', 'w') as fp:
            json.dump(jiraIssueToReopen, fp)
        http_code = jira.jiraUpdateIssue(jsonGlobal['site_name'], key, 'issueToReopen.json')
        if http_code == '204':
            if issueComponent in componentsMap:
                components = []
                components.append(componentsMap[issueComponent])
                updateIssueComponents(key, components)

    issueType = 'Issue'
    issueTypes = jira.jiraProjectIssueTypes(jsonGlobal['site_name'], jsonGlobal['defects_jira_project'])
    if 'Issue' not in issueTypes:
        issueType = 'Task'
    utils.heavyLogging('publishIssuesToJIRA: create issue with type {}'.format(issueType))
    for i in range(jiraIssuesToCreate['count']):
        jiraIssueToCreate = jiraIssuesToCreate["issues"][i]
        jiraIssueToCreate['issue']['fields']['issuetype'] = dict()
        jiraIssueToCreate['issue']['fields']['issuetype']['name'] = issueType
        issueComponent = jiraIssueToCreate["issue"]["component"]
        with open('issueToCreate.json', 'w') as fp:
            json.dump(jiraIssueToCreate['issue'], fp)
        retCreateIssue = jira.jiraCreateIssue(jsonGlobal['site_name'], 'issueToCreate.json', 'createIssue.json')
        if retCreateIssue != '201':
            utils.heavyLogging('publishIssuesToJIRA: create issue failed {}'.format(jiraIssueToCreate['issue']['fields']['summary']))
            continue
        with open('createIssue.json') as f:
            createIssue = json.load(f)
        if "errorMessages" not in createIssue:
            issueId = createIssue['key']
            if issueComponent in componentsMap:
                components = []
                components.append(componentsMap[issueComponent])
                updateIssueComponents(issueId, components)
            if 'assignee' in jiraIssueToCreate and jiraIssueToCreate["assignee"] != "":
                assignJIRAIssue(issueId, jiraIssueToCreate["assignee"], jiraIssueToCreate["assigneeFull"])
            if jsonGlobal['defects_extra_watcher'] != "":
                watchers = jsonGlobal['defects_extra_watcher'].split(',')
                for watcher in watchers:
                    authPieces = jira.getAuthPieces()
                    cmdCurl = sb.Popen(['curl', '-s', '-X', 'POST', '--url', \
                                        'https://{}/rest/api/2/issue/{}/watchers'.format(jsonGlobal['site_name'], issueId), \
                                        '-H', 'Content-Type: application/json', \
                                        '-H', 'Accept: application/json', '--data', '"{}"'.format(watcher)] + authPieces, stdout=sb.PIPE)
                    cmdCurl.wait()
            if jiraIssueToCreate["close"] == True:
                # tips: first time "Intentional" or "False Positive", transit to close
                # and no attach available caused by cov-format-error skipped that
                utils.heavyLogging('publishIssuesToJIRA: create and close {}'.format(issueId))
                jira.jiraTransitStatus(jsonGlobal['site_name'], issueId, "Close", "Won't Do")

def updateUndetectedDefectsLabel():
    with open('existedJiraIssues.json') as f:
        jiraIssues = json.load(f)
    with open('jiraIssuesToReopen.json') as f:
        jiraIssuesToReopen = json.load(f)
    for key in jiraIssues:
        jiraIssue = jiraIssues[key]
        if len(jiraIssue['fields']['streams_to_remove']) > 0:
            jiraIssueId = jiraIssue['id']
            jiraIssue['fields']['labels'] = list(set(jiraIssue['fields']['labels']) - set(jiraIssue['fields']['streams_to_remove']))
            updatedIssue = dict()
            updatedIssue['fields'] = dict()
            updatedIssue['fields']['labels'] = jiraIssue['fields']['labels']
            if jiraIssueId in jiraIssuesToReopen:
                # decription already updated in 'existedJiraIssues.json'
                # update labels only, otherwise, new stream's description would be overwritten
                # (new stream's description is existed in 'existedJiraIssues.json' only)
                logging.debug('Update labels only: {}'.format(key))
            else:
                updatedIssue['fields']['description'] = jiraIssue['fields']['description']
                logging.debug('Update labels and description: {}'.format(key))
            with open('issueToUpdate.json', 'w') as fp:
                json.dump(updatedIssue, fp)
            jira.jiraUpdateIssue(jsonGlobal['site_name'], jiraIssue['id'], 'issueToUpdate.json')
        if jiraIssue['fields']['toremove'] == True:
            logging.debug('updateUndetectedDefectsLabel: close {}'.format(jiraIssue['id']))
            jira.jiraTransitStatus(jsonGlobal['site_name'], jiraIssue['id'], "Close", "Fixed")

def copyRemoteArtifacts(targetDir):
    if 'PF_REMOTE_PARALLEL_BUILD' not in os.environ:
        return
    # trigger by remote jenkins job, copy remote artifacts
    if os.getenv('PF_REMOTE_PARALLEL_BUILD') == '1':
        cmdCurl = sb.Popen(['curl', '-s', '-X', 'GET', '-u', '{}:{}'.format(os.getenv('SDJENKINS_USER'), os.getenv('SDJENKINS_TOKEN')), \
                    '--url', '{}artifact/parallelInfo.json'.format(os.getenv('SDJENKINS_URL')), \
                    '-o', 'remoteParallelInfo.json'], stdout=sb.PIPE)
        cmdCurl.wait()
        utils.heavyLogging('copyRemoteArtifacts: copy {}artifact/parallelInfo.json'.format(os.getenv('SDJENKINS_URL')))
        f = open('remoteParallelInfo.json')
        parallelInfo = json.load(f)
        #jsonGlobal['buildBranches'] = []
        utils.heavyLogging('copyRemoteArtifacts: branches {}'.format(parallelInfo["branches"]))
        for buildBranch in parallelInfo["branches"]:
            #jsonGlobal['buildBranches'].append(buildBranch)
            reportFile = 'preview-report-committer-{}.json'.format(buildBranch)
            utils.heavyLogging('copyRemoteArtifacts: reportFile preview-report-committer-{}.json'.format(buildBranch))
            cmdCurl = sb.Popen(['curl', '-s', '-w', '%{http_code}', '-X', 'GET', '-u', '{}:{}'.format(os.getenv('SDJENKINS_USER'), os.getenv('SDJENKINS_TOKEN')), \
                        '--url', '{}artifact/{}'.format(os.getenv('SDJENKINS_URL'), reportFile), \
                        '-o', '{}/{}'.format(targetDir, reportFile)], stdout=sb.PIPE)
            cmdCurl.wait()
            while True:
                http_code = cmdCurl.stdout.readline()
                http_code = bytes.decode(http_code, 'utf-8')
                break
            if http_code == '200':
                utils.heavyLogging('copyRemoteArtifacts: got {}/{}'.format(targetDir, reportFile))
            else:
                utils.heavyLogging('copyRemoteArtifacts: error {}/{}'.format(targetDir, reportFile))
                os.remove(os.path.join(targetDir, reportFile))
        f.close()
    else:
        reportFile = 'preview-report-committer.json'
        cmdCurl = sb.Popen(['curl', '-s', '-X', 'GET', '-u', '{}:{}'.format(os.getenv('SDJENKINS_USER'), os.getenv('SDJENKINS_TOKEN')), \
                        '--url', '{}artifact/{}'.format(os.getenv('SDJENKINS_URL'), reportFile), \
                        '-o', '{}/{}'.format(targetDir, reportFile)], stdout=sb.PIPE)
        cmdCurl.wait()

def updateExcludes():
    if jsonGlobal['defects_assignee_excluded'] == '':
        utils.heavyLogging('updateExcludes: defects_assignee_excluded {}'.format(jsonGlobal['defects_assignee_excluded']))
        return
    if os.path.exists('ldap'):
        shutil.rmtree('ldap')
    os.makedirs('ldap')
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
    if os.path.isfile('{}/scripts/jira_excludes'.format(PF_ROOT)):
        fpPredefined = open('{}/scripts/jira_excludes'.format(PF_ROOT), 'r')
        txt = txt + fpPredefined.readlines()
        fpPredefined.close()
    fpResult = open('{}/scripts/jira_excludes'.format(PF_ROOT), 'w')
    fpResult.writelines(txt)
    fpResult.close()
    logging.debug('All excludes:')
    logging.debug(txt)

def defectsToIssues(defectsDir):
    parseExistedIssues()
    if 'buildBranches' not in jsonGlobal or len(jsonGlobal['buildBranches']) == 0:
        updateDetectedDefects(defectsDir, 'preview-report-committer.json', 'all')
    else:
        for buildBranch in jsonGlobal["buildBranches"]:
            updateDetectedDefects(defectsDir, 'preview-report-committer-{}.json'.format(buildBranch), buildBranch)
    commitIssues()
    with open('detectedIssues_.json', 'w') as fp:
        json.dump(detectedIssues, fp)
    for k in list(detectedIssues.keys()):
        if detectedIssues[k]["type"] == "ignore":
            del detectedIssues[k]
    updateDetectedDefectsToJiraIssues()
    with open('existedJiraIssues_.json', 'w') as fp:
        json.dump(existedJiraIssues, fp)
    for k in list(existedJiraIssues.keys()):
        if len(existedJiraIssues[k]["fields"]["streams_to_remove"]) > 0:
            for stream_to_remove in existedJiraIssues[k]["fields"]["streams_to_remove"]:
                existedJiraIssues[k]["fields"]["labels"].remove(stream_to_remove)
    with open('existedJiraIssues.json', 'w') as fp:
        json.dump(existedJiraIssues, fp)

# stageConfig.json: jira configurations
# preview-report-committer.json: defects detected
# issues.json: existed jira issues
def main(argv):
    try:
        opts, args = getopt.getopt(argv[1:], 'i:r:w:d:f:c:v', ["input=", "pf_root=", "work_dir=", "defects_dir=", "config=", "command=", "version"])
    except getopt.GetoptError:
        print('Invalid options')
        sys.exit()

    command = "MAIN"
    configFile = ''
    inputFile = ''
    defectsDir = '.'
    workDir = os.getcwd()
    global PF_ROOT
    for name, value in opts:
        if name in ('-v', '--version'):
            print("0.1")
            sys.exit(0)
        elif name in ('-c', '--command'):
            # override if --user
            command = value
        elif name in ('-i', '--input'):
            inputFile = value
        elif name in ('-r', '--pf_root'):
            PF_ROOT = os.path.abspath(value)
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
        logging.basicConfig(filename=os.path.join(workDir, 'covjira.log'), level=logging.DEBUG, filemode='w')
        logging.debug('Flush log {}'.format(os.path.join(workDir, 'covjira.log')))
        sys.exit(0)
    else:
        logging.basicConfig(filename=os.path.join(workDir, 'covjira.log'), level=logging.DEBUG, filemode='a')
    global jsonGlobal
    global detectedIssues
    global existedJiraIssues
    if configFile == "":
        with open(os.path.join(workDir, 'stageConfig.json')) as f:
            jsonGlobal = json.load(f)
            jsonGlobal['config_file_name'] = 'stageConfig.json'
    else:
        with open(configFile) as f:
            jsonGlobal = json.load(f)
            jsonGlobal['config_file_name'] = configFile
    f.close()

    if jsonGlobal['defects_issue_epic'] == "":
        jsonGlobal['defects_issue_epic'] = jsonGlobal['coverity_project_name']
    pwd = os.getcwd()
    os.chdir(workDir)
    # TODO: extract site name

    if command == "VAL_PROJECT_KEY":
        os.chdir(pwd)
        # validate project key
        projectKey = jira.jiraGetProjectKey(jsonGlobal['site_name'], jsonGlobal['defects_jira_project'])
        if projectKey == '':
            utils.heavyLogging('main: invalid project {}'.format(jsonGlobal['defects_jira_project']))
        else:
            jsonGlobal['defects_jira_project'] = projectKey
            with open(os.path.join(configFile), "w") as outfile:
                json.dump(jsonGlobal, outfile, indent=2)
            utils.heavyLogging('main: JIRA project key {}'.format(jsonGlobal['defects_jira_project']))
    elif command == "GET_JIRA_INFO":
        jira.getKeyFields(jsonGlobal['site_name'], jsonGlobal['defects_extra_fields'])
        sys.exit(0)
    elif command == "GET_JIRA_EPIC":
        jira.getEPICKey(jsonGlobal['site_name'], jsonGlobal['defects_jira_project'], jsonGlobal['defects_issue_epic'])
        sys.exit(0)
    elif command == "COPY_REMOTE_ARTIFACTS":
        copyRemoteArtifacts(defectsDir)
        sys.exit(0)
    elif command == "UPDATE_EXCLUDES":
        updateExcludes()
        sys.exit(0)
    elif command == "GET_JIRA_ISSUES":
        getExistedJIRAIssues(jsonGlobal['site_name'], jsonGlobal['defects_jira_project'], jsonGlobal['defects_issue_type'], '')
        sys.exit(0)
    elif command == "GET_JIRA_COMPONENT":
        getComponentsMap()
        sys.exit(0)
    elif command == "DEFECTS_TO_JIRA":
        defectsToIssues(defectsDir)
        sys.exit(0)
    elif command == "PUBLISH":
        publishIssuesToJIRA()
        sys.exit(0)
    elif command == "UPDATE_UNDECTED":
        updateUndetectedDefectsLabel()
        sys.exit(0)
    elif command == "MAIN":
        jira.getKeyFields(jsonGlobal['site_name'], jsonGlobal['defects_extra_fields'])
        jira.getEPICKey(jsonGlobal['site_name'], jsonGlobal['defects_jira_project'], jsonGlobal['defects_issue_epic'])
        copyRemoteArtifacts(defectsDir)
        updateExcludes()
        getExistedJIRAIssues(jsonGlobal['site_name'], jsonGlobal['defects_jira_project'], jsonGlobal['defects_issue_type'], '')
        getComponentsMap()
        defectsToIssues(defectsDir)
        publishIssuesToJIRA()
        updateUndetectedDefectsLabel()
        sys.exit(0)
    else:
        print('Invalid command {}'.format(command))

if __name__ == "__main__":
    main(sys.argv)