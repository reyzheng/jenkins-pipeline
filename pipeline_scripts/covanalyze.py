import json
import re
import getopt, sys
import os, glob, logging
import subprocess as sb
import datetime
import utils, covreport

WORK_DIR = '.pf-covanalyze'
BLAME_PATH_PATTERN = dict()

totalRows = 999999
cids = []
rawCidInfos = dict()
# covanalyze.json
covanalzyeCfgs = dict()

MAX_EVENTS = 10

def defectsScissors():
    fpHuge = open('defects.json', 'r')
    checkerProperties = False
    cid = ""
    
    if not os.path.exists("cids"):
        os.mkdir("cids")
    else:
        files = glob.glob("cids/*")
        for f in files:
            os.remove(f)
    while True:
        # Get next line from file
        line = fpHuge.readline().strip()
        if line.startswith('"stateOnServer"'):
            count = 0
            while True:
                stateOnServer = fpHuge.readline().strip()
                if stateOnServer.startswith('"cid"'):
                    tokens = re.split(',|:| ', stateOnServer)
                    # found new CID
                    # write current CID to file
                    cid = tokens[3]
                    #print("found cid {}".format(cid))
                    defectInfo = dict()
                    defectInfo[cid] = dict()
                elif stateOnServer.startswith('"classification"'):
                    tokens = re.split(',|:|\"', stateOnServer)
                    if 'triage' not in defectInfo[cid]:
                        defectInfo[cid]['triage'] = dict()
                    defectInfo[cid]['triage']['classification'] = tokens[4]
                elif stateOnServer.startswith('"action"'):
                    tokens = re.split(',|:|\"', stateOnServer)
                    if 'triage' not in defectInfo[cid]:
                        defectInfo[cid]['triage'] = dict()
                    defectInfo[cid]['triage']['action'] = tokens[4]
                elif stateOnServer.startswith('"components"'):
                    stateOnServer = fpHuge.readline().strip()
                    tokens = re.split(',|:|\"', stateOnServer)
                    #components.append(tokens[1])
                    defectInfo[cid]["components"] = []
                    defectInfo[cid]["components"].append(tokens[1])
                    break
                count = count + 1
                if count > 100:
                    print("Error parsing stateOnServer")
                    break
        elif line.startswith('"checkerProperties"'):
            count = 0
            while True:
                checkerProperties = fpHuge.readline().strip()
                if checkerProperties.startswith('"category"'):
                    tokens = re.split(':', checkerProperties)
                    category = tokens[1].strip()[1:-2]
                elif checkerProperties.startswith('"impact"'):
                    tokens = re.split(',|:| |\"', checkerProperties)
                    impact = tokens[6]
                elif checkerProperties.startswith('"subcategoryShortDescription"'):
                    tokens = re.split(':', checkerProperties)
                    subcategoryShortDescription = tokens[1].strip()[1:-2]
    
                    defectInfo[cid]["events"] = eventArray
                    defectInfo[cid]["impact"] = impact
                    defectInfo[cid]["category"] = category
                    defectInfo[cid]["subcategoryShortDescription"] = subcategoryShortDescription
    
                    filePath = "./cids/{}.txt".format(cid)
                    checkFile = os.path.isfile(filePath)
                    if checkFile == True:
                        with open(filePath) as existedFile:
                            refInfo = json.load(existedFile)
                        defectInfo[cid]["events"] += refInfo[cid]["events"]
                    fpSliced = open(filePath, 'w')
                    defectInfo[cid]["events"] = defectInfo[cid]["events"][:MAX_EVENTS]
                    fpSliced.write(json.dumps(defectInfo))
                    fpSliced.close()
                    defectInfo = dict()
                    break
                count = count + 1
                if count > 100:
                    print("Error parsing checkerProperties")
                    break
        elif line.startswith('"mainEventFilePathname"'):
            eventArray = []
            eventDict = dict()
            tokens = re.split(',|:| |\"', line)
            eventDict["filePathname"] = tokens[6]
        elif line.startswith('"mainEventLineNumber"'):
            tokens = re.split(',|:| |\"', line)
            eventDict["lineNumber"] = tokens[5]
        elif line.startswith('"functionDisplayName"'):
            tokens = re.split(',|:| |\"', line)
            eventDict["functionDisplayName"] = tokens[6]
            if len(eventArray) < MAX_EVENTS:
                # MAX_EVENTS at most
                eventArray.append(eventDict)
    
        if not line:
            break
    fpHuge.close()

    with open('defects_.json', 'w') as creating_new_csv_file: 
        pass
    with open('defectsHigh_.json', 'w') as creating_new_csv_file: 
        pass
    with open('defectsMedium_.json', 'w') as creating_new_csv_file: 
        pass
    with open('defectsLow_.json', 'w') as creating_new_csv_file: 
        pass
    fpAll = open('defects_.json', 'a')
    fpAllH = open('defectsHigh_.json', 'a')
    fpAllM = open('defectsMedium_.json', 'a')
    fpAllL = open('defectsLow_.json', 'a')
    
    fpAll.write("{\n")
    fpAllH.write("{\n")
    fpAllM.write("{\n")
    fpAllL.write("{\n")
    
    excludedComponents = []
    if 'coverity_analyze_defects_excomponents' in covanalzyeCfgs:
        excludedComponents = covanalzyeCfgs['coverity_analyze_defects_excomponents'].split(',')
    utils.heavyLogging('defectsScissors: coverity_analyze_defects_excomponents {}'.format(excludedComponents))
    files = glob.glob("cids/*")
    cntAll = 0
    cntAllH = 0
    cntAllM = 0
    cntAllL = 0
    for f in files:
        with open(f) as existedFile:
            defectInfo = json.load(existedFile)
        ignoreCID = False
        for key in defectInfo:
            if defectInfo[key]["components"][0] in excludedComponents:
                ignoreCID = True
                break
        if ignoreCID == True:
            utils.heavyLogging('defectsScissors: ignore {} (excluded component {})'.format(key, defectInfo[key]["components"][0]))
            continue
        if cntAll > 0:
            fpAll.write(",")
        fpAll.write(json.dumps(defectInfo)[1:-1] + "\n")
        cntAll += 1
        for key in defectInfo:
            if defectInfo[key]["impact"] == "High":
                if cntAllH > 0:
                    fpAllH.write(",")
                fpAllH.write(json.dumps(defectInfo)[1:-1] + "\n")
                cntAllH += 1
            elif defectInfo[key]["impact"] == "Medium":
                if cntAllM > 0:
                    fpAllM.write(",")
                fpAllM.write(json.dumps(defectInfo)[1:-1] + "\n")
                cntAllM += 1
            else:
                if cntAllL > 0:
                    fpAllL.write(",")
                fpAllL.write(json.dumps(defectInfo)[1:-1] + "\n")
                cntAllL += 1
            break
        os.remove(f)
    
    fpAll.write("}\n")
    fpAllH.write("}\n")
    fpAllM.write("}\n")
    fpAllL.write("}\n")
    
    fpAll.close()
    fpAllH.close()
    fpAllM.close()
    fpAllL.close()

