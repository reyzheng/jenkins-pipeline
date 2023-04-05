import groovy.transform.Field

@Field settingPath = "settings"
@Field modules = [:]
@Field utils

// modules.global_vars.stages: all stages found in global_config, for stage iteration, corresponding configs finding

// env.PF_PRESERVE_SOURCE
// env.PF_GERRIT_CREDENTIALS
// env.PF_SOURCE_REVISION
// env.PF_MAIN_SOURCE_NAME
// env.PF_MAIN_SOURCE_PLAINNAME
// env.PF_SOURCE_DST_{i}

def loadGlobalSettings() {
    def defaultConfigs = [
        clean_ws: true,
        stages: [],
        parallel_stages: [],
        standalone_stages: [],
        parallel_parameters: [:],
        nodes: [],
        preserve_source: false,
        gerrit_credentials: "",
        coverity_credentials: "",
        blackduck_credentials: "",
        sms_account: "",
        sms_credentials: "",
        scriptableParams: ["preserve_source"]
    ]
    def globalVarsRaw = utils.commonInit("global", defaultConfigs)
    utils.stashScriptedParamScripts("global", globalVarsRaw.settings)
    modules.global_vars = [:]
    utils.unstashScriptedParamScripts("global", globalVarsRaw.settings, modules.global_vars)

    env.PF_PRESERVE_SOURCE = modules.global_vars.preserve_source
    env.PF_GERRIT_CREDENTIALS = modules.global_vars.gerrit_credentials

    modules.global_vars.parallelBuild = false
    // re-construct stages from parallel_stages, standalone_stages
    try {
        if (modules.global_vars.parallel_stages.size() > 0) {
            modules.global_vars.stages = []
            modules.global_vars.stages.addAll(modules.global_vars.parallel_stages)
            try {
                modules.global_vars.stages.addAll(modules.global_vars.standalone_stages)
            }
            catch (e) {
                // standalone_stages not defined
            }
            if (modules.global_vars.parallel_parameters) {
                modules.global_vars.parallelBuild = true
                modules.global_vars.parallel_parameters = utils.extractParallelParameters(modules.global_vars.parallel_parameters)
            }
        }
    }
    catch (e) {
        // no parallel_stages, standalone_stages defined
    }

    // load logParserRule
    dir ('scripts') {
        modules.hasLogParserRule = fileExists "logParserRule"
        if (modules.hasLogParserRule == true) {
            stash name: "stash-global-logparser", includes: "logParserRule"
        }
    }
}

def preparePostStage() {
    if (modules.hasLogParserRule == true) {
        dir ("scripts") {
            unstash name: "stash-global-logparser"
        }
    }
}

def emailNotification() {
    // leave empty for backward compatibility
}

def postStage(postStatus) {
    if (modules.configs["post"] == null) {
    }
    else {
        def nodeName = ""
        if (modules.hasUserDefinedNodes == true) {
            nodeName = modules.global_vars.nodes[0]
        }

        def postConfig = modules.configs["post"].settings
        // post scripts
        for (def i=0; i<postConfig.post_scripts_condition.size(); i++) {
            if (postConfig.post_scripts_condition[i] == postStatus) {
                def action = utils.loadAction("post")
                if (nodeName == "" || env.NODE_NAME == nodeName) {
                    // avoid unnecessary change node
                    action.execute(modules, postConfig, i)
                }
                else {
                    node(nodeName) {
                        action.execute(modules, postConfig, i)
                    }
                }
            }
        }
        // mail
        if (postConfig.mail_conditions.contains(postStatus)) {
            sendEmail()
        }
    }
}

