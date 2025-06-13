import groovy.transform.Field


@Field modules = [:]
@Field utils

// GLOBAL
//   env.PF_FRAMEWORK_URL (defined in Jenkinsfile.appetizer)
//   env.PF_FRAMEWORK_PROD_BRANCH (defined in Jenkinsfile.appetizer)
//   env.PF_FRAMEWORK_DEV_BRANCH (defined in Jenkinsfile.appetizer)
//   env.PF_MAIN_AGENT
//   env.PF_CLEAN_WS
//   env.PF_PRESERVE_SOURCE
//   env.PF_SLURM_CREDENTIALS
//   env.PF_GERRIT_CREDENTIALS
//   env.PF_GERRIT_CREDENTIALS_MAIN
//   env.PF_COV_CREDENTIALS
//   env.PF_BD_CREDENTIALS
//   env.PF_SMS_ACCOUNT
//   env.PF_SMS_CREDENTIALS
//   env.PF_GLOBAL_PARALLELINFO
//   env.PF_PATH (PF configuration included in source, like ci, ends with /)
//   env.PF_GLOBAL_STAGES, all stages found in global_config, for stage iteration, corresponding configs finding
//   env.PF_GLOBAL_NODES
//   env.PF_CORE_ACTIONS
//   env.PF_STAGES
//   env.PF_ROOT (.pf-all)
//   env.PF_HTMLREPORTS
//   env.PF_BASEWORKSPACE (WORKSPACE before composition)
//   env.PF_POST_STAGE
//   env.PF_SHORT_WORKSPACE
// SOURCE
//   env.PF_SOURCE_WORKDIR
//   env.PF_SOURCE_DSTS
//   env.PF_SOURCE_TYPE_{i}
//   env.PF_SOURCE_DST_{i}
//   env.PF_GERRIT_PATCHSET_DIFF_FILES_{i}
// COVERITY
//   env.PF_COV_HOST
//   env.PF_COV_PORT
//   env.PF_COV_CREDENTIALS
//   env.COVERITY_FAILURE_BUILD
//   env.COVERITY_EMPTY_ANALYSIS
//   env.PF_COV_DETAILED_HTML_REPORT
//   env.PF_COV_DETAILED_HTML_REPORT_DIR
// CODEPROMPT
//   env.PF_CODEPROMPT_RESULT
// CODETEK
//   env.PF_CODETEK_COV_ANALYSIS_ADVISE
//   env.PF_REALGPT_KEY


def checkConfigPath() {
    env.PF_PATH = ""
    env.PF_STAGES = ""
    env.PF_HTMLREPORTS = ""
    // test if settings, scripts located under workspace
    def fileSeparator = "\\"
    if (isUnix()) {
        fileSeparator = "/"
    }

    def lastModified = 0
    def configFiles = findFiles glob: "**/global_config.json"
    for (def i=0; i<configFiles.size(); i++) {
        def settingsPath = configFiles[i].path
        print "checkConfigPath: check config at ${settingsPath}"
        if (settingsPath.startsWith('.pf-config') || settingsPath.startsWith('.pf-all')) {
            print "checkConfigPath: ignore config at ${settingsPath}"
            continue
        }

        settingsPath = settingsPath.substring(0, settingsPath.lastIndexOf(fileSeparator) - 8)
        if (configFiles[i].lastModified > lastModified) {
            env.PF_PATH = settingsPath
            lastModified = configFiles[i].lastModified
            print "checkConfigPath: Pipeline configurations under ${settingsPath}"
        }
    }

    print "checkConfigPath: env.PF_PATH ${env.PF_PATH}"
}

def translateGlobalSettings() {
    def utilsPath = "${env.PF_PATH}pipeline_scripts/utils.py"
    def utilsUnderPFPath = fileExists utilsPath
    if (utilsUnderPFPath == false) {
        // old-style Jenkinsfile
        utilsPath = "pipeline_scripts/utils.py"
    }
    def pythonExec = utils.getPython()

    def configFiles = findFiles (glob: "${env.PF_PATH}settings/source*_config.json,${env.PF_PATH}settings/global_config.json")
    for (def i=0; i<configFiles.size(); i++) {
        def configFilePath = configFiles[i].path
        print "translateGlobalSettings: ${configFilePath}"
        def translateCmd = "${pythonExec} ${utilsPath} -f ${configFilePath} -c TRANSLATE_CONFIG"
        if (isUnix()) {
            sh translateCmd
        }
        else {
            // env.PF_PATH -> JenkinsCI
            bat translateCmd
        }
    }
}

