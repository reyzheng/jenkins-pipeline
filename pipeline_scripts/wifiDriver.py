import json, re, sys, os
import jira, utils

jiraSite = 'jira.realtek.com'
# CN3SD4: WIFISDIV
# CM2SD6: DHCCOVERIT
jiraProject = 'WIFISDIV '
#jiraProject = 'SD8COVB'
#jiraProject = 'PCCOV'
# [Coverity] g6_wifi_driver WIFISDIV-921
# [Coverity] rtk_wifi_driver WIFISDIV-1091
# CM2SD6_Morbius DHCCOVERIT-3
epicKey = 'WIFISDIV-921'

def extractCID(summary):
    tokens = re.split(r'\[|\]| ', summary)
    return tokens[1]

def remove_first_line(text):
    """
    Removes the first line from a multi-line string.
    
    Args:
        text (str): The input string containing multiple lines
        
    Returns:
        str: The string with the first line removed
    """
    # Split the string into lines
    lines = text.splitlines(keepends=True)
    
    # If there are no lines, return empty string
    if not lines:
        return ""
    
    # Join all lines except the first one
    return ''.join(lines[1:])

def queryCoverity():
    covProjects = ['CN3SD4_g6_wifi_driver.trunk', 'CN3SD4_g6_wifi_driver.015', 'CN3SD4_g6_wifi_driver.019', 'CN3SD4_g6_wifi_driver.test', \
                   'CN3SD8_USDK231', 'CN3WD4_formal019',
                   'CN3SD4_rtk_wifi_driver.trunk', 'CN3SD4_g6_wifi_driver.release@ce_core_2_24_0', 'CN3SD4_g6_wifi_driver.release@ce_core_2_25_0']
    for covProject in covProjects:
        covQuery = dict()
        covQuery['filters'] = []
        covQuery['columns'] = ["cid", "mergeKey"]
        matcher = dict()
        matcher['class'] = 'Project'
        matcher['name'] = covProject
        matcher['type'] = 'nameMatcher'
        filter = dict()
        filter['columnKey'] = 'project'
        filter['matchMode'] = 'oneOrMoreMatch'
        filter['matchers'] = [matcher]
        covQuery['filters'].append(filter)
        with open('covQuery.json', 'w') as fp:
            json.dump(covQuery, fp, indent=2)
        cmd = ['curl', '-s', '-X', 'POST', \
                'http://172.21.15.146:8080/api/v2/issues/search?includeColumnLabels=true&rowCount=-1&locale=en_us', \
                '-H', 'Content-Type: application/json', \
                '-H', 'Accept: application/json', \
                '--user', 'admin:covadmin', '--data', '@covQuery.json', '-o', 'covResult.json']

# get jira issues
def getJIRAIssues():
    cidMap = dict()

    issues = []
    #jqlCommand = "project={} and (issuetype='Task' or issuetype='Issue') and 'Epic Link'='{}' and Status='Closed'".format(jiraProject, epicKey)
    jqlCommand = "project={} and (issuetype='Task' or issuetype='Issue') and 'Epic Link'='{}' \
                    and resolution='Unresolved'".format(jiraProject, epicKey)
    #jqlCommand = "project={} and (issuetype='Task' or issuetype='Issue') AND resolution = Unresolved".format(jiraProject)
    for i in range(200):
        jira.jiraJQLSearch(jiraSite, jqlCommand, i*1000, 1000, 'issues.json')
        with open('issues.json') as f:
            ret = json.load(f)
        issues = issues + ret['issues']
        if len(ret['issues']) < 1000:
            break
    print(len(issues))

    for issue in issues:
        streams = []
        for label in issue['fields']['labels']:
            if label.startswith("COVPRJ:"):
                pass
            elif (label == "CWE_Top_25" or
                    label == "OWASP_Top_10" or 
                    label.startswith("Impact:") or
                    label.startswith("CVSS:") or
                    label.startswith("Severity:")):
                pass
            else:
                streams.append(label)

        missed = []        
        mismatch = False
        for stream in streams:
            if stream not in issue['fields']['description']:
                missed.append(stream)
                mismatch = True

        if mismatch:
            print(issue['key'])
            print(missed)
            print()
    
        #updatedIssue = dict()
        #updatedIssue['fields'] = dict()
        #updatedIssue['fields']['labels'] = newLabels
        #with open('updatedIssue.json', 'w') as fp:
        #    json.dump(updatedIssue, fp)
        #jira.jiraUpdateIssue(jiraSite, issue['key'], 'updatedIssue.json')
        #if hasStreamLabel == False:
        #    print('close {}'.format(issue['key']))
        #    jira.jiraTransitStatus(jiraSite, issue['key'], 'Close', '')

    sys.exit(1)
    print(len(issues))
    errorKeys = []
    unknownKeys = []
    for issue in issues:
        CID = extractCID(issue['fields']['summary'])
        if CID.isnumeric() == False:
            #print('error {}'.format(issue['key']))
            continue
        if issue['fields']['description'].startswith('coverity links:') == False and \
            issue['fields']['description'].startswith('http://172.21.15.146:8080') == False:
            print('error {}'.format(issue['key']))
            unknownKeys.append(issue['key'])
            continue

        if CID not in cidMap:
            #print('error totalRows {}'.format(issue['key']))
            errorKeys.append(issue['key'])
            continue
        #print('mergeKey {}'.format(covResult['rows'][0][0]['value']))
        updatedIssue = dict()
        updatedIssue['fields'] = dict()
        updatedIssue['fields']['description'] = 'mergeKey:{}\n'.format(cidMap[CID]) + issue['fields']['description']
        with open('updatedIssue.json', 'w') as fp:
            json.dump(updatedIssue, fp)
        print('Update', issue['key'])
        #jira.jiraUpdateIssue(jiraSite, issue['key'], 'updatedIssue.json')
    # TODO: to close
    print("error ", errorKeys)
    print("unknowns ", unknownKeys)
    #for errorKey in errorKeys:
    #    jira.jiraTransitStatus(jiraSite, errorKey, 'Close', '')