def cvssReportScissors():
    global rawCidInfos
    # cvss
    with open('cvssreport.json') as f:
        data = json.load(f)
    with open(os.path.join(covanalzyeCfgs['coverity_build_root'], 'preview_report_v2.json')) as fRef:
        dataRef = json.load(fRef)
    for defectInfo in data['defectInfoList']:
        cid = 0
        mergeKey = defectInfo['mergeKey']
        for issueInfo in dataRef['issueInfo']:
            if issueInfo['mergeKey'] == mergeKey:
                cid = issueInfo['cid']
        #cid = defectInfo['optCid']['value']
        cvssSeverity = defectInfo['cvssSeverity']
        cid = str(cid)
        if cid in rawCidInfos:
            pass
        elif cid != '0':
            rawCidInfos[cid] = dict()
        if cid != '0':
            rawCidInfos[cid]["cvss"] = cvssSeverity
    # severity
    fpSeverity = open('severity.csv', 'r')
    while True:
        # Get next line from file
        line = fpSeverity.readline()
        if not line:
            break
        if line.startswith("CID") == False:
            columns = line.split(",")
            cid = columns[0].strip()
            # ensure columns[0] is exactly a cid
            if len(cid) > 0 and cid[:1].isdigit() == True:
                if cid in rawCidInfos:
                    pass
                else:
                    rawCidInfos[cid] = dict()
                rawCidInfos[cid]["severity"] = columns[3].strip()
    with open("cvssreport_.json", "w") as outfile:
        json.dump(rawCidInfos, outfile)

def intersectCids(cids, subcids):
    if len(cids) == 0:
        for subcid in subcids:
            cids.append(subcid)
        return cids
    else:
        intersects = []
        for cid in cids:
            if cid in subcids:
                intersects.append(cid)
        return intersects

def analyzeCoverityIssues(analyzeOption):
    cids = []
    for subOption in analyzeOption:
        logging.debug('analyzeCoverityIssues: subOption {}'.format(subOption))
        subcids = []
        if subOption.startswith("impact"):
            impacts = subOption.split(":")
            impactLevel = impacts[1]
            logging.debug('analyzeCoverityIssues: impact {}'.format(impactLevel))
            with open('defects{}_.json'.format(impactLevel)) as json_file:
                defects = json.load(json_file)
            for defectKey in defects:
                logging.debug('analyzeCoverityIssues: add {}'.format(defectKey))
                subcids.append(defectKey)
        elif subOption == "owasp":
            logging.debug('analyzeCoverityIssues: owasp')
            for cidKey in rawCidInfos:
                if rawCidInfos[cidKey]["owasp"] == True:
                    logging.debug('analyzeCoverityIssues: add {}'.format(cidKey))
                    subcids.append(cidKey)
        elif subOption == "cwe":
            logging.debug('analyzeCoverityIssues: cwe')
            for cidKey in rawCidInfos:
                if rawCidInfos[cidKey]["cwe"] == True:
                    logging.debug('analyzeCoverityIssues: add {}'.format(cidKey))
                    subcids.append(cidKey)
        elif subOption == "cvss":
            logging.debug('analyzeCoverityIssues: cvss')
            for cidKey in rawCidInfos:
                # TODO: CID in cvssreport.json only, not found in preview_report_v2.json
                if 'cvss' in rawCidInfos[cidKey] and (rawCidInfos[cidKey]["cvss"] == "Critical" or rawCidInfos[cidKey]["cvss"] == "High"):
                    logging.debug('analyzeCoverityIssues: add {}'.format(cidKey))
                    subcids.append(cidKey)
        elif subOption == "severity":
            logging.debug('analyzeCoverityIssues: severity')
            for cidKey in rawCidInfos:
                if rawCidInfos[cidKey]["severity"] == "Very High" or rawCidInfos[cidKey]["severity"] == "High":
                    logging.debug('analyzeCoverityIssues: add {}'.format(cidKey))
                    subcids.append(cidKey)
        cids = intersectCids(cids, subcids)
    return cids