def loadGlobalSettings() {
    def defaultConfigs = [
        clean_ws: true,
        preserve_source: false,
        stages: [],
        nodes: [],

        // singularity, docker, slurm
        build_env: "none",
        // singularity image path for singularity exece
        // docker name for docker run
        // slurm IP address for REST API call
        build_image: "",
        // params for singularity exec
        // params for docker run
        build_params: "",

        slurm_credentials: "",
        gerrit_credentials: "",
        coverity_credentials: "",
        blackduck_credentials: "",
        sms_account: "",
        sms_credentials: "",

        // TODO: merge modules.configs["post"]
        post_scripts_condition: [],
        post_scripts_type: [],
        post_scripts: [],
        mail_enabled: false,
        mail_conditions: ["always"],
        mail_subject: "",
        mail_body: "",
        mail_attachment: "",
        mail_recipient: ""
    ]

    def globalVars = utils.commonInit("global", defaultConfigs)
    utils.finalizeInit("global", globalVars)
    // TODO: modules.global_vars = globalVars['settings']?
    def globalConfigs = readJSON file: "${env.PF_PATH}settings/global_config.json"

    env.PF_CLEAN_WS = globalConfigs["clean_ws"]
    env.PF_PRESERVE_SOURCE = globalConfigs["preserve_source"]
    env.PF_SLURM_CREDENTIALS = globalConfigs["slurm_credentials"]
    env.PF_GERRIT_CREDENTIALS = globalConfigs["gerrit_credentials"]
    env.PF_COV_CREDENTIALS = globalConfigs["coverity_credentials"]
    env.PF_BD_CREDENTIALS = globalConfigs["blackduck_credentials"]
    env.PF_SMS_ACCOUNT = globalConfigs["sms_account"]
    env.PF_SMS_CREDENTIALS = globalConfigs["sms_credentials"]
    if (globalConfigs["build_env"] == "docker") {
        env.PF_BUILD_ENV = "docker:" + globalConfigs["build_image"]
        env.PF_BUILD_ENV_PARAMS = globalConfigs["build_params"]
    }
    else if (globalConfigs["build_env"] == "singularity") {
        env.PF_BUILD_ENV = "singularity:" + globalConfigs["build_image"]
        env.PF_BUILD_ENV_PARAMS = globalConfigs["build_params"]
    }
    else if (globalConfigs["build_env"] == "slurm") {
        env.PF_BUILD_ENV = "slurm:" + globalConfigs["build_image"]
    }
    else {
        env.PF_BUILD_ENV = "none"
        env.PF_BUILD_ENV_PARAMS = ""
    }
    env.PF_GLOBAL_STAGES = utils.jsonArrayToString(globalConfigs["stages"], ",")
    env.PF_GLOBAL_NODES = utils.jsonArrayToString(globalConfigs["nodes"], ",")
}

def preparePostStage() {
    // html report
    def htmlContent = ""
    def hasHtmlReport = false

    def reports = env.PF_HTMLREPORTS.split(",")
    reports = reports.sort()
    print ("preparePostStage: reports ${reports}")
    for (def i=0; i<reports.size(); i++) {
        def htmlreportExists
        if (reports[i] == "") {
            continue
        }
        dir (".pf-htmlreport") {
            deleteDir()
            unstash name: reports[i]
            htmlreportExists = fileExists "pf-htmlreport.html"
        }
        reportTitle = reports[i].split("-")
        if (htmlreportExists == true) {
            publishHTML (target : [allowMissing: true,
                    alwaysLinkToLastBuild: true,
                    keepAll: true,
                    reportDir: '.pf-htmlreport',
                    reportFiles: 'pf-htmlreport.html',
                    reportName: "PipelineReports-" + reportTitle[1],
                    reportTitles: reportTitle[1]])
        }
    }
}

def emailNotification() {
    // leave empty for backward compatibility
}

def postStage(postStatus) {
    def action
    print "postStage: NODE ${env.NODE_NAME}"
    print "postStage: PF_MAIN_AGENT ${env.PF_MAIN_AGENT}"
    if (env.NODE_NAME == env.PF_MAIN_AGENT) {
        action = utils.loadCoreAction(env.PF_ROOT, "post")
        action.execute(modules, postStatus)
    }
    else {
        node(env.PF_MAIN_AGENT) {
            action = utils.loadCoreAction(env.PF_ROOT, "post")
            action.execute(modules, postStatus)
        }
    }
}

def loadCoreActions() {
    // lookup files under groovyPath
    def actionFiles
    def coreActions = []

    dir ('groovys') {
        actionFiles = findFiles(glob: "*.groovy")
        print "Found actions " + actionFiles
        for (actionFile in actionFiles) {
            def actionFileName = actionFile.toString()
            def actionName = actionFileName.split(/\\|\/|\./)
            // groovys/source.groovy -> groovy source groovy
            actionName = actionName[0]
            coreActions << actionName
        }
    }
    // TODO: ugly code
    coreActions += ["config", "prebuild", "build", "postbuild", "test"]
    env.PF_CORE_ACTIONS = coreActions.join(",")
}

