def stashScriptsConfigs() {
    dir ("rtk_coverity") {
        stash name: "stash-covanalyzer-report-config", includes: "coverity_report_config.yaml"
    }
    dir("pipeline_scripts") {
        stash name: "stash-covanalyzer-python-scripts", includes: "cvssReportScissors.py,defectsScissors.py,defectsAnalyzer.py"
    }
}

def init(stageName) {
    def defaultConfigs = [
        display_name: "",
        coverity_scan_path: "",
        coverity_host: "172.21.15.146",
        coverity_port: "8080",
        coverity_auth_key_credential: "",
        coverity_report_path: "",
        coverity_analyze_defects_options: "",
        coverity_defects_assign_policy: "committer",
        coverity_project: "",
        coverity_stream: "",
        coverity_snapshot: 0,
        coverity_build_dir: "coverity_idir/build",
        coverity_build_root: ""
    ]

    def utils = load "utils.groovy"
    def config = utils.commonInit(stageName, defaultConfigs)

    if (config.settings.coverity_analyze_defects_options == "") {
        config.settings.coverity_analyze_defects_options = [:]
    }
    else {
        config.settings.coverity_analyze_defects_options = readJSON text: config.settings.coverity_analyze_defects_options
    }
    stashSampleCoverityConfig()

    return config
}

def captureStdout(command, underUnix) {
    def stdout = ""

    if (underUnix == true) {
        try {
            stdout = sh(script: command, returnStdout: true).trim()
            stdout = stdout.readLines()
        }
        catch (e) {
        }
    }
    else {
        //command = command.replaceAll("%", "%%")
        try {
            stdout = bat(script: command, returnStdout: true).trim()
            stdout = stdout.readLines().drop(1)
        }
        catch (e) {
        }
    }

    return stdout
}

def intersectCids(cids, subcids) {
    if (cids == null) {
        cids = []
        for (def i=0; i<subcids.size(); i++) {
            cids << subcids[i]
        }
        return cids
    }
    else {
        def intersects = []
        for (cid in cids) {
            if (subcids.contains(cid.toString()) == true) {
                intersects << cid
            }
        }
        return intersects
    }
}

def findLocalGitPath(fileName, underUnix) {
    def lastIndex
    def folder
    def localGitPath

    // TODO: coverity windows path presentation
    // ex: /jenkins/workspace/pipeline-as-code/test jira@2/source/feature-1.c
    if (fileName.contains("\\")) {
        lastIndex = fileName.lastIndexOf("\\")
        folder = fileName.substring(0, lastIndex)
    }
    else {
        lastIndex = fileName.lastIndexOf("/")
        folder = fileName.substring(0, lastIndex)
    }

    localGitPath = captureStdout("cd ${folder} && git rev-parse --show-toplevel", underUnix)
    if (localGitPath == "") {
        print "Cannot find author ${fileName} (--show-toplevel error)"
        return null
    }
    else {
        return localGitPath[0]
    }
}

def findAuthor(localGitPath, filePathname, lineNumber, assignPolicy, underUnix) {
    def gitCommitter = ''
    def blameScript

    if (assignPolicy == "committer") {
        if (underUnix) {
            blameScript = "cd \"${localGitPath}\" && git log --pretty=format:%ce -u -L ${lineNumber},${lineNumber}:${filePathname}"
        }
        else {
            blameScript = "cd \"${localGitPath}\" && git log --pretty=format:%%ce -u -L ${lineNumber},${lineNumber}:${filePathname}"
        }
    }
    else {
        blameScript = "cd \"${localGitPath}\" && git blame -e -L ${lineNumber},${lineNumber} \"${filePathname}\""
    }
    def blame = captureStdout(blameScript, underUnix)
    if (blame == "") {
        print "${filePathname} ${lineNumber} cannot find committer/author"
    }
    else {
        blame = blame[0]
        if (blame.startsWith("fatal")) {
            print "${filePathname} ${lineNumber} cannot find committer/author"
        }
        else {
            def author
            if (assignPolicy == "committer") {
                author = blame.trim()
            }
            else {
                def blames = blame.split("[>< ]")
                author = blames[2]
            }
            // email realtek, realsil
            if (author.contains("realtek") || author.contains("realsil")) {
                def authorToken = author.split("@")
                gitCommitter = authorToken[0]
            }
            else {
                print "${filePathname} ${lineNumber} found unknown committer/author ${author}"
            }
        }
    }

    return gitCommitter
}

