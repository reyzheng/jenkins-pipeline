import json, re
import sys, getopt
import os, logging, glob
import subprocess as sb
import utils, jira

def parseReport(failuremode, maxDefectsCount, noDefect):
    maxDefectsCount = int(maxDefectsCount)
    noDefect = int(noDefect)

    fp = open('parsed.html', 'r')
    lines = fp.readlines()
    fp.close()

    defectsCount = 0
    projectName = ""
    fetchProjectName = False
    fetchDuration = False
    testDuration = 0.0
    pattern = re.compile("^<a href=\"#[a-z0-9-.]+/[0-9.]+\">Test case #[0-9.]+")
    # Strips the newline character
    for line in lines:
        line = line.strip()
        if line.startswith("<body>"):
            fetchProjectName = True
        elif fetchProjectName == True:
            fetchProjectName = False
            projectName = line[4:]
        elif line.startswith("<td>Running time:"):
            fetchDuration = True
        elif fetchDuration == True:
            if line.startswith("<td "):
                fetchDuration = False
                testDuration = line[29:]
                testDuration = sum(int(x) * 60 ** i for i, x in enumerate(reversed(testDuration.split(':'))))
            else:
                pass
        else:
            if pattern.match(line):
                defectsCount = defectsCount + 1
    utils.heavyLogging('parseReport: project name {}'.format(projectName))
    utils.heavyLogging('parseReport: total defects {}'.format(defectsCount))
    utils.heavyLogging('parseReport: test duration {}'.format(testDuration))
    if projectName.index("("):
        testSuite = projectName[:projectName.index("(")]
    elif projectName.index("/"):
        testSuite = projectName[:projectName.index("/")]
    utils.heavyLogging('parseReport: test suite {}'.format(testSuite))

    parseResult = dict()
    parseResult["project"] = projectName
    parseResult["testsuite"] = testSuite
    parseResult["counts"] = defectsCount
    parseResult["duration"] = testDuration
    parseResult["defects"] = dict()
    if failuremode != "duration":
        count = 0
        terminate = False
        css = ""
        defectsCounts = dict()
        if maxDefectsCount > 0 and defectsCount > maxDefectsCount:
            utils.heavyLogging('parseReport: too many defects')
        elif defectsCount > 0:
            for line in lines:
                if line.startswith("<style type"):
                    css = line
                if pattern.match(line) and terminate == False:
                    tokens = re.split('<|>', line)
                    defectsStr = tokens[2].strip()
                    defectSection = ""
                    foundHead = False
                    foundCVSS = False
                    testCaseNumber = ""
                    testCaseNumberi = -1
                    for line2 in lines:
                        line2 = line2.strip()
                        #if line2.startswith("<h2>" + defectsStr):
                        if line2 == ("<h2>" + defectsStr):
                            testCaseNumber = re.split('#', line2)
                            testCaseNumber = testCaseNumber[1]
                            if testCaseNumber in defectsCounts:
                                # skip duplicated defects
                                defectsCounts[testCaseNumber]["count"] = defectsCounts[testCaseNumber]["count"] + 1
                            else:
                                defectsCounts[testCaseNumber] = dict()
                                defectsCounts[testCaseNumber]["count"] = 1
                                testCaseNumberi = int(testCaseNumber)
                                if noDefect >= 0 and testCaseNumberi != noDefect:
                                    # defect no. spcified and not equal
                                    utils.heavyLogging('parseReport: skip defect {}'.format(testCaseNumber))
                                    continue
                                foundHead = True
                        if foundHead:
                            if line2.startswith("<hr>") == False:
                                if foundCVSS == True:
                                    cvssTokens = re.split('<|>', line2)
                                    cvssScore = cvssTokens[2]
                                    defectsCounts[testCaseNumber]["cvss"] = cvssScore
                                    foundCVSS = False
                                if "CVSSv3/BS" in line2:
                                    foundCVSS = True
                                if line2.startswith("</span>") == True:
                                    defectSection = defectSection + "\n"
                                defectSection = defectSection + line2
                            else:
                                foundHead = False
                                htmlFileName = "case-" + testCaseNumber + ".html"
                                htmlFile = open(htmlFileName, 'w')
                                htmlFile.write("<head>")
                                htmlFile.write(css)
                                htmlFile.write("</style></head>")
                                htmlFile.write("<body>")
                                htmlFile.write(defectSection)
                                htmlFile.write("</body>")
                                htmlFile.close()
                                parseResult["defects"][testCaseNumber] = htmlFileName
                                count = count + 1
                                utils.heavyLogging("parseReport: create html {}, {}%".format(testCaseNumber, str(count*100/defectsCount)))
                                if noDefect >= 0 and testCaseNumberi == noDefect:
                                    terminate = True
                                    continue
        utils.heavyLogging("parseReport: defects summary")
        def get_relevant_counts(item):
            return item[1]["count"]
        defectsCounts = sorted(defectsCounts.items(), key=get_relevant_counts, reverse=True)
        utils.heavyLogging(json.dumps(defectsCounts, sort_keys=True, indent=2))
    with open("result.json", "w") as outfile:
        json.dump(parseResult, outfile)