def loadUserConfig(configFileName) {
    // settings/build-dummy_config.groovy -> settings "build-dummy_config" groovy
    def configName = configFileName.split(/\\|\/|\./)
    configName = configName[configName.size() - 2]
        
    // urf_license_checker_config-dummy_config -> "urf_license_checker_config-dummy" config
    def breakPos = configName.lastIndexOf("_")
    def stageName = configName.substring(0, breakPos)
    def actionName = utils.extractActionName(stageName)
    env.PF_STAGES = env.PF_STAGES + "${actionName},"
    def realActionName = utils.extractRealActionName(stageName)

    print "loadUserConfigs: ${stageName}(${actionName})"
    // TODO: refer to Jenkinsfile.appetizer
    // stash name: "pf-config", includes: "**/settings/**,**/scripts/**"
    // stash name: "pf-framework", includes: "**"
    // pf-config may be included under sub directory, like JenkinsCI (PF_PATH)
    // pf-framework does not face the issue, ie. "sub directory"
    def coreActions = env.PF_CORE_ACTIONS.split(",")
    def action
    if (coreActions.contains(actionName)) {
        action = utils.loadCoreAction("", actionName)
    }
    else {
        // user defined actions could also load configs
        action = utils.loadUserAction(PF_PATH, actionName)
    }
    try {
        action.init(stageName)
        print "loadUserConfigs: ${stageName}(${actionName}) configured"
    }
    catch (e) {
        // easyActions has no configurations
        unstable("${stageName} (${actionName}) init. failed " + e)
    }

    if (actionName == "composition") {
        def stageConfig = readJSON file: "${env.PF_PATH}settings/${stageName}_config.json"
        if (stageConfig["run_type"] == "MULTI") {
            for (def i=0; i<stageConfig["stages"].size(); i++) {
                for (def subStage in stageConfig["stages"][i]) {
                    loadUserConfig(env.PF_PATH + "settings/${subStage}_config.groovy")
                }
            }
        }
        else {
            for (def subStage in stageConfig["stages"]) {
                loadUserConfig(env.PF_PATH + "settings/${subStage}_config.groovy")
            }
        }
    }
}

def loadUserConfigs() {
    def fileSeparator = "\\"
    if (isUnix()) {
        fileSeparator = "/"
    }

    // Load user config
    def requiredConfigs = []
    def globalStages = env.PF_GLOBAL_STAGES.split(",")
    for (def i=0; i<globalStages.size(); i++) {
        def stage = globalStages[i]
        requiredConfigs << env.PF_PATH + "settings${fileSeparator}${stage}_config.groovy"
    }

    // Load ugly coverity_config
    dir (env.PF_PATH + "settings") {
        def coverityGroovyExists = fileExists "coverity_config.groovy"
        def coverityJsonExists = fileExists "coverity_config.json"
        if (coverityGroovyExists || coverityJsonExists) {
            requiredConfigs << env.PF_PATH + "settings${fileSeparator}coverity_config.groovy"
        }
    }

    // Load post_config
    def postAction = utils.loadCoreAction("", "post")
    def postConfig = postAction.init()
    // Load required scripts in post_config
    for (def i=0; i<postConfig.post_scripts_type.size(); i++) {
        if (postConfig.post_scripts_type[i] == "action") {
            def stage = postConfig.post_scripts[i]
            requiredConfigs << env.PF_PATH + "settings${fileSeparator}${stage}_config.groovy"
        }
    }

    // Load user configs
    print "Total configs to be loaded " + requiredConfigs
    for (requiredConfig in requiredConfigs) {
        loadUserConfig(requiredConfig)
    }
}

def pascCleanWs() {
    if (isUnix() == true) {
        def whoami = sh(script: "whoami", returnStdout: true).trim()
        if (whoami == "root") {
            error("Do not run jenkins agent as root")
        }
    }

    if (env.PF_CLEAN_WS == "false") {
        print "pascCleanWs: skip"
        return
    }
    def excludes = [[pattern: "${env.PF_ROOT}/**", type: "EXCLUDE"]]
    if (env.PF_PRESERVE_SOURCE == "true") {
        if (env.PF_SOURCE_DSTS) {
            def scmDsts = env.PF_SOURCE_DSTS.split(",")
            for (def j=0; j<scmDsts.size(); j++) {
                def exclude = [:]
                exclude.pattern = "${scmDsts[j]}/**"
                exclude.type = "EXCLUDE"
                excludes << exclude
            }
        }
    }
    print "pascCleanWs: clean WS, excludes: " + excludes
    cleanWs deleteDirs: true, notFailBuild: true, patterns: excludes
}

