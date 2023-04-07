import json
import re
import sys
import os, glob
import subprocess as sb

cids = []
rawCidInfos = dict()

def defectsScissors():
    arrHigh = dict()
    arrMedium = dict()
    arrLow = dict()
    
    fpHuge = open('defects.json', 'r')
    capture = True
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
                    tokens = re.split(',|:| |\"', stateOnServer)
                    #triage["classification"] = tokens[6]
                    defectInfo[cid]["triage"] = dict()
                    defectInfo[cid]["triage"]["classification"] = tokens[6]
                elif stateOnServer.startswith('"components"'):
                    stateOnServer = fpHuge.readline().strip()
                    tokens = re.split(',|:| |\"', stateOnServer)
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
                if checkerProperties.startswith('"impact"'):
                    tokens = re.split(',|:| |\"', checkerProperties)
                    impact = tokens[6]
                elif checkerProperties.startswith('"subcategoryShortDescription"'):
                    tokens = re.split(':', checkerProperties)
                    subcategoryShortDescription = tokens[1].strip()[1:-2]
    
                    defectInfo[cid]["events"] = eventArray
                    defectInfo[cid]["impact"] = impact
                    defectInfo[cid]["subcategoryShortDescription"] = subcategoryShortDescription
    
                    filePath = "./cids/{}.txt".format(cid)
                    checkFile = os.path.isfile(filePath)
                    if checkFile == True:
                        with open(filePath) as existedFile:
                            refInfo = json.load(existedFile)
                        defectInfo[cid]["events"] += refInfo[cid]["events"]
                    fpSliced = open(filePath, 'w')
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
    
    files = glob.glob("cids/*")
    cntAll = 0
    cntAllH = 0
    cntAllM = 0
    cntAllL = 0
    for f in files:
        with open(f) as existedFile:
            defectInfo = json.load(existedFile)
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
    # owasp, cwe
    fpIssues = open('.cvss/coverity-issues.csv', 'r')
    while True:
        # Get next line from file
        line = fpIssues.readline()
        if not line:
            break
        if line.startswith("CID") == False:
            columns = line.split(",")
            cid = columns[0].strip()
            # ensure columns[0] is exactly a cid
            if len(cid) > 0 and cid[0].isdigit() == True:
                rawCidInfos[cid] = dict()
                rawCidInfos[cid]["owasp"] = False
                rawCidInfos[cid]["cwe"] = False
                if columns[2].strip() != "":
                    rawCidInfos[cid]["owasp"] = True
                if columns[3].strip() != "" and int(columns[3]) <= 25:
                    rawCidInfos[cid]["cwe"] = True
    # cvss
    with open('.cvss/cvssreport.json') as f:
        data = json.load(f)
    with open('preview_report_v2.json') as fRef:
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
    fpSeverity = open('.cvss/severity.csv', 'r')
    while True:
        # Get next line from file
        line = fpSeverity.readline()
        if not line:
            break
        if line.startswith("CID") == False:
            columns = line.split(",")
            cid = columns[0].strip()
            # ensure columns[0] is exactly a cid
            if len(cid) > 0 and cid[0].isdigit() == True:
                if cid in rawCidInfos:
                    pass
                else:
                    rawCidInfos[cid] = dict()
                rawCidInfos[cid]["severity"] = columns[3].strip()
    with open(".cvss/cvssreport_.json", "w") as outfile:
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
        subcids = []
        if subOption.startswith("impact"):
            impacts = subOption.split(":")
            impactLevel = impacts[1]
            with open('defects{}_.json'.format(impactLevel)) as json_file:
                defects = json.load(json_file)
            for defectKey in defects:
                subcids.append(defectKey)
        elif subOption == "owasp":
            for cidKey in rawCidInfos:
                if rawCidInfos[cidKey]["owasp"] == True:
                    subcids.append(cidKey)
        elif subOption == "cwe":
            for cidKey in rawCidInfos:
                if rawCidInfos[cidKey]["cwe"] == True:
                    subcids.append(cidKey)
        elif subOption == "cvss":
            for cidKey in rawCidInfos:
                if rawCidInfos[cidKey]["cvss"] == "Critical" or rawCidInfos[cidKey]["cvss"] == "High":
                    subcids.append(cidKey)
        elif subOption == "severity":
            for cidKey in rawCidInfos:
                if rawCidInfos[cidKey]["severity"] == "Very High" or rawCidInfos[cidKey]["severity"] == "High":
                    subcids.append(cidKey)
        cids = intersectCids(cids, subcids)
    return cids