# triageRule
#     positive: include files with invalid path/author
#     negative: ignore files with invalid path/author
def defectsAnalyzer(analyzeOptsSize, covuser, covkey, command, triageRule):
    global covanalzyeCfgs

    defectsAnalyzed = dict()
    arrAnalyzed = []
    arrIgnored = []
    with open('defects_.json') as f:
        defects = json.load(f)
    pwd = os.getcwd()
    assignPolicy = 'author'
    if 'coverity_defects_assign_policy' in covanalzyeCfgs and covanalzyeCfgs["coverity_defects_assign_policy"] == "component":
        assignPolicy = 'component'
    elif covanalzyeCfgs['coverity_analyze_rtkonly'] == True:
        projectUrl = "http://{}:{}/api/v2/streams/{}?locale=en_us".format(covanalzyeCfgs["coverity_host"], covanalzyeCfgs["coverity_port"], covanalzyeCfgs["coverity_stream"])
        cmdCurl = sb.Popen(['curl', '-s', '--location', '-X', 'GET', projectUrl, '-H', 'Content-Type: application/json', \
                        '-H', 'Accept: application/json', '--user', '{}:{}'.format(covuser, covkey), '-o', 'streamInfo.json'], stdout=sb.PIPE)
        cmdCurl.communicate()
        fpStreamInfo = open('streamInfo.json')
        jsonStreams = json.load(fpStreamInfo)
        fpStreamInfo.close()
        if len(jsonStreams['streams']) == 0:
            logging.debug('Invalid coverity stream: {}'.format(covanalzyeCfgs["coverity_stream"]))
            return
        else:
            logging.debug('Got triage store {} from coverity stream: {}'.format(jsonStreams['streams'][0]['triageStoreName'], covanalzyeCfgs["coverity_stream"]))
            if jsonStreams['streams'][0]['triageStoreName'] == 'Default Triage Store':
                print('Invalid triage store: Default Triage Store')
                return
            url = 'http://{}:{}/api/v2/issues/triage?locale=en_us&triageStoreName={}'.format(covanalzyeCfgs["coverity_host"], covanalzyeCfgs["coverity_port"], jsonStreams['streams'][0]['triageStoreName'])

    for key in defects:
        # tips: analyzeOptsSize == 0 -> no analyzeOptions, all defects to jira
        if analyzeOptsSize == 0 or key in cids:
            events = defects[key]["events"]
            foundAuthor = False
            eventIdx = 0
            if assignPolicy == 'component':
                foundAuthor = True
                for event in events:
                    event["author"] = "COMPONENT"
                    event["committer"] = "COMPONENT"
                    event["authorfull"] = "COMPONENT"
                    event["committerfull"] = "COMPONENT"
            else:
                for event in events:
                    event["author"] = ""
                    event["committer"] = ""
                    event["authorfull"] = ""
                    event["committerfull"] = ""
                    filePathname = event["filePathname"]
                    lineNumber = event["lineNumber"]
                    utils.heavyLogging('defectsAnalyzer: filepath {}, line {}'.format(filePathname, lineNumber))
                    if os.path.islink(filePathname):
                        utils.heavyLogging('defectsAnalyzer: The file is a softlink...')
                        filePathname = os.path.realpath(filePathname)
                    for pattern in BLAME_PATH_PATTERN:
                        if re.match(pattern, filePathname):
                            filePathname = re.sub(r'{}'.format(pattern), BLAME_PATH_PATTERN[pattern], filePathname)
                            utils.heavyLogging('defectsAnalyzer: filepath(re.sub) {}'.format(filePathname))
                            break
                    dir = os.path.dirname(os.path.abspath(filePathname))
                    filename = os.path.basename(filePathname)
                    if os.path.isfile(filePathname) == False:
                        msg = 'defectsAnalyzer: filepath {} does not exists, skip it'.format(filePathname)
                        utils.heavyLogging(msg)
                        if triageRule == 'positive':
                            foundAuthor = True
                        continue
                    try:
                        os.chdir(dir)
                        # Find author
                        # git blame -e -L ${lineNumber},${lineNumber} \"${filePathname}\"
                        author = sb.Popen(['git', 'blame' , '-e', '-L', '{},{}'.format(lineNumber, lineNumber), filename], stdout=sb.PIPE)
                        line = author.stdout.readline()
                        line = line.decode("utf-8") .strip()
                        #if "realtek" in line or "realsil" in line:
                        if "@" in line:
                            line = re.split('[>< ]', line)
                            if '@' in line[2]:
                                line = line[2]
                            else:
                                line = line[3]
                            if covanalzyeCfgs["coverity_analyze_rtkonly"] == True:
                                # TODO: trivial, realtek/realsil always in line (coverity.py->manageEmitDB())
                                # if coverity_analyze_rtkonly == true
                                if "realtek" not in line and "realsil" not in line:
                                    logging.debug("skip non-rtk {}: {}\n".format(filePathname, line))
                                    continue
                            tokens = line.split('@')
                            event["author"] = tokens[0]
                            event["authorfull"] = line
                            foundAuthor = True
                            utils.heavyLogging("found author: {}".format(event["author"]))
                        else:
                            utils.heavyLogging("invlid author: {}".format(filePathname))
                            event["author"] = ""
                        # Find committer
                        # git log --pretty=format:%ce -u -L ${lineNumber},${lineNumber}:${filePathname}
                        committer = sb.check_output(['git', 'log' , '--pretty=format:%ce', '-u', '-L', '{},{}:{}'.format(lineNumber, lineNumber, filename)], timeout=5)
                        # get first line
                        line = committer.decode('utf-8').splitlines()
                        line = line[0].strip()
                        #if "realtek" in line or "realsil" in line:
                        if "@" in line:
                            tokens = line.split('@')
                            event["committer"] = tokens[0]
                            event["committerfull"] = line
                            utils.heavyLogging("found committer: {}".format(event["committer"]))
                        else:
                            utils.heavyLogging("invlid committer: {}\n".format(filePathname))
                            event["committer"] = ""
                    except Exception as e:
                        utils.heavyLogging('defectsAnalyzer: exception {}'.format(filePathname))
                        utils.heavyLogging(e)
                        if event["author"] != "":
                            event["committer"] = event["author"]
                            event["committerfull"] = event["authorfull"]
                            utils.lightLogging("author auto-assigned {}\n".format(filePathname))
                        else:
                            if triageRule == 'positive':
                                foundAuthor = True
                            else:
                                foundAuthor = False
                            utils.heavyLogging('defectsAnalyzer: empty author')
                    eventIdx += 1
            if foundAuthor == True:
                arrAnalyzed.append(key)
                defectsAnalyzed[key] = defects[key]
                if key in rawCidInfos:
                    defectsAnalyzed[key]["cwe"] = rawCidInfos[key]["cwe"]
                    defectsAnalyzed[key]["owasp"] = rawCidInfos[key]["owasp"]
                    defectsAnalyzed[key]["cvss"] = rawCidInfos[key]["cvss"]
                    defectsAnalyzed[key]["severity"] = rawCidInfos[key]["severity"]
            else:
                arrIgnored.append(key)
    os.chdir(pwd)
    with open("defects_.json", "w") as outfile:
        json.dump(defectsAnalyzed, outfile, indent=2)
    utils.heavyLogging('defectsAnalyzer: {}'.format(os.path.abspath('defects_.json')))
    # triage OSS defects to 'Action' 'Ignore'
    if assignPolicy != "component" and covanalzyeCfgs['coverity_analyze_rtkonly'] == True:
        dataJson = dict()
        attributeValue = dict()
        if command == 'TRIAGE_OSS_FP':
            attributeValue["attributeName"] = "Classification"
        else:
            attributeValue["attributeName"] = "Action"
        # triage to ignore
        if len(arrIgnored) > 0:
            if command == 'TRIAGE_OSS_FP':
                attributeValue["attributeValue"] = "False Positive"
            else:
                attributeValue["attributeValue"] = "Ignore"
            dataJson["cids"] = arrIgnored
            dataJson["attributeValuesList"] = []
            dataJson["attributeValuesList"].append(attributeValue)
            logging.debug("Triage action ignore: {}".format(arrIgnored))
            with open("ignored-raw", "w") as outfile:
                outfile.write(json.dumps(dataJson))
            cmdCurl = sb.Popen(['curl', '-s', '--location', '-X', 'PUT', url, '-H', 'Content-Type: application/json', \
                        '-H', 'Accept: application/json', '--user', '{}:{}'.format(covuser, covkey), '-d', '@ignored-raw'], stdout=sb.PIPE)
            while True:
                line = cmdCurl.stdout.readline()
                print('Triage defects to Ignore/FP: curl {}'.format(bytes.decode(line, 'utf-8')))
                if not line:
                    break
            cmdCurl.communicate()
        # triage to undecided
        if len(arrAnalyzed) > 0:
            if command == 'TRIAGE_OSS_FP':
                attributeValue["attributeValue"] = "Unclassified"
            else:
                attributeValue["attributeValue"] = "Undecided"
            dataJson["cids"] = arrAnalyzed
            dataJson["attributeValuesList"] = []
            dataJson["attributeValuesList"].append(attributeValue)
            logging.debug("Triage action undecided: {}".format(arrAnalyzed))
            with open("undecided-raw", "w") as outfile:
                outfile.write(json.dumps(dataJson))
            cmdCurl = sb.Popen(['curl', '-s', '--location', '-X', 'PUT', url, '-H', 'Content-Type: application/json', \
                        '-H', 'Accept: application/json', '--user', '{}:{}'.format(covuser, covkey), '-d', '@undecided-raw'], stdout=sb.PIPE)
            while True:
                line = cmdCurl.stdout.readline()
                print('Triage defects to Undecided/Unclassified: curl {}'.format(bytes.decode(line, 'utf-8')))
                if not line:
                    break
            cmdCurl.communicate()