def init() {
    def underUnix = isUnix()
    utils = load "utils.groovy"
    // store exec. result at each stage
    env.PIPELINE_AS_CODE_STAGE_BUILD_RESULTS = ""
    env.PIPELINE_AS_CODE_STAGE_TEST_RESULTS = ""

    checkConfigPath()
    // 1. translate global config before load
    // 2. translate necessary configs, source, to get checkout directory to preserve
    translateGlobalSettings()
    // load global_config
    loadGlobalSettings()
    
    // stage pre-initialization is necessary:
    // pipeline from scm was done at master node, 
    // groovy loading would be failed after jobs dispatched to agents

    loadCoreActions()
    loadUserConfigs()
    dir ("pipeline_scripts") {
        def licenseInfo = ''
        if (env.BUILD_URL && env.BUILD_URL.startsWith("https://rs")) {
            if (underUnix) {
                licenseInfo = "PSP_LICENSE_SERVER=5679@172.29.82.1 "
            }
            else {
                licenseInfo = "set PSP_LICENSE_SERVER=5679@172.29.82.1&&"
            }
        }
        try {
            if (underUnix) {
                sh "${licenseInfo}ACTIONS=${env.PF_STAGES} ./wrapper_pipeline_linux -s CTCSOCPIPELINE"
            }
            else {
                bat "${licenseInfo}set ACTIONS=${env.PF_STAGES}&&wrapper_pipeline_win.exe -s CTCSOCPIPELINE"
            }
        }
        catch (e) {}
    }

    // clean workspace
    // stash utils before clean workspace
    // re-write logParserRule after initialization
    stash name: 'stash-pf-framework', includes: "groovys/**,pipeline_scripts/**,templates/**,rtk_coverity/**,vendor/**"
    dir (env.PF_PATH) {
        stash name: 'stash-pf-config', includes: "Jenkinsfile*,settings/**,scripts/**"
    }
    // note: for Jenkinsfile.restartable
    // iterateStages() would not be called in Jenkinsfile.restartable
    utils.unstashPipelineFramework()

    pascCleanWs()
}

def iterateToFile(stages, sourceOnly) {
	if (! utils) {
		utils = load 'utils.groovy'
	}
    def stageConfig
    def content = ""
    if (stages.size() > 0) {
        for (def stageIdx=0; stageIdx<stages.size(); stageIdx++) {
            def stageName = stages[stageIdx]
			def actionName = utils.extractActionName(stageName)
            if (sourceOnly == true && actionName != "source") {
                continue
            }

            def realStageName = stageName
            try {
                dir (env.PF_PATH + 'settings') {
                    stageConfig = readJSON file: "${stageName}_config.json"
                    if (stageConfig.containsKey("display_name")) {
                        realStageName = stageConfig["display_name"]
                    }
                }
            }
            catch(e) {
                print "iterateToFile exception: " + e
            }

            if (actionName == "composition" && stageConfig.run_type == "SEQUENTIAL_SPLIT") {
                for (def i=0; i<stageConfig.stages.size(); i++) {
                    content += "stage('$realStageName-$i') {\n"
                    content += "    steps {\n"
                    content += "        script {\n"
                    content += "            if (!pf) {\n"
                    content += "                pf = pfInit(true)\n";
                    content += "            }\n"
                    content += "            pf.startCompositionSplit('$stageName', $i)\n"
                    content += "        }\n"
                    content += "    }\n"
                    content += "}\n"
                }
            }
            else {
                def stageNode = false
                content += "stage('$realStageName') {\n"
                if (stageConfig.containsKey("node") == true && stageConfig["node"] != "") {
                    if (actionName == "composition") {
                        // skip node config in composition_config
                        // node config is adopted in parallelBuild()
                        print("composition, skip node config in composition_config")
                    }
                    else {
                        stageNode = true
                        if (stageConfig["node"].startsWith("docker:") == true) {
                            def dockerImage = stageConfig["node"].split(":")
                            dockerImage = dockerImage[1]
                            content += "agent {\n"
                            content += "    docker {\n"
                            content += "        image \"${dockerImage}\"\n"
                            if (stageConfig.containsKey("node_args") == true && stageConfig["node_args"] != "") {
                                content += "        args \"" + stageConfig["node_args"] + "\"\n"
                            }
                            content += "        reuseNode true\n"
                            content += "    }\n"
                            content += "}\n"
                        }
                        else {
                            content += "agent {\n"
                            content += "    label \"${stageConfig['node']}\"\n"
                            content += "}\n"
                        }
                    }
                }
                def userDefinedStageOptions = fileExists "${env.PF_PATH}scripts/${stageName}.options"
                if (userDefinedStageOptions == true) {
                    content += readFile file: "${env.PF_PATH}scripts/${stageName}.options"
                }
                content += "    steps {\n"
                def credLines = ['', '']
                def userDefinedCredentials = fileExists "${env.PF_PATH}scripts/${stageName}.creds"
                if (userDefinedCredentials == true) {
                    def fpCreds = readFile "${env.PF_PATH}scripts/${stageName}.creds"
                    credLines = fpCreds.readLines()
                }
                content += credLines[0]
                content += "        script {\n"
                if (stageNode == true) {
                    content += "            def pfTmp = pfInit(false)\n";
                    if (actionName == "composition") {
                        content += "        pfTmp.startComposition('$stageName')\n"
                    }
                    else {
                        content += "        pfTmp.execStage('$actionName', '$stageName')\n"
                    }
                }
                else {
                    content += "            if (!pf) {\n"
                    content += "                pf = pfInit(true)\n";
                    content += "            }\n"
                    if (actionName == "composition") {
                        content += "            pf.startComposition('$stageName')\n"
                    }
                    else {
                        content += "            pf.execStage('$actionName', '$stageName')\n"
                    }
                }
                content += "        }\n"
                content += credLines[1]
                content += "    }\n"
                content += "}\n"
            }
        }
    }
	return content
}