// output: analyzedDefects, cidsFoundAuthor
// input: cidPools, rawCidInfos
def appendIssueToAnalyzedDefects(analyzedDefects, cidsFoundAuthor, rawCidInfos, assignPolicy) {
    def underUnix = isUnix()
    def defects = readJSON file: "defects_.json"

    for (def key in defects.keySet()) {
        def cid = key
        def defect = defects[key]
        def foundAuthor = false
        for (def j=0; j<defect.events.size(); j++) {
            def event = defect.events[j]

            def gitCommitter = ''
            def gitAuthor = ''
            def localGitPath = findLocalGitPath(event.filePathname, underUnix)
            if (localGitPath != null) {
                // git blame to find author
                // or git log to find committer: git log --pretty=format:%ce -u -L 20,20:test.c
                gitCommitter = findAuthor(localGitPath, event.filePathname, event.lineNumber, 'committer', underUnix)
                gitAuthor = findAuthor(localGitPath, event.filePathname, event.lineNumber, 'author', underUnix)
            }
            defect.events[j].committer = gitCommitter
            defect.events[j].author = gitAuthor
            if (assignPolicy == 'committer' && gitCommitter != '') {
                foundAuthor = true
            }
            else if (assignPolicy == 'author' && gitAuthor != '') {
                foundAuthor = true
            }
        }
        if (rawCidInfos) {
            defect.cwe = rawCidInfos."${cid}".cwe
            defect.owasp = rawCidInfos."${cid}".owasp
            defect.cvss = rawCidInfos."${cid}".cvss
            defect.severity = rawCidInfos."${cid}".severity
        }
        if (foundAuthor == true) {
            // push to cids (and then generate per cid html output) only if foundAuthor
            cidsFoundAuthor."${cid}" = true
        }
    }

    analyzedDefects.defects = defects
}

def analyzeCoverityIssues(analyzeOptions, rawCidInfos) {
    def cids
    print "analyzeCoverityIssues: ${analyzeOptions}"
    for (analyzeOption in analyzeOptions) {
        def subcids = []
        if (analyzeOption.startsWith("impact")) {
            def impacts = analyzeOption.split(":")
            def impactLevel = impacts[1]
            def defects = readJSON file: "defects${impactLevel}_.json"
            for (def key in defects.keySet()) {
                subcids << key
            }
        }
        else if (analyzeOption == "owasp") {
            for (rawCidInfo in rawCidInfos) {
                def cid = rawCidInfo.key
                if (rawCidInfos."$cid".owasp == true) {
                    subcids << cid
                }
            }
        }
        else if (analyzeOption == "cwe") {
            for (rawCidInfo in rawCidInfos) {
                def cid = rawCidInfo.key
                if (rawCidInfos."$cid".cwe == true) {
                    subcids << cid
                }
            }
        }
        else if (analyzeOption == "cvss") {
            for (rawCidInfo in rawCidInfos) {
                def cid = rawCidInfo.key
                if (rawCidInfos."$cid".cvss == "Critical" || rawCidInfos."$cid".cvss == "High") {
                    subcids << cid
                }
            }
        }
        else if (analyzeOption == "severity") {
            for (rawCidInfo in rawCidInfos) {
                def cid = rawCidInfo.key
                if (rawCidInfos."$cid".severity == "Very High" || rawCidInfos."$cid".severity == "High") {
                    subcids << cid
                }
            }
        }
        cids = intersectCids(cids, subcids)
    }

    return cids
}

