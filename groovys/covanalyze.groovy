def stashScriptsConfigs() {
    dir ("rtk_coverity") {
        stash name: "stash-covanalyzer-report-config", includes: "coverity_report_config.yaml"
    }
    dir("pipeline_scripts") {
        //stash name: "stash-covanalyzer-python-scripts", includes: "cvssReportScissors.py,defectsScissors.py,defectsAnalyzer.py"
        stash name: "stash-covanalyzer-python-scripts", includes: "covanalyze.py"
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
    stashScriptsConfigs()

    return config
}

def appendIssueToAnalyzedDefects(analyzedDefects, cidsFoundAuthor, assignPolicy) {
    def underUnix = isUnix()
    def defects = readJSON file: "defects_.json"

    for (def key in defects.keySet()) {
        def cid = key
        def defect = defects[key]
        def foundAuthor = false
        for (def j=0; j<defect.events.size(); j++) {
            def event = defect.events[j]

            def gitCommitter = event["committer"]
            def gitAuthor = event["author"]
            defect.events[j].committer = gitCommitter
            defect.events[j].author = gitAuthor
            if (assignPolicy == 'committer' && gitCommitter != '') {
                foundAuthor = true
            }
            else if (assignPolicy == 'author' && gitAuthor != '') {
                foundAuthor = true
            }
        }
        /*
        if (rawCidInfos.containsKey(cid)) {
            defect.cwe = rawCidInfos."${cid}".cwe
            defect.owasp = rawCidInfos."${cid}".owasp
            defect.cvss = rawCidInfos."${cid}".cvss
            defect.severity = rawCidInfos."${cid}".severity
        }
        */
        if (foundAuthor == true) {
            // push to cids (and then generate per cid html output) only if foundAuthor
            cidsFoundAuthor."${cid}" = true
        }
    }

    analyzedDefects.defects = defects
}

// TODO: dummy parameter pipelineAsCode, preloads
def func(pipelineAsCode, configs, preloads) {
    def underUnix = isUnix()
    def cidPools = [:]
    def defects
    def rawCidInfos = [:]

    unstash name: "stash-script-utils"
    def utils = load "utils.groovy"
    def pythonExec = utils.getPython()
    configs.coverity_stream = utils.captureStdout("echo ${configs.coverity_stream}", underUnix)
    configs.coverity_stream = configs.coverity_stream[0]

    def separator = "\\"
    if (underUnix == true) {
        separator = "/"
    }
    def covCmdPrefix = configs.coverity_scan_path
    if (covCmdPrefix != "") {
        covCmdPrefix = covCmdPrefix + separator
    }
    def covReportPath = configs.coverity_report_path
    if (covReportPath != "") {
        covReportPath = covReportPath + separator
    }

    if (configs.coverity_build_root == "") {
        configs.coverity_build_root = WORKSPACE
    }
    dir(configs.coverity_build_root) {
        withCredentials([file(credentialsId: configs.coverity_auth_key_credential, variable: 'KEY_PATH')]) {
            if (configs.coverity_project == "" || configs.coverity_project == null) {
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
            // tips: read defects.json, due to 
            // 1. the strange windows file path in preview-report.json
            // 2. lacking fileds: impact, subcategoryShortDescription
            def jsonReportScript = covCmdPrefix + "cov-format-errors -sf .coverity.license.config --dir ${configs.coverity_build_dir} --json-output-v8 defects.json --no-default-triage-filters --preview-report-v2 preview_report_v2.json"
            if (underUnix == true) {
                sh commitReportScript
                sh jsonReportScript
            }
            else {
                bat commitReportScriptWin
                bat jsonReportScript
            }

            // Reports
            dir (".cvss") {
                // cov-generate-cvss-report: "cvssreport.json"
                //     1. get all defects in project (TODO: 'get all defects' is not necessary, for new CN3SD4 LESS_NOTIFICATION feature)
                //     2. defect's cvssSeverity
                unstash "stash-covanalyzer-report-config"
                if (underUnix == true) {
                    sh "sed -i \"s/url:.*/url: http:\\/\\/${configs.coverity_host}:${configs.coverity_port}/g\" coverity_report_config.yaml"
                    sh "unset DISPLAY && WRITE_ISSUES_JSON=cvssreport.json ${covReportPath}cov-generate-cvss-report coverity_report_config.yaml --project ${configs.coverity_project} --auth-key-file \${KEY_PATH} --report --output cvss_tmp.pdf"
                }
                else {
                    def stdout
                    stdout = powershell(script: "get-content coverity_report_config.yaml | %{\$_ -replace \"url:.*\",\"url: http://${configs.coverity_host}:${configs.coverity_port}\"}", returnStdout: true)
                    writeFile file: 'coverity_report_config.yaml', text: stdout
                    bat "set WRITE_ISSUES_JSON=cvssreport.json&& \"${covReportPath}cov-generate-cvss-report\" coverity_report_config.yaml --project ${configs.coverity_project} --auth-key-file %KEY_PATH% --report --output cvss_tmp.pdf"
                }

                // advanced analyze option enabled: CWE, OWASP, CVSS
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
                // syn-generate-integrity-report: "coverity-issues.csv"
                if (underUnix == true) {
                    sh "sed -i \"s/snapshot-id:.*/snapshot-id: ${configs.coverity_snapshot}/g\" coverity_report_config.yaml"
                    sh """
                        unset DISPLAY
                        ${covReportPath}syn-generate-integrity-report coverity_report_config.yaml --project ${configs.coverity_project} --auth-key-file \${KEY_PATH} --output integrity_tmp.pdf
                        WRITE_SEVERITIES_CSV=severity.csv ${covReportPath}cov-generate-security-report coverity_report_config.yaml --project ${configs.coverity_project} --auth-key-file \${KEY_PATH} --output security_tmp.pdf
                    """
                }
                else {
                    def stdout
                    stdout = powershell(script: "get-content coverity_report_config.yaml | %{\$_ -replace \"snapshot-id:.*\",\"snapshot-id: ${configs.coverity_snapshot}\"}", returnStdout: true)
                    writeFile file: 'coverity_report_config.yaml', text: stdout
                    bat """
                        \"${covReportPath}syn-generate-integrity-report\" coverity_report_config.yaml --project ${configs.coverity_project} --auth-key-file %KEY_PATH% --output integrity_tmp.pdf
                        set WRITE_SEVERITIES_CSV=severity.csv&& \"${covReportPath}cov-generate-security-report\" coverity_report_config.yaml --project ${configs.coverity_project} --auth-key-file %KEY_PATH% --output security_tmp.pdf
                    """
                }
                // extract coverity-issues.csv from integrity_tmp.zip
                unzip zipFile: 'integrity_tmp.zip'
            }
        }

        writeJSON file: "analyzeOptions.json", json: configs.coverity_analyze_defects_options
        unstash "stash-covanalyzer-python-scripts"
        if (underUnix == true) {
            sh "${pythonExec} covanalyze.py"
        }
        else {
            bat "${pythonExec} covanalyze.py"
        }

        def analyzedDefects = [:]
        // TODO: cidsFoundAuthor no longer used
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
        appendIssueToAnalyzedDefects(analyzedDefects, cidsFoundAuthor, configs.coverity_defects_assign_policy)

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

        /*
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