def execStage(actionName, stageName) {
    print "execStage: ${stageName}(${actionName})"
    //utils.resetPython()
    def coreActions = env.PF_CORE_ACTIONS.split(",")
    if (coreActions.contains(actionName)) {
        def action = utils.loadCoreAction(env.PF_ROOT, actionName)
        action.func(stageName)
    }
    else {
        def action = utils.loadUserAction(env.PF_ROOT, actionName)
        try {
            def configExists = fileExists "${env.PF_ROOT}/settings/${stageName}_config.json"
            if (configExists) {
                print "execStage: user action with config"
                def stageConfig = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"
                action.func(modules, stageConfig, null)
            }
            else {
                print "execStage: user action without config"
                action.func()
            }
        }
        catch (e) {
            error(message: "${stageName} is unstable " + e)
        }
    }        
}

def _format(withNodeLabel) {
    checkConfigPath()

    def globalConfig
    dir (env.PF_PATH + 'settings') {
        globalConfig = readJSON file: 'global_config.json'
    }
    if (! utils) {
        utils = load 'utils.groovy'
    }

    def nodeSection
    def nodeLabel = ""
    if (withNodeLabel) {
        if (globalConfig.nodes.size() > 0) {
            nodeLabel = globalConfig.nodes[0]
        }
        nodeSection = "def nodeLabel='$nodeLabel'\n"
    }
    else {
        nodeSection = ""
    }
    def stages = globalConfig.stages
    def initHalf
    def topHalf
    def optionHalf
    def triggersHalf
    def startHalf
    def bottomHalf
    dir ('pipeline_scripts') {
        initHalf = readFile file: 'Jenkinsfile.inithalf'
        if (withNodeLabel) {
            print ("_format: user defined agent ${nodeLabel}")
            print ("_format: current agent ${env.NODE_LABELS}")
            if (nodeLabel == "" || env.NODE_LABELS.contains(nodeLabel)) {
                topHalf = readFile file: 'Jenkinsfile.tophalf.none'
            }
            else {
                topHalf = readFile file: 'Jenkinsfile.tophalf'
            }
        }
        else {
            topHalf = readFile file: 'Jenkinsfile.tophalf.none'
        }
        optionHalf = readFile file: "Jenkinsfile.options"
        triggersHalf = readFile file: "Jenkinsfile.triggers"
        startHalf = readFile file: "Jenkinsfile.starthalf"
        bottomHalf = readFile file: 'Jenkinsfile.bottomhalf'
    }
    dir (env.PF_PATH + 'scripts') {
        def userDefinedOptions = fileExists "Jenkinsfile.options"
        if (userDefinedOptions == true) {
            optionHalf = readFile file: "Jenkinsfile.options"
        }
        def userDefinedTriggers = fileExists "Jenkinsfile.triggers"
        if (userDefinedTriggers == true) {
            triggersHalf = readFile file: "Jenkinsfile.triggers"
        }
    }
    def sourceOnly = false
    if (globalConfig.dagger) {
        sourceOnly = true
    }
    def content = iterateToFile(stages, sourceOnly)

    print "Jenkinsfile generated"
    print nodeSection + initHalf + topHalf + optionHalf + triggersHalf + startHalf + content + bottomHalf
    writeFile file: 'Jenkinsfile.restartable', text: nodeSection + initHalf + topHalf + optionHalf + triggersHalf + startHalf + content + bottomHalf
}