def retrieveSnapshotIssues(covuser, covkey, offset):
    global covanalzyeCfgs
    dataRaw = dict()
    dataRaw["filters"] = []
    filter = dict()
    filter["columnKey"] = "project"
    filter["matchMode"] = "oneOrMoreMatch"
    filter["matchers"] = []
    matcher = dict()
    matcher["class"] = "Project"
    matcher["name"] = covanalzyeCfgs["coverity_project"]
    matcher["type"] = "nameMatcher"
    filter["matchers"].append(matcher)
    dataRaw["filters"].append(filter)
    dataRaw["columns"] = ["cid", "column_standard_OWASP Web Top Ten 2021", "column_standard_2021 CWE Top 25"]
    dataRaw["snapshotScope"] = dict()
    dataRaw["snapshotScope"]["show"] = dict()
    dataRaw["snapshotScope"]["show"]["scope"] = covanalzyeCfgs["coverity_snapshot"]
    with open("data-raw", "w") as outfile:
        outfile.write(json.dumps(dataRaw))
    url = "http://{}:{}/api/v2/issues/search?includeColumnLabels=false&locale=en_us&offset={}&queryType=bySnapshot&rowCount=200".format(covanalzyeCfgs["coverity_host"], covanalzyeCfgs["coverity_port"], offset)
    cmdCurl = sb.Popen(['curl', '-s', '--location', '-X', 'POST', url, '-H', 'Content-Type: application/json', \
                        '-H', 'Accept: application/json', '--user', '{}:{}'.format(covuser, covkey), '-o', 'issues.json', '-d', '@data-raw'], stdout=sb.PIPE)
    cmdCurl.wait()
    fpIssues = open('issues.json')
    jsonIssues = json.load(fpIssues)
    fpIssues.close()

    global rawCidInfos
    for issue in jsonIssues["rows"]:
        cid = issue[0]["value"]
        rawCidInfos[cid] = dict()

        rawCidInfos[cid]["owasp"] = False
        rawCidInfos[cid]["cwe"] = False
        if issue[1]["value"].strip() != "None":
            rawCidInfos[cid]["owasp"] = True
        if issue[2]["value"].strip() != "None":
            cweRank = issue[2]["value"].split('-')
            cweRank = cweRank[1]
            if int(cweRank) <= 25:
                rawCidInfos[cid]["cwe"] = True

    global totalRows
    totalRows = jsonIssues["totalRows"]

    return len(jsonIssues["rows"])