def checkClosed():
    with open('closed.json') as f:
        jiraIssues = json.load(f)
    for jiraIssue in jiraIssues:
        hasStreamLabel = False
        for label in jiraIssue['fields']['labels']:
            if label.startswith("COVPRJ:"):
                pass
            elif (label == "CWE_Top_25" or
                    label == "OWASP_Top_10" or 
                    label.startswith("Impact:") or
                    label.startswith("CVSS:") or
                    label.startswith("Severity:")):
                pass
            else:
                hasStreamLabel = True
        if hasStreamLabel == True:
            print('Still has stream label', jiraIssue['key'])

def checkNonClosed():
    with open('non-closed.json') as f:
        jiraIssues = json.load(f)
    for jiraIssue in jiraIssues:
        hasStreamLabel = False
        for label in jiraIssue['fields']['labels']:
            if label.startswith("COVPRJ:"):
                pass
            elif (label == "CWE_Top_25" or
                    label == "OWASP_Top_10" or 
                    label.startswith("Impact:") or
                    label.startswith("CVSS:") or
                    label.startswith("Severity:")):
                pass
            else:
                hasStreamLabel = True
        if hasStreamLabel == False:
            print('Has no stream label', jiraIssue['key'])

def checkNonClosedStreamProject():
    with open('non-closed.json') as f:
        jiraIssues = json.load(f)
    for jiraIssue in jiraIssues:
        hasProjLabel = False
        hasOtherProjLabel = False
        hasStreamLabel = False
        for label in jiraIssue['fields']['labels']:
            if label == "COVPRJ:CN3SD4_g6_wifi_driver.019":
                hasProjLabel = True
            elif label.startswith("COVPRJ:"):
                hasOtherProjLabel = True
            elif "019" in label:
                hasStreamLabel = True
        if hasOtherProjLabel == False:
            if hasProjLabel != hasStreamLabel:
                print('Project/stream label not match', jiraIssue['key'])

def updateDesc():
    with open('non-closed.json') as f:
        jiraIssues = json.load(f)
    for jiraIssue in jiraIssues:
        lines = jiraIssue['fields']['description'].splitlines()

        urlDesc = ''
        streamDesc = dict()
        hasToModify = False
        for line in lines:
            if line == '':
                continue
            if line.startswith('http:'):
               urlDesc = line 
            else:
                if line.startswith('coverity stream CM2SD6_Morbius_ATV'):
                    hasToModify = True
                    line = line.replace("coverity stream CM2SD6_Morbius_ATV", "coverity stream CM2SD6_Morbius_GTV")
                if line.startswith('coverity stream '):
                    tokens = line.split()
                    streamDesc[tokens[2]] = line + '\n'
                else:
                    streamDesc[tokens[2]] = streamDesc[tokens[2]] + line + '\n'
        if hasToModify == True:
            desc = urlDesc + "\n"
            for key in streamDesc:
                desc = desc + streamDesc[key]

            updatedIssue = dict()
            updatedIssue['fields'] = dict()
            updatedIssue['fields']['description'] = desc
            with open('updatedIssue.json', 'w') as fp:
                json.dump(updatedIssue, fp)
            print('Update', jiraIssue['key'])
            jira.jiraUpdateIssue(jiraSite, jiraIssue['id'], 'updatedIssue.json')

def addURLDesc():
    with open('non-closed.json') as f:
        jiraIssues = json.load(f)
    for jiraIssue in jiraIssues:
        lines = jiraIssue['fields']['description'].splitlines()

        cid = ''
        remainDesc = ''
        for line in lines:
            if line == '':
                continue
            if line.startswith('http:') or line.startswith('[http:'):
                cid = line[line.rindex('=')+1:]
            else:
                remainDesc = remainDesc + line + '\n'
        if cid == '':
            print('addURLDesc: skip {}(summary)'.format(jiraIssue['key']), flush=True)
            continue
        if cid.endswith(']'):
            cid = cid[:-1]

        projects = []
        labels = jiraIssue['fields']['labels']
        for label in labels:
            if label.startswith('COVPRJ:'):
                tokens = label.split(':')
                projects.append(tokens[1])

        if len(projects) <= 1:
            print('addURLDesc: skip {}(single covproject)'.format(jiraIssue['key']), flush=True)
            continue
        urlDesc = 'coverity links:\n'
        urlDesc += '||project||link||\n'
        for project in projects:
            urlDesc += '||{}||[http://172.21.15.146:8080/query/defects.htm?project={}&cid={}|http://172.21.15.146:8080/query/defects.htm?project={}&cid={}]||\n'.format(project, project, cid, project, cid)
        fullDesc = urlDesc + remainDesc

        updatedIssue = dict()
        updatedIssue['fields'] = dict()
        updatedIssue['fields']['description'] = fullDesc
        with open('updatedIssue.json', 'w') as fp:
            json.dump(updatedIssue, fp)
        if jiraIssue['key'] == 'WIFISDIV-1835':
            continue
        print('Update', jiraIssue['key'], cid)
        #jira.jiraUpdateIssue(jiraSite, jiraIssue['id'], 'updatedIssue.json', notifyUsers=False)

getJIRAIssues()


#checkClosed()
#checkNonClosed()
#checkNonClosedStreamProject()

#updateDesc()
#addURLDesc()