def defensicsToJIRA(configs):
    pwd = os.getcwd()
    os.chdir(configs['WORK_DIR'])

    jira.getKeyFields(configs['jira_site_name'], '')
    jira.getEPICKey(configs['jira_site_name'], configs['defensics_jira_project'], configs['issue_epic'])

    with open('epicLinkField.json') as f:
        field = json.load(f)
    epicLinkFieldId = field['id']
    with open('epicKey.json') as f:
        epicKey = json.load(f)
    jiraEPICkey = epicKey['key']
    
    fpParsed = open('parsed.html', 'w')
    cmdSed = sb.Popen(['sed', 's/</\\n</g', configs['defensics_report_path']], stdout=fpParsed)
    cmdSed.wait()
    fpParsed.close()

    parseReport(configs['failure_mode'], configs['max_defects'], configs['specified_defect'])
    with open('result.json') as f:
        jsonObject = json.load(f)
    # The label contains spaces which is invalid
    testSuite = jsonObject['testsuite'].replace(' ', '_')
    defectsCount = jsonObject['counts']
    projectName = jsonObject['project']
    duration = jsonObject['duration']
    # 72hr, 259200.0 seconds
    if (configs['failure_mode'] == 'duration' and duration < 259200.0) or \
            (configs['max_defects'] > 0 and defectsCount > configs['max_defects']):
        # to many defects, aggregate to one issue only
        issue = dict()
        issue['fields'] = dict()
        issue['fields']['project'] = dict()
        issue['fields']['project']['key'] = configs['defensics_jira_project']
        issue['fields']['summary'] = projectName
        issue['fields']['description'] = '{}, total defects {}'.format(projectName, defectsCount)
        issue['fields'][epicLinkFieldId] = jiraEPICkey
        issue['fields']['labels'] = configs['issue_label']
        issue['fields']['issuetype'] = dict()
        issue['fields']['issuetype']['name'] = 'Issue'
        with open('issueToCreate.json', 'w') as fp:
            json.dump(issue, fp)
        jira.jiraCreateIssue(configs['jira_site_name'], 'issueToCreate.json', 'createResult.json')

        fpIssueResult = open('createResult.json')
        jsonIssueResult = json.load(fpIssueResult)
        fpIssueResult.close()
        if 'errors' in jsonIssueResult:
            # create issue failed
            utils.heavyLogging('defensicsToJIRA: create issue {} failed'.format(issue['fields']['summary']))
        else:
            # create issue failed
            utils.heavyLogging('defensicsToJIRA: create issue {} success'.format(issue['fields']['summary']))
            jira.jiraUploadAttachment(configs['jira_site_name'], jsonIssueResult['key'], configs['defensics_report_path'])
    elif defectsCount > 0:
        files = glob.glob('case-*.html')
        for file in files:
            attachmentPath = file['path']
            #def attachmentTokens = attachmentPath.split(/\.|\-/)
            attachmentTokens = attachmentPath.split('\.|\-')
            testCase = attachmentTokens[1]
            issue = dict()
            issue['fields'] = dict()
            issue['fields']['project'] = dict()
            issue['fields']['project']['key'] = configs['defensics_jira_project']
            issue['fields']['summary'] = '{} - {}'.format(projectName, testCase)
            issue['fields'][epicLinkFieldId] = jiraEPICkey
            issue['fields']['labels'] = configs['issue_label']
            issue['fields']['issuetype'] = dict()
            issue['fields']['issuetype']['name'] = 'Issue'
            with open('issueToCreate.json', 'w') as fp:
                json.dump(issue, fp)
            jira.jiraCreateIssue(configs['jira_site_name'], 'issueToCreate.json', 'createResult.json')

            fpIssueResult = open('createResult.json')
            jsonIssueResult = json.load(fpIssueResult)
            fpIssueResult.close()
            if 'errors' in jsonIssueResult:
                # create issue failed
                utils.heavyLogging('defensicsToJIRA: create issue {} failed'.format(issue['fields']['summary']))
            else:
                # create issue failed
                utils.heavyLogging('defensicsToJIRA: create issue {} success'.format(issue['fields']['summary']))
                jira.jiraUploadAttachment(configs['jira_site_name'], jsonIssueResult['key'], attachmentPath)

    os.chdir(pwd)

def main(argv):
    if "JIRA_TOKEN" not in os.environ:
        sys.exit("Environment variable JIRA_TOKEN not defined")

    workDir = ''
    configFile = ''
    try:
        opts, args = getopt.getopt(argv[1:], 'w:f:v', ["work_dir=", "config=", "version"])
    except getopt.GetoptError:
        sys.exit()
    for name, value in opts:
        if name in ('-v', '--version'):
            print("0.1")
            sys.exit(0)
        elif name in ('-f', '--config'):
            configFile = value
        elif name in ('-w', '--work_dir'):
            workDir = value

    if os.path.isdir(workDir) == False:
        os.makedirs(workDir)
    logging.basicConfig(filename=os.path.join(workDir, 'defensicstojira.log'), level=logging.DEBUG, filemode='w')
    utils.translateConfig(configFile)
    configs = utils.loadConfigs(configFile)
    configs['WORK_DIR'] = workDir
    defensicsToJIRA(configs)

if __name__ == '__main__':
    main(sys.argv)