def loadcovanalzyeCfgs(covuser, covkey, configFile, reportConfigFile):
    if configFile == "":
        if os.path.exists('covanalyze.json') == False:
            sys.exit("Cannot found covanalyze.json")
        fpConfig = open('covanalyze.json')
    else:
        fpConfig = open(configFile)

    global covanalzyeCfgs
    covanalzyeCfgs = json.load(fpConfig)
    fpConfig.close()
    if "coverity_project" not in covanalzyeCfgs or covanalzyeCfgs["coverity_project"] == "":
        cmdCurl = sb.Popen(['curl', '-s', '-X', 'GET', '-H', 'Content-Type: application/json', \
                        '-H', 'Accept: application/json', '--user', '{}:{}'.format(covuser, covkey), \
                        'http://{}:{}/api/v2/streams/{}?locale=en_us'.format(covanalzyeCfgs["coverity_host"], covanalzyeCfgs["coverity_port"], covanalzyeCfgs["coverity_stream"])], stdout=sb.PIPE)
        cmdCurl.wait()
        logging.debug('loadcovanalzyeCfgs: get coverity project from stream {}'.format(covanalzyeCfgs["coverity_stream"]))
        while True:
            line = cmdCurl.stdout.readline()
            logging.debug('loadcovanalzyeCfgs: api/v2/streams {}'.format(line))
            projectObj = json.loads(line)
            covanalzyeCfgs["coverity_project"] = projectObj["streams"][0]["primaryProjectName"]
            break
        logging.debug("loadcovanalzyeCfgs: got coverity project name {}".format(covanalzyeCfgs["coverity_project"]))
    if os.path.exists('.coverity.license.config') == False:
        with open('.coverity.license.config', 'w') as f:
            f.write('#FLEXnet (do not delete this line)\n')
            f.write('license-server 1123@papyrus.realtek.com\n')
    if reportConfigFile == '':
        reportConfigFile = 'coverity_report_config.yaml'
    if os.path.exists(reportConfigFile) == False:
        sys.exit("Cannot found coverity_report_config.yaml")
    else:
        covanalzyeCfgs['coverity_report_config_path'] = os.path.abspath(reportConfigFile)
        logging.debug("loadcovanalzyeCfgs: coverity report config path {}".format(covanalzyeCfgs['coverity_report_config_path']))
    if 'coverity_build_root' not in covanalzyeCfgs or covanalzyeCfgs['coverity_build_root'] == '':
        covanalzyeCfgs['coverity_build_root'] = os.getcwd()
        utils.heavyLogging('loadcovanalzyeCfgs: take {} as coverity_build_root'.format(covanalzyeCfgs['coverity_build_root']))
    if 'coverity_command_prefix' not in covanalzyeCfgs or covanalzyeCfgs['coverity_command_prefix'] == '':
        if 'coverity_scan_path' in covanalzyeCfgs:
            # from dashboard
            logging.debug('loadcovanalzyeCfgs: coverity_scan_path defined')
            covanalzyeCfgs['coverity_command_prefix'] = covanalzyeCfgs['coverity_scan_path']
    logging.debug('loadcovanalzyeCfgs: take {} as coverity commandprefix'.format(covanalzyeCfgs['coverity_command_prefix']))

def generatePreviewReport():
    global covanalzyeCfgs
    covCmdPrefix = covanalzyeCfgs['coverity_command_prefix']
    if covCmdPrefix != "":
        covCmd = os.path.join(covCmdPrefix, "cov-commit-defects")
    else:
        covCmd = "cov-commit-defects"
    covCmdPieces = covCmd.split()
    if os.path.isabs(covanalzyeCfgs['coverity_build_dir']):
        buildDir = covanalzyeCfgs['coverity_build_dir']
    else:
        buildDir = os.path.join(covanalzyeCfgs['coverity_build_root'], covanalzyeCfgs['coverity_build_dir'])
    logging.debug("COVANALYZE: generatePreviewReport {} {}".format(covCmd, buildDir))
    cmdCurl = sb.Popen(covCmdPieces + ['-sf', os.path.join('..', '.coverity.license.config'), '--dir', buildDir, \
                        '--url', 'http://{}:{}'.format(covanalzyeCfgs['coverity_host'], covanalzyeCfgs['coverity_port']), \
                        '--auth-key-file', os.getenv('COV_AUTH_KEY'), \
                        '--stream', covanalzyeCfgs['coverity_stream'], \
                        '--encryption', 'none', '--preview-report-v2', os.path.join(covanalzyeCfgs['coverity_build_root'], 'preview_report_v2.json')], stdout=sb.PIPE)
    cmdCurl.wait()
    utils.heavyLogging("generatePreviewReport: file {}".format(os.path.abspath('preview_report_v2.json')))