def extractSeverity(rawCidInfos) {
    def file = readFile "severity.csv"
    def lines = file.readLines()
    for (line in lines) {
        if (line.startsWith("CID") == false) {
            def columns = line.split(",")
            def cid = columns[0].trim()
            // ensure columns[0] is exactly a cid
            def testCID = (cid ==~ /^[0-9]*$/)
            if (testCID == false) {
                continue
            }
            if (rawCidInfos.containsKey(cid)) {
                rawCidInfos."${cid}".severity = ""
                if (columns[3].trim() != "") {
                    rawCidInfos."${cid}".severity = columns[3].trim()
                }
            }
        }
    }
}

// TODO: dummy parameter pipelineAsCode, preloads
def func(pipelineAsCode, configs, preloads) {
    def underUnix = isUnix()
    def cidPools = [:]
    def defects
    def rawCidInfos

    configs.coverity_stream = captureStdout("echo ${configs.coverity_stream}", underUnix)
    configs.coverity_stream = configs.coverity_stream[0]

    def covCmdPrefix = ""
    if (underUnix == true) {
        covCmdPrefix = configs.coverity_scan_path + "/"
    }
    else {
        // windows coverity_scan_path with space
        covCmdPrefix = "\"" + configs.coverity_scan_path + "\"\\"
    }

    if (configs.coverity_build_root == "") {
        configs.coverity_build_root = WORKSPACE
    }
    dir(configs.coverity_build_root) {
        withCredentials([file(credentialsId: configs.coverity_auth_key_credential, variable: 'KEY_PATH')]) {
            if (configs.coverity_project == "" || configs.coverity_project == null) {
                unstash name: "stash-script-utils"
                def utils = load "utils.groovy"
                def keyObj = readJSON file: KEY_PATH
                //def projectStdout = utils.captureStdout("set +x && curl -X GET --header 'Content-Type: application/json' --header 'Accept: application/json' --user ${keyObj.username}:${keyObj.key} http://${configs.coverity_host}:${configs.coverity_port}/api/v2/streams/${configs.coverity_stream}?locale=en_us", underUnix)
                def projectStdout = utils.captureStdout("curl -X GET --header 'Content-Type: application/json' --header 'Accept: application/json' --user ${keyObj.username}:${keyObj.key} http://${configs.coverity_host}:${configs.coverity_port}/api/v2/streams/${configs.coverity_stream}?locale=en_us", underUnix)
                def projectObj = readJSON text: projectStdout[0]
                configs.coverity_project = projectObj.streams[0].primaryProjectName
                print("covanalyze: got coverity project name ${configs.coverity_project}")
            }

            def exists = fileExists '.coverity.license.config'
            if (exists == false) {
                writeFile file: '.coverity.license.config', text: "#FLEXnet (do not delete this line)\nlicense-server 1123@papyrus.realtek.com\n"
            }
            def commitReportScript = covCmdPrefix + "cov-commit-defects -sf .coverity.license.config --dir ${configs.coverity_build_dir} --url http://${configs.coverity_host}:${configs.coverity_port} --stream \"${configs.coverity_stream}\" --auth-key-file \${KEY_PATH} --encryption none --preview-report-v2 preview_report_v2.json"
            def commitReportScriptWin = covCmdPrefix + "cov-commit-defects -sf .coverity.license.config --dir ${configs.coverity_build_dir} --url http://${configs.coverity_host}:${configs.coverity_port} --stream \"${configs.coverity_stream}\" --auth-key-file %KEY_PATH% --encryption none --preview-report-v2 preview_report_v2.json"
            def jsonReportScript = covCmdPrefix + "cov-format-errors -sf .coverity.license.config --dir ${configs.coverity_build_dir} --json-output-v8 defects.json --no-default-triage-filters --preview-report-v2 preview_report_v2.json"
            if (underUnix == true) {
                sh commitReportScript
                sh jsonReportScript
            }
            else {
                bat commitReportScriptWin
                bat jsonReportScript
            }
        }

        unstash "stash-covanalyzer-python-scripts"
        if (underUnix == true) {
            sh "chmod 755 defectsScissors.py && ./defectsScissors.py"
        }
        else {
            bat "python defectsScissors.py"
        }

        // Reports:
        // cov-generate-cvss-report: "cvssreport.json"
        //     1. get all defects in project (TODO: 'get all defects' is not necessary, for new CN3SD4 LESS_NOTIFICATION feature)
        //     2. defect's cvssSeverity
        // syn-generate-integrity-report: "coverity-issues.csv"
        dir (".cvss") {
            unstash "stash-covanalyzer-report-config"
            withCredentials([file(credentialsId: configs.coverity_auth_key_credential, variable: 'KEY_PATH')]) { //set SECRET with the credential content
                if (underUnix == true) {
                    sh "sed -i \"s/url:.*/url: http:\\/\\/${configs.coverity_host}:${configs.coverity_port}/g\" coverity_report_config.yaml"
                    sh "unset DISPLAY && WRITE_ISSUES_JSON=cvssreport.json ${configs.coverity_report_path}/cov-generate-cvss-report coverity_report_config.yaml --project ${configs.coverity_project} --auth-key-file \${KEY_PATH} --report --output cvss_tmp.pdf"
                    sh "chmod 755 ../cvssReportScissors.py && ../cvssReportScissors.py"
                }
                else {
                    def stdout
                    stdout = powershell(script: "get-content coverity_report_config.yaml | %{\$_ -replace \"url:.*\",\"url: http://${configs.coverity_host}:${configs.coverity_port}\"}", returnStdout: true)
                    writeFile file: 'coverity_report_config.yaml', text: stdout
                    bat "set WRITE_ISSUES_JSON=cvssreport.json&& \"${configs.coverity_report_path}\\cov-generate-cvss-report\" coverity_report_config.yaml --project ${configs.coverity_project} --auth-key-file %KEY_PATH% --report --output cvss_tmp.pdf"
                    bat "python ..\\cvssReportScissors.py"
                }
            }
        }

        // tips: read defects.json, due to 
        // 1. the strange windows file path in preview-report.json
        // 2. lacking fileds: impact, subcategoryShortDescription
        if (configs.coverity_analyze_defects_options.size() > 0) {
            // advanced analyze option enabled: CWE, OWASP, CVSS
            dir (".cvss") {
                withCredentials([file(credentialsId: configs.coverity_auth_key_credential, variable: 'KEY_PATH')]) { //set SECRET with the credential content
                    def curlCmd
                    def covCredentials = readJSON file: KEY_PATH
                    if (configs.coverity_snapshot == 0) {
                        // snapshot id not specified, got via rest api
                        def today = new Date()
                        today = today.format("yyyy-12-31")
                        curlCmd = """
                                curl --location \
                                    -X GET http://${configs.coverity_host}:${configs.coverity_port}/api/v2/streams/stream/snapshots?idType=byName&name=${configs.coverity_stream}&lastBeforeCodeVersionDate=${today}T00%3A00%3A00Z&locale=en_us \
                                    -H "Content-Type: application/json" \
                                    -H "Accept: application/json" \
                                    --user ${covCredentials.username}:${covCredentials.key} -s -o snapshots.json
                        """
                        if (underUnix == true) {
                            sh curlCmd
                        }
                        else {
                            bat curlCmd
                        }
                        def snapshotsObj = readJSON file: "snapshots.json"
                        configs.coverity_snapshot = snapshotsObj.snapshotsForStream.id[0]
                    }
                    // query snapshot version, description
                    curlCmd =  """
                            curl --location \
                                -X GET http://${configs.coverity_host}:${configs.coverity_port}/api/v2/snapshots/${configs.coverity_snapshot}?locale=en_us \
                                -H "Content-Type: application/json" \
                                -H "Accept: application/json" \
                                --user ${covCredentials.username}:${covCredentials.key} -s -o snapshot.json
                    """
                    if (underUnix == true) {
                        sh curlCmd
                    }
                    else {
                        bat curlCmd
                    }
                    def snapshotObj = readJSON file: "snapshot.json"
                    configs.snapshot_version = snapshotObj.sourceVersion
                    configs.snapshot_description = snapshotObj.description
                    if (underUnix == true) {
                        sh "sed -i \"s/snapshot-id:.*/snapshot-id: ${configs.coverity_snapshot}/g\" coverity_report_config.yaml"
                        sh """
                            unset DISPLAY
                            ${configs.coverity_report_path}/syn-generate-integrity-report coverity_report_config.yaml --project ${configs.coverity_project} --auth-key-file \${KEY_PATH} --output integrity_tmp.pdf
                            WRITE_SEVERITIES_CSV=severity.csv ${configs.coverity_report_path}/cov-generate-security-report coverity_report_config.yaml --project ${configs.coverity_project} --auth-key-file \${KEY_PATH} --output security_tmp.pdf
                        """
                    }
                    else {
                        def stdout
                        stdout = powershell(script: "get-content coverity_report_config.yaml | %{\$_ -replace \"snapshot-id:.*\",\"snapshot-id: ${configs.coverity_snapshot}\"}", returnStdout: true)
                        writeFile file: 'coverity_report_config.yaml', text: stdout
                        bat """
                            \"${configs.coverity_report_path}\\syn-generate-integrity-report\" coverity_report_config.yaml --project ${configs.coverity_project} --auth-key-file %KEY_PATH% --output integrity_tmp.pdf
                            set WRITE_SEVERITIES_CSV=severity.csv&& \"${configs.coverity_report_path}\\cov-generate-security-report\" coverity_report_config.yaml --project ${configs.coverity_project} --auth-key-file %KEY_PATH% --output security_tmp.pdf
                        """
                    }
                }
                // extract coverity-issues.csv from integrity_tmp.zip
                unzip zipFile: 'integrity_tmp.zip'

                // store CVSS, OWASP, CWE into rawCidInfos
                rawCidInfos = [:]
                def file = readFile "coverity-issues.csv"
                def lines = file.readLines()
                for (line in lines) {
                    if (line.startsWith("CID") == false) {
                        def columns = line.split(",")
                        def cid = columns[0].trim()
                        // ensure columns[0] is exactly a cid
                        def testCID = (cid ==~ /^[0-9]*$/)
                        if (testCID == false) {
                            continue
                        }
                        rawCidInfos."$cid" = [:]
                        rawCidInfos."$cid".owasp = false
                        rawCidInfos."$cid".cwe = false
                        if (columns[2].trim() != "") {
                            rawCidInfos."$cid".owasp = true
                        }
                        if (columns[3].trim() != "" && columns[3].toInteger() <= 25) {
                            rawCidInfos."$cid".cwe = true
                        }
                    }
                }
                extractSeverity(rawCidInfos)

                // cvssreport_.json generated by cvssReportScissors.py
                def cvssDefects = readJSON file: "cvssreport_.json"
                for (def i=0; i<cvssDefects.size(); i++) {
                    def cvssDefect = cvssDefects[i]
                    def cid = cvssDefect.cid
                    if (rawCidInfos.containsKey(cid) == true) {
                        rawCidInfos."$cid".cvss = cvssDefect.cvss
                    }
                }
                def cvssReportFile
                if (env.BUILD_BRANCH != null) {
                    cvssReportFile = "cvssreport-${env.BUILD_BRANCH}.json"
                }
                else {
                    cvssReportFile = "cvssreport.json"
                }
                if (underUnix == true) {
                    sh "mv cvssreport_.json ${cvssReportFile}"
                }
                else {
                    bat "move cvssreport_.json ${cvssReportFile}"
                }
                archiveArtifacts artifacts: cvssReportFile
            }

            for (analyzeDefectsOption in configs.coverity_analyze_defects_options) {
                def analyzedCids = analyzeCoverityIssues(analyzeDefectsOption, rawCidInfos)
                for (analyzedCid in analyzedCids) {
                    cidPools."${analyzedCid}" = true
                }
            }
            writeJSON file: 'cidsAnalyzed.json', json: cidPools
            if (underUnix == true) {
                sh "chmod 755 defectsAnalyzer.py && ./defectsAnalyzer.py"
            }
            else {
                def statusPython = bat script: "python --version", returnStatus: true
                def statusPython3 = bat script: "python3 --version", returnStatus: true
                if (statusPython == 0) {
                    bat 'python defectsAnalyzer.py'
                }
                else if (statusPython3 == 0) {
                    bat 'python3 defectsAnalyzer.py'
                }
            }
        }

        def analyzedDefects = [:]
        def cidsFoundAuthor = [:]
        // trick, variables define in stream, like "CN3SD8_${COV_PRJ_SUFFIX}_${PRECONFIG_SUFFIX}"
        analyzedDefects.host = configs.coverity_host
        analyzedDefects.port = configs.coverity_port
        analyzedDefects.assignPolicy = configs.coverity_defects_assign_policy
        analyzedDefects.snapshot = configs.coverity_snapshot
        analyzedDefects.snapshotVersion = configs.snapshot_version
        analyzedDefects.snapshotDescription = configs.snapshot_description
        //analyzedDefects.coverityProject = configs.coverity_project
        analyzedDefects.coverityStream = configs.coverity_stream
        analyzedDefects.defects = [:]
        appendIssueToAnalyzedDefects(analyzedDefects, cidsFoundAuthor, rawCidInfos, configs.coverity_defects_assign_policy)

        if (env.BUILD_BRANCH != null) {
            // under parallel build
            writeJSON file: "preview-report-committer-${env.BUILD_BRANCH}.json", json: analyzedDefects
            archiveArtifacts artifacts: "preview-report-committer-${env.BUILD_BRANCH}.json"
            print "Archive preview-report-committer-${env.BUILD_BRANCH}.json"
        }
        else {
            writeJSON file: "preview-report-committer.json", json: analyzedDefects
            archiveArtifacts artifacts: 'preview-report-committer.json'
            print "Archive preview-report-committer.json"
        }

        dir (".coverityDefects") {
            for (def cid in cidsFoundAuthor.keySet()) {
                print "get defect ${cid} html report"
                if (underUnix == true) {
                    sh "rm -rf ${cid}"
                    sh covCmdPrefix + "cov-format-errors --dir ../${configs.coverity_build_dir} --preview-report-v2 ../preview_report_v2.json --html-output ${cid} --cid ${cid}"
                }
                else {
                    bat "if exist ${cid} rd ${cid} /s /q"
                    bat covCmdPrefix + "cov-format-errors --dir ..\\${configs.coverity_build_dir} --preview-report-v2 ..\\preview_report_v2.json --html-output ${cid} --cid ${cid}"
                }
            }
        }

        /*
        def defectsReportFile
        if (env.BUILD_BRANCH != null) {
            defectsReportFile = "defectsReport-${env.BUILD_BRANCH}.zip"
        }
        else {
            defectsReportFile = "defectsReport.zip"
        }
        if (underUnix == true) {
            sh "rm -f ${defectsReportFile}"
        }
        else {
            bat "if exist ${defectsReportFile} del ${defectsReportFile} /s /q"
        }
        try {
            zip zipFile: defectsReportFile, dir: ".coverityDefects"
            archiveArtifacts artifacts: defectsReportFile
        }
        catch (e) {
            print "ZIP ${defectsReportFile} failed: " + e
        }
        */
    }
}

return this