def sendEmail() {
    def postConfig = modules.configs["post"].settings
    //def postPreloads = modules.configs["post"].preloads
    if (postConfig.mail_enabled == true) {
        def emailbody = """${currentBuild.result}: Job '${env.JOB_NAME} [${env.BUILD_NUMBER}]':
                        Check console output at ${env.BUILD_URL}"""
        if (postConfig.mail_body != "") {
            def externalMailMethod
            dir ('.pf-post') {
                unstash name: "pf-post-mail-body"
                externalMailMethod = load(postConfig.mail_body)
            }
            emailbody = externalMailMethod.func()
        }

        def mailSubject = postConfig.mail_subject
        if (postConfig.mail_subject == "") {
            mailSubject = "${currentBuild.result}: Job '${env.JOB_NAME} [Build ${env.BUILD_NUMBER}]'"
        }
        emailext (
            subject: mailSubject,
			body: emailbody,
            to: "${postConfig.mail_recipient}"
            //recipientProviders: [[$class: 'DevelopersRecipientProvider']]
        )
    }
}

def loadCoreActions() {
    // lookup files under groovyPath
    def actionFiles

    dir ('groovys') {
        actionFiles = findFiles(glob: "*.groovy")
        print "Found actions " + actionFiles
        for (actionFile in actionFiles) {
            def actionFileName = actionFile.toString()
            def actionName = actionFileName.split(/\\|\/|\./)
            // groovys/source.groovy -> groovy source groovy
            actionName = actionName[0]
            modules.coreActions << actionName
        }
    }
    // TODO: ugly code
    modules.coreActions += ["config", "prebuild", "build", "postbuild", "test"]
}

def loadUserConfig(configFileName) {
    // settings/build-dummy_config.groovy -> settings "build-dummy_config" groovy
    def configName = configFileName.split(/\\|\/|\./)
    configName = configName[1]
        
    // urf_license_checker_config-dummy_config -> "urf_license_checker_config-dummy" config
    def breakPos = configName.lastIndexOf("_")
    def stageName = configName.substring(0, breakPos)
    def actionName = utils.extractActionName(stageName)
    def realActionName = utils.extractRealActionName(stageName)

    if (modules.actionStashed.contains(actionName) == false) {
        def stashStatus = false

        dir ('groovys') {
            // core actions
            def frameworkAction = fileExists "${realActionName}.groovy"
            if (frameworkAction == true) {
                stash name: "stash-actions-${actionName}", includes: "${realActionName}.groovy"
                if (actionName == "coverity") {
                    // Ugly: for Rock's dynamic 'build only' or 'build + coverity'
                    stash name: "stash-actions-script", includes: "script.groovy"
                }
                stashStatus = true
            }
        }
        if (stashStatus == false) {
            // user-defined actions
            dir ('scripts') {
                def customAction = fileExists "${realActionName}.groovy"
                if (customAction == true) {
                    stash name: "stash-actions-${actionName}", includes: "${realActionName}.groovy"
                    stashStatus = true
                }
            }
        }
        modules.actionStashed << actionName
    }

    // user defined actions could also load configs
    print "loadUserConfigs: ${stageName}(${actionName})"
    def action = utils.loadAction(actionName)
    try {
        modules.configs[stageName] = action.init(stageName)
        print "loadUserConfigs: ${stageName}(${actionName}) configured"
    }
    catch (e) {
        // easyActions has no configurations
        unstable("${stageName} (${actionName}) init. failed " + e)
    }

    if (actionName == "composition") {
        def stageConfig
        dir ('.pf-global') {
            unstash name: "pf-${stageName}-config"
            stageConfig = readJSON file: 'temporal.json'
        }
        for (def subStage in stageConfig.stages) {
            loadUserConfig(settingPath + "/${subStage}_config.groovy")
        }
    }
}