def retrieveDefectsJSON():
    global covanalzyeCfgs

    if not os.path.isfile(os.path.join(covanalzyeCfgs['coverity_build_root'], 'preview_report_v2.json')):
        utils.heavyLogging('retrieveDefectsJSON: Generate preview_report_v2.json')
        generatePreviewReport()

    #covCmdPrefix = covanalzyeCfgs['coverity_scan_path']
    covCmdPrefix = covanalzyeCfgs['coverity_command_prefix']
    if covCmdPrefix != "":
        covCmd = os.path.join(covCmdPrefix, "cov-format-errors")
    else:
        covCmd = "cov-format-errors"
    covCmdPieces = covCmd.split()
    if os.path.isabs(covanalzyeCfgs['coverity_build_dir']):
        buildDir = covanalzyeCfgs['coverity_build_dir']
    else:
        buildDir = os.path.join(covanalzyeCfgs['coverity_build_root'], covanalzyeCfgs['coverity_build_dir'])
    utils.heavyLogging("retrieveDefectsJSON: {} {}".format(covCmd, buildDir))
    cmdCurl = sb.Popen(covCmdPieces + ['-sf', os.path.join('..', '.coverity.license.config'), '--dir', buildDir, \
                        '--json-output-v8', 'defects.json', '--no-default-triage-filters', '--preview-report-v2', \
                        os.path.join(covanalzyeCfgs['coverity_build_root'], 'preview_report_v2.json')], stdout=sb.PIPE)
    out, err = cmdCurl.communicate()
    utils.heavyLogging("retrieveDefectsJSON: file {}".format(os.path.abspath('defects.json')))

def retrieveSnapshotsJSON(covuser, covkey):
    global covanalzyeCfgs
    today = "{}-12-31".format(datetime.date.today().year)
    utils.heavyLogging("retrieveSnapshotsJSON: curl streams/stream/snapshots")
    cmdCurl = sb.Popen(['curl', '--location', '-X', 'GET', \
                        'http://{}:{}/api/v2/streams/stream/snapshots?idType=byName&name={}&lastBeforeCodeVersionDate={}T00%3A00%3A00Z&locale=en_us'.format(covanalzyeCfgs['coverity_host'], covanalzyeCfgs['coverity_port'], covanalzyeCfgs['coverity_stream'], today), \
                        '-H', 'Content-Type: application/json', '-H', 'Accept: application/json', '--user', \
                        '{}:{}'.format(covuser, covkey), '-s', '-o', 'snapshots.json'], stdout=sb.PIPE)
    cmdCurl.wait()
    with open('snapshots.json') as f:
        data = json.load(f)
        covanalzyeCfgs["coverity_snapshot"] = data['snapshotsForStream'][0]['id']
        utils.heavyLogging("retrieveSnapshotsJSON: got coverity snapshot {}".format(covanalzyeCfgs["coverity_snapshot"]))

def querySnapshotInfo(covuser, covkey):
    global covanalzyeCfgs
    logging.debug("COVANALYZE: curl snapshots/{}".format(covanalzyeCfgs["coverity_snapshot"]))
    cmdCurl = sb.Popen(['curl', '--location', '-X', 'GET', \
                        'http://{}:{}/api/v2/snapshots/{}?locale=en_us'.format(covanalzyeCfgs['coverity_host'], covanalzyeCfgs['coverity_port'], covanalzyeCfgs["coverity_snapshot"]), \
                        '-H', 'Content-Type: application/json', '-H', 'Accept: application/json', '--user', \
                        '{}:{}'.format(covuser, covkey), '-s', '-o', 'snapshot.json'], stdout=sb.PIPE)
    cmdCurl.wait()
    covanalzyeCfgs["snapshot_version"] = "null"
    covanalzyeCfgs["snapshot_description"] = "null"
    with open('snapshot.json') as f:
        data = json.load(f)
        if "sourceVersion" in data:
            covanalzyeCfgs['snapshot_version'] = data['sourceVersion']
            logging.debug('COVANALYZE: got snapshot version {}'.format(covanalzyeCfgs['snapshot_version']))
        if "description" in data:
            covanalzyeCfgs['snapshot_description'] = data['description']
            logging.debug('COVANALYZE: got snapshot description {}'.format(covanalzyeCfgs['snapshot_description']))

