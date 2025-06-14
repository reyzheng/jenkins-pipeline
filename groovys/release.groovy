def checkConfig(config) {
    if (config.unified_release_flow == true) {
        if (config.release_sftp_key == "") {
            error("Warning: infra URF support ends in 2022 Mid. September, please set SMS ssh public key")
        }
        else {
            def sftpHost = "sdmft.rtkbf.com"
            def buildUrl = env.BUILD_URL.split('/')[2].split(':')[0]
            if (buildUrl.indexOf("-infra") > 0) {
                sftpHost = "rsdmft.rtkbf.com"
            }
            def urfUser = config.release_urf_user
            urfUser = urfUser.split("@")
            urfUser = urfUser[0]
            dir(".mfttest") {
                def statusCode
                def batFile = "bye"
                writeFile file: "bat", text: batFile
                withCredentials([sshUserPrivateKey(credentialsId: config.release_sftp_key, keyFileVariable: 'keyfile')]) {
                    if (isUnix() == true) {
                        statusCode = sh script: "sftp -P 22 -c aes128-cbc -b bat -o \"StrictHostKeyChecking=no\" -i \${keyfile} ${urfUser}@${sftpHost}", returnStatus: true
                    }
                    else {
                        statusCode = bat script: """
                            rem Icacls %keyfile% /c /t /Inheritance:d
                            rem Icacls %keyfile% /c /t /Grant %UserName%:F
                            rem TakeOwn /F %keyfile%
                            rem Icacls %keyfile% /c /t /Grant:r %UserName%:F
                            rem Icacls %keyfile% /c /t /Remove:g "Authenticated Users" BUILTIN\\Administrators BUILTIN Everyone System Users
                            rem sftp -P 22 -c aes128-cbc -b bat -o \"StrictHostKeyChecking=no\" -i %keyfile% ${urfUser}@${sftpHost}
                            echo skip
                        """, returnStatus: true
                    }
                }
                if (statusCode == 255) {
                    unstable("Warning: invalid SMS sftp key")
                }
            }
        }
    }
}

def init(stageName) {
    def defaultConfigs = [
        release_enabled: true,
        node: "",
        unified_release_flow: false,
        // ANT-style pattern
        unified_release_flow_files: [],
        unified_release_flow_config: "settings/URF/config",
        unified_release_flow_coverity_report: false,
        coverity_report_ignored: false,
        coverity_report_toolpath: "",
        coverity_report_config: "",
        coverity_report_latest_snapshot: false,
        unified_release_flow_coverity_projects: [],
        unified_release_flow_balckduck_report: false,
        unified_release_flow_blackduck_projects: [],
        unified_release_flow_blackduck_versions: [],
        unified_release_flow_user_reports: [],
        release_script_type: "",
        release_script: "",
        release_archive_artifacts: false,
        release_artifacts_path: "",
        release_urf_user: "",
        release_urf_reviewer: "",
        release_urf_receiver: "",
        release_urf_token: "",
        release_sftp_key: "",
        unified_release_flow_bom: "",
        coverity_report_key_credential: "",
        blackduckreport_token_credential: "",
        coverity_report_toolbox: "",
        unified_release_flow_toolbox: "",

        scriptableParams: [
            "unified_release_flow_coverity_projects", "unified_release_flow_blackduck_projects", "unified_release_flow_blackduck_versions",
            "release_urf_reviewer", "release_urf_receiver", "unified_release_flow_files"
        ]
    ]
    def utils = load "utils.groovy"
    def mapConfig = utils.commonInit(stageName, defaultConfigs)

    if (mapConfig["release_urf_token"] == "") {
        mapConfig["release_urf_user"] = env.PF_SMS_ACCOUNT
        mapConfig["release_urf_token"] = env.PF_SMS_CREDENTIALS
    }
    if (mapConfig["blackduckreport_token_credential"] == "") {
        mapConfig["blackduckreport_token_credential"] = env.PF_BD_CREDENTIALS
    }
    if (mapConfig["coverity_report_key_credential"] == "") {
        mapConfig["coverity_report_key_credential"] = env.PF_COV_CREDENTIALS
    }
    checkConfig(mapConfig)
    utils.finalizeInit(stageName, mapConfig)

    return mapConfig
}