def loadUserConfigs() {
    // Load user config
    def requiredConfigs = []
    for (def i=0; i<modules.global_vars.stages.size(); i++) {
        def stage = modules.global_vars.stages[i]
        requiredConfigs << settingPath + "/${stage}_config.groovy"
    }
    
    // Load ugly coverity_config
    dir (settingPath) {
        def coverityGroovyExists = fileExists "coverity_config.groovy"
        def coverityJsonExists = fileExists "coverity_config.json"
        if (coverityGroovyExists || coverityJsonExists) {
            requiredConfigs << settingPath + "/coverity_config.groovy"
        }
    }

    // Load post_config
    dir ('groovys') {
        stash name: "stash-actions-post", includes: "post.groovy"
    }
    def postAction = utils.loadAction("post")
    modules.configs["post"] = postAction.init()
    // Load required scripts in post_config
    for (def i=0; i<modules.configs["post"].settings.post_scripts_type.size(); i++) {
        if (modules.configs["post"].settings.post_scripts_type[i] == "action") {
            def stage = modules.configs["post"].settings.post_scripts[i]
            requiredConfigs << settingPath + "/${stage}_config.groovy"
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
    def excludes = []
    def preserveSource = false
    def cleanWS = true

    cleanWS = modules.global_vars.clean_ws
    preserveSource = modules.global_vars.preserve_source
    if (preserveSource == true || preserveSource == "true") {
        modules.global_vars.preserve_source = true
    }
    else {
        modules.global_vars.preserve_source = false
    }

    if (cleanWS == false) {
        return
    }
    if (modules.global_vars.preserve_source == true) {
        if (env.PF_MAIN_SOURCE_NAME) {
            def sourceNames = env.PF_MAIN_SOURCE_NAME.split(',')
            def sourcePlainNames = env.PF_MAIN_SOURCE_PLAINNAME.split(',')
            for (def j=0; j<sourceNames.size(); j++) {
                def sourceName = sourceNames[j]
                def sourcePlainName = sourcePlainNames[j]
                for (def i=0; i<modules.configs[sourceName].settings.scm_counts; i++) {
                    def exclude = [:]
                    def scmDst = modules.configs[sourceName].settings.scm_dsts[i]

                    // TODO: handle parameterized scm_dsts, like ${TEXT_DST}, ugly
                    scmDst = utils.extractScriptedParameter(scmDst, "stash-${sourcePlainName}-params-scm_dsts-${i}")

                    exclude.pattern = "${scmDst}/**"
                    exclude.type = "EXCLUDE"
                    excludes << exclude
                }
            }
        }
    }
    print "Clean WS, excludes: " + excludes
    cleanWs deleteDirs: true, patterns: excludes
}

def init() {
    stash name: "stash-script-utils", includes: "utils.groovy"
    utils = load "utils.groovy"
    // store exec. result at each stage
    env.PIPELINE_AS_CODE_STAGE_BUILD_RESULTS = ""
    env.PIPELINE_AS_CODE_STAGE_TEST_RESULTS = ""

    // load global_config
    loadGlobalSettings()

    // stage pre-initialization is necessary:
    // pipeline from scm was done at master node, 
    // groovy loading would be failed after jobs dispatched to agents
    modules.actions = [:]
    modules.coreActions = []
    modules.actionStashed = []
    modules.configs = [:]

    loadCoreActions()
    loadUserConfigs()

    // clean workspace
    // stash utils before clean workspace
    // re-write logParserRule after initialization
    dir ('pipeline_scripts') {
        stash name: 'stash-script-bdsh', includes: 'bdsh.sh'
    }
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
                dir('settings') {
                    stageConfig = readJSON file: "${stageName}_config.json"
                    realStageName = stageConfig.display_name
                }
            }
            catch(e) {
            }

            if (actionName == "composition" && stageConfig.run_type == "SEQUENTIAL_SPLIT") {
                for (def i=0; i<stageConfig.stages.size(); i++) {
                    content += "stage('$realStageName-$i') {\n"
                    content += "    steps {\n"
                    content += "        script {\n"
                    content += "            if (!utils) {\n"
                    content += "                utils = load 'utils.groovy'\n";
                    content += "                pf = load('rtk_stages.groovy')\n";
                    content += "                pf.init()\n";
                    content += "            }\n"
                    content += "            pf.startCompositionSplit(pf.modules.configs['$stageName'].settings, pf.modules.configs['$stageName'].preloads, $i)\n"
                    content += "        }\n"
                    content += "    }\n"
                    content += "}\n"
                }
            }
            else {
                content += "stage('$realStageName') {\n"
                content += "    steps {\n"
                content += "        script {\n"
                content += "            if (!utils) {\n"
                content += "                utils = load 'utils.groovy'\n";
                content += "                pf = load('rtk_stages.groovy')\n";
                content += "                pf.init()\n";
                content += "            }\n"
                if (actionName == "composition") {
                    content += "        pf.startComposition('$stageName')\n"
                }
                else {
                    content += "        pf.execStage('$actionName', '$stageName')\n"
                }
                content += "        }\n"
                content += "    }\n"
                content += "}\n"
            }
        }
    }
	return content
}