def prepareReportConfig(cwd):
    global covanalzyeCfgs
    with open(covanalzyeCfgs['coverity_report_config_path'], "r") as sources:
        lines = sources.readlines()
    with open(covanalzyeCfgs['coverity_report_config_path'], "w") as sources:
        for line in lines:
            line = re.sub(r'url:.*', 'url: http://{}:{}'.format(covanalzyeCfgs['coverity_host'], covanalzyeCfgs['coverity_port']), line)
            if (covanalzyeCfgs["coverity_snapshot"] != 0):
                line = re.sub(r'snapshot-id:.*', 'snapshot-id: {}'.format(covanalzyeCfgs['coverity_snapshot']), line)
            sources.write(line)
        utils.heavyLogging('prepareReportConfig: re-write report config xml with smapshot id {}'.format(covanalzyeCfgs['coverity_snapshot']))
    code = covreport.checkReportInPATH(covanalzyeCfgs['coverity_report_path'])
    if code < 0:
        utils.heavyLogging('prepareReportConfig: coverity report not in PATH')
        utils.heavyLogging('prepareReportConfig: download URF.sif')
        covanalzyeCfgs['coverity_report_path'] = covreport.downloadURFSif(cwd)
        # back to string
        covanalzyeCfgs['coverity_report_path'] = ' '.join(covanalzyeCfgs['coverity_report_path']) + ' /SDLC/cov-report/bin/'
        utils.heavyLogging('prepareReportConfig: coverity report path(sif) {}'.format(covanalzyeCfgs['coverity_report_path']))
    else:
        utils.heavyLogging('prepareReportConfig: coverity report path {}'.format(covanalzyeCfgs['coverity_report_path']))

def generateCVSSReport():
    global covanalzyeCfgs
    covReportPath = covanalzyeCfgs['coverity_report_path']
    if covReportPath != "":
        covCmd = os.path.join(covReportPath, "cov-generate-cvss-report")
    else:
        covCmd = "cov-generate-cvss-report"
    covCmdPieces = covCmd.split()
    utils.lightLogging('generateCVSSReport: command {}'.format(covCmdPieces))
    cmdEnv = dict(os.environ)
    cmdEnv['WRITE_ISSUES_JSON'] = 'cvssreport.json'
    if os.name == "posix":
        os.unsetenv('DISPLAY')
    with open('cov-generate-cvss-report.log', "w") as logReport:
        cmdShell = sb.Popen(covCmdPieces + [covanalzyeCfgs['coverity_report_config_path'], '--project', covanalzyeCfgs['coverity_project'], \
                        '--auth-key-file', os.getenv('COV_AUTH_KEY'), '--report', '--output', 'cvss_tmp.pdf'], stdout=logReport, stderr=logReport, env=cmdEnv)
        cmdShell.wait()
        logReport.flush()
    utils.heavyLogging('generateCVSSReport: {}'.format(os.path.abspath('cvssreport.json')))

def generateIntegrityReport():
    global covanalzyeCfgs
    covReportPath = covanalzyeCfgs['coverity_report_path']
    if covReportPath != "":
        covCmd = os.path.join(covReportPath, "cov-generate-security-report")
    else:
        covCmd = "cov-generate-security-report"
    covCmdPieces = covCmd.split()
    utils.lightLogging('generateIntegrityReport: command {}'.format(covCmdPieces))
    cmdEnv = dict(os.environ)
    cmdEnv['WRITE_SEVERITIES_CSV'] = 'severity.csv'
    if os.name == "posix":
        os.unsetenv('DISPLAY')
    with open('cov-generate-security-report.log', "w") as logReport:
        cmdShell = sb.Popen(covCmdPieces + [covanalzyeCfgs['coverity_report_config_path'], '--project', covanalzyeCfgs['coverity_project'], \
                        '--auth-key-file', os.getenv('COV_AUTH_KEY'), '--output', 'security_tmp.pdf'], stdout=logReport, stderr=logReport, env=cmdEnv)
        cmdShell.wait()
        logReport.flush()
    print('generateSecurityReport: {}'.format(os.path.abspath('severity.csv')))

def analyzedDefectsToJSON():
    global covanalzyeCfgs

    analyzedDefects = dict()
    analyzedDefects['host'] = covanalzyeCfgs['coverity_host']
    analyzedDefects['port'] = covanalzyeCfgs['coverity_port']
    analyzedDefects['assignPolicy'] = covanalzyeCfgs['coverity_defects_assign_policy']
    analyzedDefects['snapshot'] = covanalzyeCfgs['coverity_snapshot']
    analyzedDefects['snapshotVersion'] = covanalzyeCfgs['snapshot_version']
    analyzedDefects['snapshotDescription'] = covanalzyeCfgs['snapshot_description']
    analyzedDefects['coverityStream'] = covanalzyeCfgs['coverity_stream']
    with open('defects_.json') as f:
        analyzedDefects['defects'] = json.load(f)
    return analyzedDefects