def formatmb() {
    def configFiles = findFiles glob: "**/pf-config.json"
    if (configFiles.size() > 0) {
        def pfConfig = readJSON file: configFiles[0].path
        print "MB, checkout pipeline config " + configFiles[0].path
        // checkout to .pf-mb-config to avoid the skip of .pf-config in checkConfigPath()
        dir ('.pf-mb-config') {
            deleteDir()
            checkout([
                $class: 'GitSCM',
                branches: [[name: "*/${pfConfig.BRANCH}"]],
                extensions: [[
                    $class: 'CloneOption',
                    shallow: true,
                    depth:   1,
                    timeout: 30
                ]],
                userRemoteConfigs: [[
                    url: pfConfig.URL,
                    credentialsId: pfConfig.CREDENTIALS
                ]]
            ])
            stash name: "pf-config", includes: "**/settings/**,**/scripts/**"
        }
    }
    else {
        // settings, scripts bundled with source itself
    }

    _format(false)
}

def format() {
    if (! env.PF_FRAMEWORK_URL) {
        env.PF_FRAMEWORK_URL = "https://mirror.rtkbf.com"
        env.PF_FRAMEWORK_PROD_BRANCH = "stable-py"
        env.PF_FRAMEWORK_DEV_BRANCH = "develop-python"
    }
    _format(true)
}

def iterateStages(stages, unstashPF) {
    if (unstashPF == true) {
        utils.unstashPipelineFramework()
    }
    if (stages.size() > 0) {
        for (def stageIdx=0; stageIdx<stages.size(); stageIdx++) {
            if (currentBuild.result == 'ABORTED') {
                print "iterateStages: ABORTED"
                return //this will exit the pipeline
            }

            def stageName = stages[stageIdx]
            print "iterateStages: stage $stageName"
            def actionName = utils.extractActionName(stageName)

            def stageConfig = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"
            def stageDisplayName = stageName
            try {
                if (stageConfig.display_name && stageConfig.display_name != "") {
                    stageDisplayName = stageConfig.display_name
                }
            }
            catch (e) {
            }

            if (actionName == "composition") {
                startComposition(stageName)
            }
            else {
                if (stageConfig.containsKey("stage_lock") && stageConfig["stage_lock"] == true) {
                    lock(stageDisplayName) {
                        stage(stageDisplayName) {
                            execStage(actionName, stageName)
                        }
                    }
                }
                else {
                    stage(stageDisplayName) {
                        execStage(actionName, stageName)
                    }
                }
            }
        }
    }	
}

def escapedBashVariablename(str) {
    def ret = str
    ret = ret.replaceAll("\\-", "dash")
    ret = ret.replaceAll("\\.", "dot")
    ret = ret.replaceAll("/", "slash")
    return ret
}

def generateCustomWS(jobName, stageName) {
    def normalizedPath
    def customWS

    if (isUnix()) {
        normalizedPath = jobName.replaceAll("\\\\", "/")
    }
    else {
        normalizedPath = jobName.replaceAll("/", "\\\\")
    }
    print "generateCustomWS: normalizedPath, ${normalizedPath}"

    stageName = stageName.replaceAll("/", "_")
    // do not modify the workspace naming rules, fixed workspace name is necessary for cn2sd5
    if ((isUnix() == false && stageName.length() > 32) || env.PF_SHORT_WORKSPACE) {
        writeFile file: ".pf-stagename", text: stageName
        def shasum = sha1 file: ".pf-stagename"
        shasum = shasum.substring(0, 8)
        print("generateCustomWS: map ${stageName} to ${shasum}")
        stageName = shasum
    }

    if (env.WORKSPACE.indexOf("${normalizedPath}@") > 0) {
        customWS = env.WORKSPACE.substring(0, env.WORKSPACE.indexOf("${normalizedPath}@") + normalizedPath.length()) + "@${stageName}"
    }
    else if (env.WORKSPACE.indexOf("_job_") > 0) {
        // normalizedPath may not be presented on windows
        customWS = env.WORKSPACE.substring(0, env.WORKSPACE.lastIndexOf("_job_")) + "@${stageName}"
    }
    else {
        customWS = env.WORKSPACE + "@${stageName}"
    }
    customWS = customWS.replaceAll("@", "at")

    return customWS
}

