import groovy.transform.Field

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
    def utils = load "utils.groovy"
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
    def utils = load "utils.groovy"
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
        action.execute(null, postStatus)
    }
    else {
        node(env.PF_MAIN_AGENT) {
            action = utils.loadCoreAction(env.PF_ROOT, "post")
            action.execute(null, postStatus)
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
    def utils = load "utils.groovy"
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
    def utils = load "utils.groovy"
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

def init() {
    def underUnix = isUnix()
    def utils = load "utils.groovy"
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
    stash name: 'stash-pf-framework', includes: "utils.groovy,groovys/**,pipeline_scripts/**,templates/**,rtk_coverity/**,vendor/**"
    dir (env.PF_PATH) {
        stash name: 'stash-pfxxx-config', includes: "Jenkinsfile*,settings/**,scripts/**"
    }
    // note: for Jenkinsfile.restartable
    // iterateStages() would not be called in Jenkinsfile.restartable
    utils.unstashPipelineFramework()
    utils.pascCleanWs()
}

def _format(withNodeLabel) {
    checkConfigPath()
    def utils = load 'utils.groovy'
    def pythonExec = utils.getPython()
    def formatScript = "${pythonExec} pipeline_scripts/utils.py -f ${env.PF_PATH}/settings/global_config.json -c FORMAT_JENKINSFILE -n ${withNodeLabel}"
    if (isUnix()) {
        sh formatScript
    }
    else {
        bat formatScript
    }
    dir ('.pf-global') {
        stash name: 'pf-global-parallelinfo', includes: 'parallelInfo.json'
        env.PF_GLOBAL_PARALLELINFO = "1"
    }
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

return this