def main(argv):
    skipTranslate = False
    command = 'MAIN'
    configFile = ''
    reportConfigFile = ''
    ordination = 'positive'
    global WORK_DIR
    try:
        opts, args = getopt.getopt(argv[1:], 'b:o:c:w:r:f:u:p:vs', \
                                    ["blame_path_replacement=", "ordination=", "command=", "work_dir=", "report_config=", "config=", "user=", "password=", "version", "skip_translate"])
    except getopt.GetoptError:
        sys.exit()
    for name, value in opts:
        if name in ('-v', '--version'):
            print("0.1")
            sys.exit(0)
        elif name in ('-s', '--skip_translate'):
            skipTranslate = True
        elif name in ('-u', '--user'):
            # override if --user
            covuser = value
        elif name in ('-p', '--password'):
            # override if --password
            covpass = value
        elif name in ('-f', '--config'):
            configFile = value
        elif name in ('-r', '--report_config'):
            reportConfigFile = value
        elif name in ('-c', '--command'):
            command = value
            availableCommands = ['MAIN', 'TRIAGE_OSS_IGNORE', 'TRIAGE_OSS_FP', 'ANALYZE_ONLY', 'INIT_WORKDIR']
            if command not in availableCommands:
                print('Invalid command {}'.format(command))
                sys.exit(1)
        elif name in ('-w', '--work_dir'):
            WORK_DIR = value
        elif name in ('-b', '--blame_path_replacement'):
            fpBlamePath = open(value, 'r')
            while True:
                line = fpBlamePath.readline()
                if line.startswith('#'):
                    continue
                tokens = line.split(':')
                if len(tokens) > 1:
                    BLAME_PATH_PATTERN[tokens[0]] = tokens[1].strip()
                if not line:
                    break
            fpBlamePath.close()
        elif name in ('-o', '--ordination'):
            # TODO: negative ordination
            ordination = value
            availableOrdinations = ['positive', 'negative']
            if ordination not in availableOrdinations:
                print('Invalid triage rule {}'.format(ordination))
                sys.exit(1)

    if os.path.isdir(WORK_DIR) == False:
        os.makedirs(WORK_DIR)
    logging.basicConfig(filename=os.path.join(WORK_DIR, 'covanalyze.log'), level=logging.DEBUG, filemode='w')
    print('main: log file {}'.format(os.path.join(WORK_DIR, 'covanalyze.log')), flush=True)

    if command == 'INIT_WORKDIR':
        utils.cleanEnvAndArchives(WORK_DIR)
        sys.exit(0)
    if skipTranslate == False:
        utils.translateConfig(configFile)
    # check if jenkins credentials defined (as env. variable)
    if "COV_AUTH_KEY" in os.environ:
        COV_AUTH_KEY = os.getenv('COV_AUTH_KEY')
        fpCovAuthKey = open(COV_AUTH_KEY)
        data = json.load(fpCovAuthKey)
        fpCovAuthKey.close()
        covuser = data["username"]
        covpass = data["key"]
        utils.heavyLogging("main: got environmental variable, COV_AUTH_KEY")
    else:
        sys.exit("Environmental variable COV_AUTH_KEY not defined")

    # step 1
    #     Load configurations
    #     Get coverity project name if necessary
    #     Generate .coverity.license.config
    loadcovanalzyeCfgs(covuser, covpass, configFile, reportConfigFile)
    cwd = os.getcwd()
    os.chdir(WORK_DIR)
    # step 2
    #     cov-commit-defects -> preview_report_v2.json
    #     cov-format-errors  -> defects.json (Impact)
    #     preview_report_v2.json is insufficient:
    #         2.1 the strange windows file path in preview-report.json
    #         2.2 lacking fileds: impact, subcategoryShortDescription
    retrieveDefectsJSON()
    # step 3
    #     defects.json -> defects_.json, defectsHigh_.json, defectsMedium_.json, defectsLow_.json
    defectsScissors()
    if command == 'TRIAGE_OSS_IGNORE' or command == 'TRIAGE_OSS_FP':
        # tips: analyzeOptsSize == 0 -> no analyzeOptions, analyze all
        defectsAnalyzer(0, covuser, covpass, command, ordination)
        sys.exit(0)
    # step 4
    #     get snapshot id to covanalzyeCfgs["coverity_snapshot"]
    retrieveSnapshotsJSON(covuser, covpass)
    # step 5
    #     query snapshot version, description to covanalzyeCfgs['snapshot_version'], covanalzyeCfgs['snapshot_description']
    querySnapshotInfo(covuser, covpass)
    # step 6
    #     retrieve snapshot issues to get OWASP, CWE store to rawCidInfos
    retrievedRows = 0
    while retrievedRows < totalRows:
        retrievedRows += retrieveSnapshotIssues(covuser, covpass, retrievedRows)
    # step 7
    #     prepare coverity_report_config.yaml
    prepareReportConfig(cwd)
    # step 8
    #     cov-generate-cvss-report: "cvssreport.json" to get defect's cvssSeverity
    generateCVSSReport()
    # step 9
    #     syn-generate-security-report: "coverity-issues.csv" to get defect's Severity
    generateIntegrityReport()
    # step 10
    #     store cvss, severity into rawCidInfos
    cvssReportScissors()
    # step 11
    #     output defects_.json
    global cids
    analyzeOptions = covanalzyeCfgs["coverity_analyze_defects_options"]
    utils.heavyLogging('main: analyze options {}'.format(analyzeOptions))
    for analyzeOption in analyzeOptions:
        cids = cids + analyzeCoverityIssues(analyzeOption)
    cids = list(set(cids))
    defectsAnalyzer(len(analyzeOptions), covuser, covpass, 'TRIAGE_OSS_IGNORE', ordination)
    if command == 'ANALYZE_ONLY':
        sys.exit(0)
    # step 12
    #     generate preview-report-committer-${env.BUILD_BRANCH}.json for JIRA action
    analyzedDefects = analyzedDefectsToJSON()
    os.chdir(cwd)

    if "BUILD_BRANCH" in os.environ:
        analyzedDefectsJSONPath = "preview-report-committer-{}.json".format(os.getenv('BUILD_BRANCH'))
    else:
        analyzedDefectsJSONPath = "preview-report-committer.json"
    with open(analyzedDefectsJSONPath, 'w') as fp:
        json.dump(analyzedDefects, fp, indent=2)
    utils.heavyLogging("main: final report {}".format(os.path.abspath(analyzedDefectsJSONPath)))

if __name__ == "__main__":
    main(sys.argv)