def parallelBuildMulti(stages, nodeNames) {
    def nodes = nodeNames.split(',')

    def parallelInfo = [:]
    parallelInfo.branches = []
    def customWS
    def combinationEnvs = []
    def jobs = [:]
    for (def multiIdx=0; multiIdx<stages.size(); multiIdx++) {
        def nodeName
        if (multiIdx >= nodes.size()) {
            nodeName = nodes[nodes.size() - 1]
        }
        else {
            nodeName = nodes[multiIdx]
        }
        def subStages = stages[multiIdx]
        def stageName = "PF_MULTI${multiIdx}"
        print "parallelBuildMulti: ${stageName} " + subStages + " (${nodeName})"
        combinationEnvs[multiIdx] = []
        combinationEnvs[multiIdx] << "BUILD_BRANCH=" + escapedBashVariablename(stageName)
        combinationEnvs[multiIdx] << "BUILD_BRANCH_RAW=" + stageName
        parallelInfo.branches << escapedBashVariablename(stageName)
        def envvar = combinationEnvs[multiIdx]
        if (nodeName == "" || env.NODE_LABELS.contains(nodeName)) {
            jobs[stageName] = {
                // check WORKSPACE ${JOB_NAME}@n or ${JOB_NAME}_job_n, reference: parallelBuild()
                if (env.WORKSPACE.indexOf("${JOB_NAME}@") > 0) {
                    customWS = env.WORKSPACE.substring(0, env.WORKSPACE.indexOf("${JOB_NAME}@") + JOB_NAME.length()) + "@${stageName}"
                }
                else if (env.WORKSPACE.indexOf("${JOB_NAME}_job_") > 0) {
                    customWS = env.WORKSPACE.substring(0, env.WORKSPACE.indexOf("${JOB_NAME}_job_") + JOB_NAME.length()) + "@${stageName}"
                }
                else {
                    customWS = env.WORKSPACE + "@${stageName}"
                }

                print "Set parallel build WS: ${customWS}"
                ws (customWS) {
                    withEnv(envvar) {
                        stage(stageName) {
                            pascCleanWs()
                            iterateStages(subStages, true)
                        }
                    }
                }
            }
        }
        else {
            jobs[stageName] = {
                // job could not be paralleled if fixed stageName applied, like stage("paralleBuild")
                node(nodeName) {
                    customWS = generateCustomWS(JOB_NAME, stageName)
                    print "Set parallel build WS: ${customWS}"
                    ws (customWS) {
                        withEnv(envvar) {
                            stage(stageName) {
                                pascCleanWs()
                                iterateStages(subStages, true)
                            }
                        }
                    }
                }
            }
        }
    }

    dir ('.pf-global') {
        writeJSON file: 'parallelInfo.json', json: parallelInfo
        stash name: 'pf-global-parallelinfo', includes: 'parallelInfo.json'
        env.PF_GLOBAL_PARALLELINFO = "1"
    }

    stage('Parallel-Multi') {
        parallel jobs
    }
}

def parallelBuild(parallelParameters, parallelExcludes, stages, nodeName, cleanWS) {
    def parallelParams = []
    def parallelValues = [:]
    for (def key in parallelParameters.keySet()) {
        parallelParams << key
        parallelValues[key] = parallelParameters."${key}"
    }
    def totalCombinations = 1
    def combinations = []
    def combinationEnvs = []
    for (def i=0; i<parallelParams.size(); i++) {
        def parallelParam = parallelParams[i]
        totalCombinations = totalCombinations * parallelValues[parallelParam].size()
    }
    // ex: OS = {linux-5.11, macos-mojave}
    // ex: CPU = {arm, mips}
    // totalCombinations = 2x2 = 4
    // combinations[0] = {linux-5.11, arm}
    // combinations[1] = {linux-5.11, mips}
    // ...
    // combinationEnvs[0] = {OS=linux-5.11, CPU=arm}
    // combinationEnvs[1] = {OS=linux-5.11, CPU=mips}
    // ...
    for (def i=0; i<totalCombinations; i++) {
        combinations[i] = []
        combinationEnvs[i] = []
    }
    def divider = totalCombinations
    for (def j=0; j<parallelParams.size(); j++) {
        def parallelParam = parallelParams[j]
        def dimensionSize = parallelValues[parallelParam].size()
        divider = divider.intdiv(dimensionSize)
        for (def i=0; i<totalCombinations; i++) {
            def index = i.intdiv(divider)
            index = index % dimensionSize

            combinations[i] << parallelValues[parallelParam][index]
            combinationEnvs[i] << parallelParam + "=" + parallelValues[parallelParam][index]
        }
    }
    def parallelCounts = 0
    def jobs = [:]
    def parallelInfo = [:]
    parallelInfo.branches = []
    for (def i=0; i<totalCombinations; i++) {
        def stageName = combinations[i].join("_")
        def stageNameForExcludesComparison = combinations[i].join(",,")
        // empty parallel_parameter
        if (stageName == "") {
            stageName = "parallel"
        }
        // Note: there are two excludes configurations available
        // 1. llinux-5.11_arm
        // 2. llinux-5.11,,arm (recommended)
        if (parallelExcludes.contains(stageName) || parallelExcludes.contains(stageNameForExcludesComparison)) {
            print "skip stage ${stageName}"
            continue
        }
        def regexMatch = false
        for (def j=0; j<parallelExcludes.size(); j++) {
            if (stageNameForExcludesComparison.matches(parallelExcludes[j])) {
                print "match ${parallelExcludes[j]}, skip stage ${stageName}"
                regexMatch = true
                break
            }
        }
        if (regexMatch == true) {
            continue
        }
        combinationEnvs[i] << "BUILD_BRANCH=" + escapedBashVariablename(stageName)
        combinationEnvs[i] << "BUILD_BRANCH_RAW=" + stageName
        parallelInfo.branches << escapedBashVariablename(stageName)
        def customWS = ""
        def envvar = combinationEnvs[i]
        print "parallelBuild: parallelCounts ${parallelCounts}"

        jobs[stageName] = {
            node(nodeName) {
                customWS = generateCustomWS(JOB_NAME, stageName)
                print "parallelBuild: set parallel build WS, ${customWS}"

                ws (customWS) {
                    withEnv(envvar) {
                        stage(stageName) {
                            if (cleanWS) {
                                pascCleanWs()
                            }
                            iterateStages(stages, true)
                        }
                    }
                }
            }
        }
        parallelCounts = parallelCounts + 1

    }
    dir ('.pf-global') {
        writeJSON file: 'parallelInfo.json', json: parallelInfo
        stash name: 'pf-global-parallelinfo', includes: 'parallelInfo.json'
        env.PF_GLOBAL_PARALLELINFO = "1"
    }

    stage('Parallel') {
        parallel jobs
    }
}