def execStage(actionName, stageName) {
	//def staticActions = ['coverity']
    def staticActions = []
    def skinnyActions = ['jira', 'source']
    if (modules.coreActions.contains(actionName)) {
        def action = utils.loadAction(actionName)
        if (staticActions.contains(actionName)) {
            action.func(actionName, stageName)
        }
        else if (skinnyActions.contains(actionName)) {
			def stageConfig = modules.configs[stageName].settings
			def stagePreloads = modules.configs[stageName].preloads
            action.func(null, stageConfig, stagePreloads)
        }
        else {
			def stageConfig = modules.configs[stageName].settings
			def stagePreloads = modules.configs[stageName].preloads
            action.func(modules, stageConfig, stagePreloads)
        }
    }
    else {
        def action = utils.loadAction(actionName)
        try {
            if (modules.configs[stageName]) {
                def stageConfig = modules.configs[stageName].settings
                def stagePreloads = modules.configs[stageName].preloads
                action.func(modules, stageConfig, stagePreloads)
            }
            else {
                action.func()
            }
        }
        catch (e) {
            error(message: "${stageName} is unstable " + e)
        }
    }        
}

def format() {
    def globalConfig
    dir ('settings') {
        globalConfig = readJSON file: 'global_config.json'
    }

    if (! utils) {
        utils = load 'utils.groovy'
    }
    def stages = globalConfig.stages
    def nodeLabel = ""
    if (globalConfig.nodes.size() > 0) {
        nodeLabel = globalConfig.nodes[0]
    }
    def nodeSection = "def nodeLabel='$nodeLabel'\n"
    def topHalf
    def bottomHalf
    dir ('pipeline_scripts') {
        topHalf = readFile file: 'Jenkinsfile.tophalf'
        bottomHalf = readFile file: 'Jenkinsfile.bottomhalf'
    }
    def sourceOnly = false
    if (globalConfig.dagger) {
        sourceOnly = true
    }
    def content = iterateToFile(stages, sourceOnly)

    print "Jenkinsfile generated"
    print nodeSection + topHalf + content + bottomHalf
    writeFile file: 'Jenkinsfile.restartable', text: nodeSection + topHalf + content + bottomHalf
}

