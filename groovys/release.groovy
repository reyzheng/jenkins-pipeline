def checkConfig(config) {
    def settings = config.settings
    def preloads = config.preloads

    if (settings.unified_release_flow_balckduck_report == true) {
        dir ("groovys") {
            stash name: "stash-actions-blackduckreport", includes: "blackduckreport.groovy"
        }
    }
    if (settings.unified_release_flow_coverity_report == true) {
        dir ("groovys") {
            stash name: "stash-actions-coverityreport", includes: "coverityreport.groovy"
        }
    }

    if (settings.unified_release_flow == true) {
        if (settings.release_sftp_key == "") {
            error("Warning: infra URF support ends in 2022 Mid. September, please set SMS ssh public key")
        }
        else {
            def sftpHost = "sdmft.rtkbf.com"
            def buildUrl = env.BUILD_URL.split('/')[2].split(':')[0]
            if (buildUrl.indexOf("-infra") > 0) {
                sftpHost = "rsdmft.rtkbf.com"
            }
            def urfUser = settings.release_urf_user
            urfUser = urfUser.split("@")
            urfUser = urfUser[0]
            dir(".mfttest") {
                def statusCode
                def batFile = "bye"
                writeFile file: "bat", text: batFile
                withCredentials([sshUserPrivateKey(credentialsId: settings.release_sftp_key, keyFileVariable: 'keyfile')]) {
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
        unified_release_flow_files: [],
        unified_release_flow_config: "settings/URF/config",
        unified_release_flow_coverity_report: false,
        coverity_report_ignored: false,
        coverity_report_toolpath: "",
        coverity_report_config: "",
        unified_release_flow_coverity_projects: [],
        unified_release_flow_balckduck_report: false,
        unified_release_flow_blackduck_projects: [],
        unified_release_flow_blackduck_versions: [],
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

    if (mapConfig["settings"]["release_urf_token"] == "") {
        mapConfig["settings"]["release_urf_user"] = env.PF_SMS_ACCOUNT
        mapConfig["settings"]["release_urf_token"] = env.PF_SMS_CREDENTIALS
    }
    if (mapConfig["settings"]["blackduckreport_token_credential"] == "") {
        mapConfig["settings"]["blackduckreport_token_credential"] = env.PF_BD_CREDENTIALS
    }
    if (mapConfig["settings"]["coverity_report_key_credential"] == "") {
        mapConfig["settings"]["coverity_report_key_credential"] = env.PF_COV_CREDENTIALS
    }
    if (mapConfig["settings"]["release_enabled"] == true && mapConfig["settings"]["unified_release_flow"] == true) {
        if (mapConfig["settings"]["unified_release_flow_bom"] == "") {
            // hint 'source' action to generate SBOM on-the-fly
            env.PF_SOURCE_REVISION = "true"
        }
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
        if (underUnix == true) {
            sh vars.release_script
        }
        else {
            bat vars.release_script
        }
    }
    else if (vars.release_script_type != "") {
        def dstFile = ".pf-all/scripts/" + vars["release_script"]

        if (vars.release_script_type == "source") {
            sh ". " + dstFile
        }
        else if (vars.release_script_type == "groovy") {
            def externalMethod = load(dstFile)
            externalMethod.func()
        }
        else if (vars.release_script_type == "file") {
            if (underUnix == true) {
                sh "sh " + dstFile
            }
            else {
                bat ".pf-all\\scripts\\" + vars["release_script"]
            }
        }
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
            try {
                def stashName = 'pf-revision-info'
                if (env.BUILD_BRANCH) {
                    stashName += "-${env.BUILD_BRANCH}"
                }
                unstash name: stashName
            }
            catch (e) {}
            try {
                def jsonGitInfo = readJSON file: '.pf-revision-info'
                // git
                def originRemote
                urfBOM = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
                urfBOM += "<manifest>\n"
                for (def i=0; i<jsonGitInfo.sources.size(); i++) {
                    def revision = jsonGitInfo.sources[i]
                    if (i == 0) {
                        urfBOM += "<remote fetch=\"${revision.addr}\" name=\"origin\" />\n"
                        urfBOM += "<default remote=\"origin\" revision=\"master\" />\n"
                        // take the 0th source as origin remote
                        originRemote = revision.addr
                    }
                    else {
                        if (originRemote != revision.addr) {
                            urfBOM += "<remote fetch=\"${revision.addr}\" name=\"remote${i}\" />\n"
                        }
                    }
                    if (originRemote == revision.addr) {
                        urfBOM += "<project name=\"${revision.name}\" path=\"${revision.path}\" revision=\"${revision.revision}\" upstream=\"${revision.upstream}\"/>\n"
                    }
                    else {
                        urfBOM += "<project name=\"${revision.name}\" path=\"${revision.path}\" revision=\"${revision.revision}\" upstream=\"${revision.upstream}\" remote=\"remote${i}\"/>\n"
                    }
                }
                urfBOM += "</manifest>"
            }
            catch (e) {
                // repo
                urfBOM = readFile '.pf-revision-info'
            }
            writeFile file: 'URFSBOM', text: urfBOM
            print "SBOM, got from source stage"
        }
        else if (vars["unified_release_flow_bom"].startsWith('source:') == true) {
            print "SBOM, user specified source location: " + vars["unified_release_flow_bom"]
        }
        else {
            print "SBOM, file content: " + vars["unified_release_flow_bom"]
        }

        for (def ite=0; ite<vars["unified_release_flow_files"].size(); ite++) {
            filename = vars["unified_release_flow_files"][ite]
            if (filename.startsWith('artifacts:')) {
                // release artifacts
                filename = filename.split(":")
                filename = filename[1].trim()
                dir (".pf-${plainStageName}/release_artifacts") {
                    step([$class: 'CopyArtifact', 
                            filter: filename, 
                            flatten: false, 
                            projectName: env.JOB_NAME, 
                            selector: [$class: 'SpecificBuildSelector', 
                            buildNumber: '${BUILD_NUMBER}'], 
                        target: './'])
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
            def underSD = "-e RT_OA"
            def buildUrl = env.BUILD_URL.split('/')[2].split(':')[0]
            if (buildUrl.indexOf("-infra") > 0) {
                underSD = "-e RT_SD"
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

        // parse URFRESULT, save env.PIPELINE_AS_CODE_URF_ID
        def SMSURFId = 0
        def fpURF = readFile(file: 'URFRESULT')
        def lines = fpURF.readLines()
        lines.each { line ->
            if (line.indexOf("sms_id") >= 0) {
                def firstColon = line.indexOf(":")
                def jsonURF = line.substring(firstColon + 1, line.length())
                try {
                    def jsonObject = readJSON text: jsonURF
                    if (jsonObject["msg"] == "Success") {
                        SMSURFId = jsonObject["sms_id"].toInteger()
                    }
                    else {
                        print "URF error message: ${jsonObject.msg}"
                    }
                }
                catch (e) {
                }
            }
        }
        env.PIPELINE_AS_CODE_URF_ID = SMSURFId
        env.PIPELINE_AS_CODE_URF_INFO = plainStageName
        print "SMS URF ID: ${SMSURFId}"
        if (SMSURFId == 0) {
            error("${vars.stageName}: URF failed")
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
    if (stageConfig['node'] == "" || env.NODE_NAME == stageConfig['node']) {
        exec(stageName)
    }
    else {
        node(stageConfig['node']) {
            utils.unstashPipelineFramework()
            exec(stageName)
        }
    }
}

return this