def defectsAnalyzer(analyzeOptsSize):
    defectsAnalyzed = dict()
    with open('defects_.json') as f:
        defects = json.load(f)
    pwd = os.getcwd()
    for key in defects:
        # tips: analyzeOptsSize == 0 -> no analyzeOptions, all defects to jira
        if analyzeOptsSize == 0 or key in cids:
            events = defects[key]["events"]
            foundAuthor = False
            for event in events:
                filePathname = event["filePathname"]
                lineNumber = event["lineNumber"]
                dir = os.path.dirname(os.path.abspath(filePathname))
                os.chdir(dir)
                # git log --pretty=format:%ce -u -L ${lineNumber},${lineNumber}:${filePathname}
                committer = sb.Popen(['git', 'log' , '--pretty=format:%ce', '-u', '-L', '{},{}:{}'.format(lineNumber, lineNumber, filePathname)], stdout=sb.PIPE)
                # get first line
                line = committer.stdout.readline()
                line = line.decode("utf-8") .strip()
                if "realtek" in line or "realsil" in line:
                    tokens = line.split('@')
                    event["committer"] = tokens[0]
                else:
                    print("Invlid committer: {}".format(filePathname))
                    event["committer"] = ""
                # git blame -e -L ${lineNumber},${lineNumber} \"${filePathname}\"
                author = sb.Popen(['git', 'blame' , '-e', '-L', '{},{}'.format(lineNumber, lineNumber), filePathname], stdout=sb.PIPE)
                line = author.stdout.readline()
                line = line.decode("utf-8") .strip()
                if "realtek" in line or "realsil" in line:
                    line = re.split('[>< ]', line)
                    line = line[2]
                    tokens = line.split('@')
                    event["author"] = tokens[0]
                    foundAuthor = True
                else:
                    print("Invlid author: {}".format(filePathname))
                    event["author"] = ""
            if foundAuthor == True:
                defectsAnalyzed[key] = defects[key]
                if key in rawCidInfos:
                    defectsAnalyzed[key]["cwe"] = rawCidInfos[key]["cwe"]
                    defectsAnalyzed[key]["owasp"] = rawCidInfos[key]["owasp"]
                    defectsAnalyzed[key]["cvss"] = rawCidInfos[key]["cvss"]
                    defectsAnalyzed[key]["severity"] = rawCidInfos[key]["severity"]
    os.chdir(pwd)
    with open("defects_.json", "w") as outfile:
        json.dump(defectsAnalyzed, outfile)

def main(argv):
    #try:
    #    opts, args = getopt.getopt(argv[1:], 'v', ["version"])
    #except getopt.GetoptError:
    #    sys.exit()
    #for name, value in opts:
    #    if name in ('-v', '--version'):
    #        print("0.1")
    #        sys.exit(0)

    # defects.json -> defects_.json
    defectsScissors()
    # store CVSS, OWASP, CWE into rawCidInfos
    cvssReportScissors()

    global cids
    with open('analyzeOptions.json') as json_file:
        analyzeOptions = json.load(json_file)
    print("analyzeCoverityIssues: {}".format(analyzeOptions))
    for analyzeOption in analyzeOptions:
        cids = cids + analyzeCoverityIssues(analyzeOption)
    cids = list(set(cids))
    defectsAnalyzer(len(analyzeOptions))

if __name__ == "__main__":
    main(sys.argv)