//def exec(vars) {
def exec(stageName) {
    def configPath = "${WORKSPACE}/.pf-all/settings/${stageName}_config.json"
    print "Running on ${env.NODE_NAME}, at ${env.WORKSPACE}"

    def pythonExec = utils.getPython()
    def pyTranslate = "${pythonExec} ${env.PF_ROOT}/pipeline_scripts/utils.py -f ${env.PF_ROOT}/settings/${stageName}_config.json -c TRANSLATE_CONFIG"
    if (isUnix()) {
        sh pyTranslate
    }
    else {
        bat pyTranslate
    }

    def vars = readJSON file: configPath
    def underUnix = isUnix()
    if (vars.release_script_type == "inline") {
        utils.inlineScript(vars["release_script"], underUnix, "")
    }
    else if (vars.release_script_type != "") {
        utils.fileScript(underUnix, vars["release_script_type"], vars["release_script"], "", "", ".pf-${vars.plainStageName}")
    }

    try {
        if (vars.release_archive_artifacts == true) {
            archiveArtifacts artifacts: vars.release_artifacts_path
        }
    }
    catch (e) {
    }

    def plainStageName = vars["plainStageName"]

    if (vars["unified_release_flow"] == true) {
        // vars.unified_release_flow_bom
        // case 1: leave empty, got SBOM from source stage
        // case 2: source dir. specified
        // case 3: user-defined file
        // case 3.1: user-defined file not in jenkins-config repo, preloaded at init.
        // case 3.2: user-defined file in jenkins-config repo, reload here
        def urfBOM = ""
        if (vars["unified_release_flow_bom"] == "") {
            dir (".pf-${plainStageName}") {
                def stashes = []
                // case 1: release under specific build branch
                if (env.BUILD_BRANCH) {
                    stashes << "pf-revision-info-${env.BUILD_BRANCH}"
                }
                else {
                    // case 2: release after parallel builds
                    if (env.PF_GLOBAL_PARALLELINFO) {
                        unstash name: 'pf-global-parallelinfo'
                        def parallelInfo = readJSON file: 'parallelInfo.json'
                        for (def i=0; i<parallelInfo.branches.size(); i++) {
                            def buildBranch = parallelInfo.branches[i]
                            stashes << "pf-revision-info-${buildBranch}"
                        }
                    }
                    // case 3: release after single build
                    else {
                        stashes << "pf-revision-info"
                    }
                    print "exec(release): build branches ${stashes}"
                }
                dir ("revision_info") {
                    deleteDir()
                    for (def i=0; i<stashes.size(); i++) {
                        dir ("source_${i}") {
                            try {
                                unstash name: stashes[i]
                            }
                            catch (e) {}
                        }
                    }
                }
            }
            print "SBOM, got from source stage"
        }
        else if (vars["unified_release_flow_bom"].startsWith('source:') == true) {
            print "SBOM, user specified source location: " + vars["unified_release_flow_bom"]
        }
        else {
            print "SBOM, file content: " + vars["unified_release_flow_bom"]
        }

        dir (".pf-${plainStageName}/release_artifacts") {
            deleteDir()
            for (def ite=0; ite<vars["unified_release_flow_files"].size(); ite++) {
                def filename = vars["unified_release_flow_files"][ite]
                if (filename.startsWith('artifacts:')) {
                    // release artifacts
                    filename = filename.split(":")
                    filename = filename[1].trim()
                    step([$class: 'CopyArtifact', 
                            filter: filename, 
                            flatten: false, 
                            projectName: env.JOB_NAME, 
                            selector: [$class: 'SpecificBuildSelector', 
                            buildNumber: '${BUILD_NUMBER}'], 
                        target: './'])
                }
                else if (filename.startsWith('stash:')) {
                    // release artifacts
                    filename = filename.split(":")
                    filename = filename[1].trim()
                    unstash name: filename
                }
            }
        }
        for (def ite=0; ite<vars["unified_release_flow_user_reports"].size(); ite++) {
            def filename = vars["unified_release_flow_user_reports"][ite]
            if (filename.startsWith('artifacts:')) {
                // release artifacts
                filename = filename.split(":")
                filename = filename[1].trim()
                dir (".pf-${plainStageName}/report_artifacts") {
                    step([$class: 'CopyArtifact',
                            filter: filename,
                            flatten: false,
                            projectName: env.JOB_NAME,
                            selector: [$class: 'SpecificBuildSelector',
                            buildNumber: '${BUILD_NUMBER}'],
                        target: './'])
                }
            }
            else if (filename.startsWith('stash:')) {
                // release artifacts
                filename = filename.split(":")
                filename = filename[1].trim()
                dir (".pf-${plainStageName}/report_artifacts") {
                    unstash name: filename
                }
            }
        }

        def creds = []
        def credURF = string(credentialsId: vars["release_urf_token"], variable: 'SMS_TOKEN')
        def credMFT = sshUserPrivateKey(credentialsId: vars["release_sftp_key"], keyFileVariable: 'MFT_KEY')
        creds.add(credURF)
        creds.add(credMFT)
        if (vars["unified_release_flow_coverity_report"] == true) {
            def credCOV = file(credentialsId: vars["coverity_report_key_credential"], variable: 'COV_AUTH_KEY')
            creds.add(credCOV)
        }
        if (vars["unified_release_flow_balckduck_report"] == true) {
            def credBD = string(credentialsId: vars["blackduckreport_token_credential"], variable: 'BD_TOKEN')
            creds.add(credBD)
        }
        withCredentials(creds) {
            def underSD = "-e OA"
            def buildUrl = env.BUILD_URL.split('/')[2].split(':')[0]
            if (buildUrl.indexOf("-infra") > 0) {
                underSD = "-e SD"
            }
            def pyCmd = "${pythonExec} $WORKSPACE/.pf-all/pipeline_scripts/release.py -r .pf-all -f $configPath -w .pf-${plainStageName} -j $WORKSPACE $underSD"
            if (isUnix()) {
                sh pyCmd
            }
            else {
                bat pyCmd
            }
        }
        dir("urf_package/reports") {
            archiveArtifacts artifacts: "blackduck*.csv", allowEmptyArchive: true
            archiveArtifacts artifacts: "coverity*.pdf", allowEmptyArchive: true
            archiveArtifacts artifacts: "coverity*.xml", allowEmptyArchive: true
        }
        dir (".pf-${plainStageName}") {
            utils.exportEnv()
        }
    }
}

def func(stageName) {
    def stageConfig = readJSON file: ".pf-all/settings/${stageName}_config.json"
    def plainStageName = stageConfig["plainStageName"]

    if (stageConfig['release_enabled'] == false) {
        print "Skip release"
        return
    }
    exec(stageName)
}

return this