def startCompositionSplit(stageName, idx) {
    env.PF_BASEWORKSPACE = WORKSPACE
    utils.translateConfig(stageName)
    def stageConfig = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"
    def stages = []
    stages << stageConfig.stages[idx]
    print "startCompositionSplit: " + idx
    print "startCompositionSplit: stageConfig, " + stageConfig
    if (idx == 0) {
        parallelBuild(stageConfig.parallel_parameters, stageConfig.parallel_excludes, stages, stageConfig.node, true)
    }
    else {
        parallelBuild(stageConfig.parallel_parameters, stageConfig.parallel_excludes, stages, stageConfig.node, false)
    }
}

def startComposition(stageName) {
    env.PF_BASEWORKSPACE = WORKSPACE
    utils.translateConfig(stageName)
    def stageConfig = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"
    print "startComposition: NODE_NAME, " + env.NODE_NAME
    print "startComposition: stageConfig, " + stageConfig
    if (stageConfig.run_type == "SEQUENTIAL") {
        def seqNode = stageConfig["node"]
        if (stageConfig["node"] == "") {
            seqNode = env.NODE_NAME
            //seqNode = "PF_KEEP_AGENT"
        }
        print "startComposition: running on ${seqNode}"
        parallelBuild(stageConfig.parallel_parameters, stageConfig.parallel_excludes, stageConfig.stages, seqNode, true)
    }
    else if (stageConfig.run_type == "MULTI") {
        def seqNode = stageConfig["node"]
        if (stageConfig["node"] == "") {
            seqNode = env.NODE_NAME
        }
        print "startComposition: running on ${seqNode}"
        parallelBuildMulti(stageConfig.stages, seqNode)
    }
    else {
        def jobs = [:]
        for (def concurrentStage in stageConfig.stages) {
            def stageArray = []
            stageArray << concurrentStage
            jobs[concurrentStage] = {
                iterateStages(stageArray, false)
            }
        }
        if (stageConfig.node == "" || env.NODE_LABELS.contains(stageConfig.node)) {
            stage('Concurrent') {
                parallel jobs
            }
        }
        else {
            node(stageConfig.node) {
                stage('Concurrent') {
                    parallel jobs
                }
            }
        }
    }
}

def start() {
    def nodeName = ""
    try {
        if (env.PF_GLOBAL_NODES != "") {
            def nodes = env.PF_GLOBAL_NODES.split(",")
            nodeName = nodes[0]
        }
    }
    catch (e) {
        // @Field List nodes = [""] not found
    }

    def globalStages = env.PF_GLOBAL_STAGES.split(",")
    //if (nodeName == "" || env.NODE_NAME == nodeName) {
    if (nodeName == "" || env.NODE_LABELS.contains(nodeName)) {
        // avoid unnecessary change node
        pascCleanWs()
        env.PF_MAIN_AGENT = env.NODE_NAME
        iterateStages(globalStages, true)
    }
    else {
        node(nodeName) {
            pascCleanWs()
            env.PF_MAIN_AGENT = env.NODE_NAME
            iterateStages(globalStages, true)
        }
    }
}

return this