def iterateStages(stages) {
    if (stages.size() > 0) {
        for (def stageIdx=0; stageIdx<stages.size(); stageIdx++) {
            def stageName = stages[stageIdx]
            print "iterateStages: stage $stageName"
            def actionName = utils.extractActionName(stageName)
            def stageConfig
            def stagePreloads
            try {
                stageConfig = modules.configs[stageName].settings
                stagePreloads = modules.configs[stageName].preloads
            }
            catch (e) {
                // maybe user-defined simple action
                // simple action: action without configuration
                // general action: action with configuration
                print "$stageName config not found"
            }
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
            else if (actionName == "coverity" || 
                        (actionName == "build" && modules.configs["coverity"] != null && modules.configs["coverity"].settings.coverity_scan_enabled == true)) {
                stage(stageDisplayName) {
                    def action = utils.loadAction("coverity")
                    action.func(modules, stageConfig, stagePreloads)
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

def standaloneStages() {
    try {
        iterateStages(modules.global_vars.standalone_stages)
    }
    catch (e) {
        print "Standalone stages not defined in parallel build " + e
    }
}

def escapedBashVariablename(str) {
    def ret = str
    ret = ret.replaceAll("\\-", "dash")
    ret = ret.replaceAll("\\.", "dot")
    ret = ret.replaceAll("/", "slash")
    return ret
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
        jobs[stageName] = {
            // job could not be paralleled if fixed stageName applied, like stage("paralleBuild")
            node(nodeName) {
                // NOTE: do not let customWS assign out of node{} section, therefore we can get CORRECT env.WORKSPACE inside node{}
                // check WORKSPACE ${JOB_NAME}@n or ${JOB_NAME}_job_n
                if (env.WORKSPACE.indexOf("${JOB_NAME}@") > 0) {
                    customWS = env.WORKSPACE.substring(0, env.WORKSPACE.indexOf("${JOB_NAME}@") + JOB_NAME.length()) + "@${stageName}"
                }
                else if (env.WORKSPACE.indexOf("${JOB_NAME}_job_") > 0) {
                    customWS = env.WORKSPACE.substring(0, env.WORKSPACE.indexOf("${JOB_NAME}_job_") + JOB_NAME.length()) + "@${stageName}"
                }
                else {
                    customWS = env.WORKSPACE + "@${stageName}"
                }
                customWS = customWS.replaceAll("@", "at")
                print "Set parallel build WS: ${customWS}"

                ws (customWS) {
                    withEnv(envvar) {
                        stage(stageName) {
                            if (cleanWS) {
                                pascCleanWs()
                            }
                            iterateStages(stages)
                        }
                    }
                }
            }
        }
    }

    dir ('.pf-global') {
        writeJSON file: 'parallelInfo.json', json: parallelInfo
        stash name: 'pf-global-parallelinfo', includes: 'parallelInfo.json'
    }

    stage('Parallel') {
        parallel jobs
    }
}

def startCompositionSplit(stageConfig, stagePreloads, idx) {
    def stages = []
    stages << stageConfig.stages[idx]
    if (idx == 0) {
        parallelBuild(stageConfig.parallel_parameters, stageConfig.parallel_excludes, stages, stageConfig.node, true)
    }
    else {
        parallelBuild(stageConfig.parallel_parameters, stageConfig.parallel_excludes, stages, stageConfig.node, false)
    }
}

def startComposition(stageName) {
    def stageConfig
    dir ('.pf-global') {
        unstash name: "pf-${stageName}-config"
        stageConfig = readJSON file: 'temporal.json'
    }
    if (stageConfig.run_type == "SEQUENTIAL") {
        parallelBuild(stageConfig.parallel_parameters, stageConfig.parallel_excludes, stageConfig.stages, stageConfig.node, true)
    }
    else {
        def jobs = [:]
        for (def concurrentStage in stageConfig.stages) {
            def stageArray = []
            stageArray << concurrentStage
            jobs[concurrentStage] = {
                iterateStages(stageArray)
            }
        }
        if (stageConfig.node == "" || env.NODE_NAME == stageConfig.node) {
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
    modules.hasUserDefinedNodes = false
    try {
        if (modules.global_vars.nodes.size() > 0) {
            modules.hasUserDefinedNodes = true
            nodeName = modules.global_vars.nodes[0]
        }
    }
    catch (e) {
        // @Field List nodes = [""] not found
    }

    if (modules.global_vars.parallelBuild == true) {
        def emptyList = []
        parallelBuild(modules.global_vars.parallel_parameters, emptyList, modules.global_vars.parallel_stages, nodeName, true)
    }
    else {
        if (nodeName == "" || env.NODE_NAME == nodeName) {
            // avoid unnecessary change node
            pascCleanWs()
            iterateStages(modules.global_vars.stages)
        }
        else {
            node(nodeName) {
                pascCleanWs()
                iterateStages(modules.global_vars.stages)
            }
        }
    }

    if (modules.global_vars.parallelBuild == true) {
        if (modules.hasUserDefinedNodes == true && modules.global_vars.nodes.size() > 1) {
            // user specified standaloneStages node
            nodeName = modules.global_vars.nodes[1]
        }
        else {
            nodeName = ""
        }
        stage("OutsideParallel") {
            if (nodeName == "" || env.NODE_NAME == nodeName) {
                pascCleanWs()
                standaloneStages()
            }
            else {
                node(nodeName) {
                    pascCleanWs()
                    standaloneStages()
                }
            }
        }
    }
}

return this
