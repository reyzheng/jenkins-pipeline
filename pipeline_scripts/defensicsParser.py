import sys, re, getopt
import json

try:
    opts, args = getopt.getopt(sys.argv[1:], 'f:m:n:', ["failure=", "max=", "no="])
except getopt.GetoptError:
    print(f'{sys.argv[0]} -f <failure_mode> -m <max_defects_count> -n <defect_number>')
    sys.exit()

failuremode = "duration"
maxDefectsCount = 0
noDefect = -1

for name, value in opts:
    if name in ('-m', '--max'):
        maxDefectsCount = int(value)
    elif name in ('-n', '--no'):
        noDefect = int(value)
    elif name in ('-f', '--failure'):
        failuremode = value

fp = open('parsed.html', 'r')
lines = fp.readlines()

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
print("Project name: " + projectName)
print("Total defects: " + str(defectsCount))
print("Test duration: " + str(testDuration))

if projectName.index("("):
    testSuite = projectName[:projectName.index("(")]
elif projectName.index("/"):
    testSuite = projectName[:projectName.index("/")]
print("Test suite: " + testSuite)

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
        print("Too many defects")
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
                                print("Skip defect " + testCaseNumber)
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
                            print("Create html:" + testCaseNumber + ", " + str(count*100/defectsCount) + "%")
                            if noDefect >= 0 and testCaseNumberi == noDefect:
                                terminate = True
                                continue
    print("defects summary:")
    def get_relevant_counts(item):
        return item[1]["count"]
    defectsCounts = sorted(defectsCounts.items(), key=get_relevant_counts, reverse=True)
    print(json.dumps(defectsCounts, sort_keys=True, indent=4))

with open("result.json", "w") as outfile:
    json.dump(parseResult, outfile)