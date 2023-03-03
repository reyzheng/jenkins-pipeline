import groovy.transform.Field

@Field groovyPath = "groovys"
@Field scriptPath = "scripts"
@Field settingPath = "settings"
@Field modules = [:]
@Field utils

// modules.global_vars.stages: all stages found in global_config, for stage iteration, corresponding configs finding
// modules.global_vars.stagesExtended: all stages found in global_config(post_config), composition*_config, for user-defined action finding

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
        //post_scripts_condition: [],
        //post_scripts_type: [],
        //post_scripts: [],
        //mail_enabled: false,
        //mail_conditions: ["always"],
        //mail_subject: "",
        //mail_body: "",
        //mail_recipient: "",
        scriptableParams: ["preserve_source"]
    ]
    def globalVarsRaw = utils.commonInit("global", defaultConfigs)
    utils.stashScriptedParamScripts("global", globalVarsRaw.settings)
    modules.global_vars = [:]
    utils.unstashScriptedParamScripts("global", globalVarsRaw.settings, modules.global_vars)

    modules.global_vars.parallelBuild = false
    modules.global_vars.stagesExtended = []
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
    dir (scriptPath) {
        modules.hasLogParserRule = fileExists "logParserRule"
        if (modules.hasLogParserRule == true) {
            stash name: "stash-global-logparser", includes: "logParserRule"
        }
    }

    /*
    // Default coverity checkers, report config yaml
    modules.coverityCheckersCustom = ""
    def hasCustomChecker = fileExists "scripts/checkers_custom"
    if (hasCustomChecker == true) {
        modules.coverityCheckersCustom = readFile(file: "scripts/checkers_custom")
    }
    stash name: "stash-global-coverity", includes: "rtk_coverity/checkers_default,rtk_coverity/checkers_default-light,rtk_coverity/checkers_medium,rtk_coverity/checkers_medium-light,rtk_coverity/checkers_heavy"
    */
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
        def postPreloads = modules.configs["post"].preloads
        // post scripts
        for (def i=0; i<postConfig.post_scripts_condition.size(); i++) {
            if (postConfig.post_scripts_condition[i] == postStatus) {
                def action = utils.loadAction("post")
                if (nodeName == "" || env.NODE_NAME == nodeName) {
                    // avoid unnecessary change node
                    action.execute(modules, postConfig, postPreloads, i)
                }
                else {
                    node(nodeName) {
                        action.execute(modules, postConfig, postPreloads, i)
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
    def postPreloads = modules.configs["post"].preloads
    if (postConfig.mail_enabled == true) {
        emailbody = """${currentBuild.result}: Job '${env.JOB_NAME} [${env.BUILD_NUMBER}]':
                        Check console output at ${env.BUILD_URL}"""
        if (postConfig.mail_body != "") {
            def dstFileName = "script-mailbody-" + currentBuild.startTimeInMillis
            def dstFile = env.WORKSPACE + modules.separator + dstFileName
            writeFile(file: dstFile , text: postPreloads.mail_body)
            def externalMailMethod = load(dstFile)
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
    actionFiles = findFiles(glob: "${groovyPath}${modules.separator}*.groovy")
    
    print "Found actions " + actionFiles
    for (actionFile in actionFiles) {
        def actionFileName = actionFile.toString()
        def actionName = actionFileName.split(/\\|\/|\./)
        // groovys/source.groovy -> groovy source groovy
        actionName = actionName[1]
        modules.coreActions << actionName
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

        dir (scriptPath) {
            def customAction = fileExists "${realActionName}.groovy"
            if (customAction == true) {
                stash name: "stash-actions-${actionName}", includes: "${realActionName}.groovy"
                stashStatus = true
            }
        }
        if (stashStatus == false) {
            dir (groovyPath) {
                def frameworkAction = fileExists "${realActionName}.groovy"
                if (frameworkAction == true) {
                    stash name: "stash-actions-${actionName}", includes: "${realActionName}.groovy"
                    stashStatus = true
                }
            }
        }
        modules.actionStashed << actionName
    }

    /*
    if (actionName in modules.coreActions == false) {
        // skip user defined actions
        return
    }
    */
    // user defined actions could also load configs
    try {
        def configExists = false
        def jsonConfigExists = false
        dir (settingPath) {
            configExists = fileExists "${stageName}_config.groovy"
            jsonConfigExists = fileExists "${stageName}_config.json"
        }
        if (configExists == true || jsonConfigExists == true) {
            print "loadUserConfigs: ${stageName}(${actionName}) start"
            def action = utils.loadAction(actionName)
            modules.configs[stageName] = action.init(stageName)
            print "loadUserConfigs: ${stageName}(${actionName}) configured"
            if (actionName == "source") {
                modules.mainSourceStage = stageName
                modules.mainSourcePlainStageName = modules.configs[stageName].preloads.plainStageName
            }
        }
        else {
            modules.easyActions << actionName
        }
    }
    catch (e) {
        // stage not configured
        unstable("${stageName} (${actionName}) init. failed " + e)
    }

    if (actionName == "composition") {
        for (def subStage in modules.configs[stageName].settings.stages) {
            modules.global_vars.stagesExtended << subStage
            loadUserConfig(settingPath + "/${subStage}_config.groovy")
        }
    }
}

def loadUserConfigs() {
    // Load user config
    def requiredConfigs = []
    for (def i=0; i<modules.global_vars.stages.size(); i++) {
        def stage = modules.global_vars.stages[i]
        modules.global_vars.stagesExtended << stage
        requiredConfigs << settingPath + "/${stage}_config.groovy"
    }
    
    // Load ugly coverity_config
    dir (settingPath) {
        def coverityConfigExists = fileExists "coverity_config.groovy"
        if (coverityConfigExists) {
            def coverityConfig = load "coverity_config.groovy"
            if (coverityConfig.coverity_scan_enabled == true) {
                requiredConfigs << settingPath + "/coverity_config.groovy"
            }
        }
    }

    // Load post_config
    dir (groovyPath) {
        stash name: "stash-actions-post", includes: "post.groovy"
    }
    def postAction = utils.loadAction("post")
    modules.configs["post"] = postAction.init()
    // Load required scripts in post_config
    for (def i=0; i<modules.configs["post"].settings.post_scripts_type.size(); i++) {
        if (modules.configs["post"].settings.post_scripts_type[i] == "action") {
            def stage = modules.configs["post"].settings.post_scripts[i]
            modules.global_vars.stagesExtended << stage
            requiredConfigs << settingPath + "/${stage}_config.groovy"
        }
    }

    // Load user configs
    print "Total configs to be loaded " + requiredConfigs
    for (requiredConfig in requiredConfigs) {
        loadUserConfig(requiredConfig)
    }

    // here we got source configuration, initialize modules.srcRevisions
    try {
        for (def i=0; i<modules.configs[modules.mainSourceStage].settings.scm_counts; i++) {
            modules.srcRevisions."${i}" = [:]
        }
    }
    catch (e) { // invalid source configuration
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

    try {
        cleanWS = modules.global_vars.clean_ws
    }
    catch (e) {
    }
    try {
        preserveSource = modules.global_vars.preserve_source
    }
    catch (e) {
    }

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
        try {
            for (def i=0; i<modules.configs[modules.mainSourceStage].settings.scm_counts; i++) {
                def exclude = [:]
                def scmDst = modules.configs[modules.mainSourceStage].settings.scm_dsts[i]

                // TODO: handle parameterized scm_dsts, like ${TEXT_DST}, ugly
                scmDst = utils.extractScriptedParameter(scmDst, "stash-${modules.mainSourcePlainStageName}-params-scm_dsts-${i}")

                exclude.pattern = "${scmDst}/**"
                exclude.type = "EXCLUDE"
                excludes << exclude
            }
        }
        catch(e) { // invalid source configuration
        }
    }
    print "Clean WS, excludes: " + excludes
    cleanWs deleteDirs: true, patterns: excludes
}

def init() {
    utils = load "utils.groovy"
    if (isUnix() == true) {
        modules.separator = "/"
    }
    else {
        modules.separator = "\\"
    }
    // store exec. result at each stage
    env.PIPELINE_AS_CODE_STAGE_BUILD_RESULTS = ""
    env.PIPELINE_AS_CODE_STAGE_TEST_RESULTS = ""

    // load global_config
    loadGlobalSettings()

    modules.global_vars.buildBranches = []
    modules.srcRevisions = [:]
    modules.srcRevisions.manifest = null
    // stage pre-initialization is necessary:
    // pipeline from scm was done at master node, 
    // groovy loading would be failed after jobs dispatched to agents
    modules.actions = [:]
    modules.coreActions = []
    modules.easyActions = []
    modules.actionStashed = []
    modules.configs = [:]

    loadCoreActions()
    loadUserConfigs()

    // search for hsm actions
    for (def i=0; i<modules.global_vars.stagesExtended.size(); i++) {
        def stageName = modules.global_vars.stagesExtended[i]
        def actionName = utils.extractActionName(stageName)
        /*
        if ((actionName in modules.coreActions) == false) {
            // custom actions, load groovy file
            modules.configs[stageName] = readFile(file: "scripts/${actionName}.groovy")
        }
        */
	}

    // clean workspace
    // stash utils before clean workspace
    // re-write logParserRule after initialization
    stash name: "stash-script-utils", includes: "utils.groovy"
    pascCleanWs()
}

def iterateToFile(stages, sourceOnly) {
    if (! utils) {
        utils = load 'utils.groovy'
    }
    def content = ""
    if (stages.size() > 0) {
        for (def stageIdx=0; stageIdx<stages.size(); stageIdx++) {
            def stageName = stages[stageIdx]
            def actionName = utils.extractActionName(stageName)
	    if (sourceOnly && actionName != "source") {
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

            content += "stage('$realStageName') {\n"
            content += "    steps {\n"
            content += "        script {\n"
            content += "            if (!utils) {\n"
            content += "                utils = load 'utils.groovy'\n";
            content += "                pf = load('rtk_stages.groovy')\n";
            content += "                pf.init()\n";
            content += "            }\n"
            if (actionName == "composition") {
                content += "            pf.startComposition(pf.modules.configs['$stageName'].settings, pf.modules.configs['$stageName'].preloads)\n"
            }
            else {
                content += "            pf.execStage('$actionName', '$stageName')\n"
            }
            content += "        }\n"
            content += "    }\n"
            content += "}\n"

/*
            if (actionName == "composition") {
				def compositionCfg
				dir('settings') {
					compositionCfg = readJSON file: "${stageName}_config.json"
				}
                compositionCfg.parallel_parameters = utils.extractParallelParameters(compositionCfg.parallel_parameters)
                compositionCfg.parallel_excludes = utils.extractParameters(compositionCfg.parallel_excludes)

				content += "stage('$stageName') {\n"
                content += "    steps {\n"
                content += "        script {\n"
                content += "            if (!utils) {\n"
                content += "                utils = load 'utils.groovy'\n";
                content += "                pf = load('rtk_stages.groovy')\n";
                content += "                pf.init()\n";
                content += "            }\n"
				content += "            pf.startComposition(pf.modules.configs['$stageName'].settings, pf.modules.configs['$stageName'].preloads)\n"
                content += "        }\n"
                content += "    }\n"
				content += "}\n"
            }
			else {
				content += "stage('$stageName') {\n"
				content += "    steps {\n"
				content += "        script {\n"
                content += "            if (!utils) {\n"
                content += "                utils = load 'utils.groovy'\n";
                content += "                pf = load('rtk_stages.groovy')\n";
                content += "                pf.init()\n";
                content += "            }\n"
                content += "            pf.execStage('$actionName', '$stageName')\n"
                //content += "            def action = utils.loadAction('$actionName')\n"
				//content += "            action.func(pf.modules, pf.modules.configs['$stageName'].settings, pf.modules.configs['$stageName'].preloads)\n"
				content += "        }\n"
				content += "    }\n"
				content += "}\n"
			}
*/
        }
    }
	return content
}

def execStage(actionName, stageName) {
    if (modules.coreActions.contains(actionName)) {
        def action = utils.loadAction(actionName)
        def stageConfig = modules.configs[stageName].settings
        def stagePreloads = modules.configs[stageName].preloads
        action.func(modules, stageConfig, stagePreloads)
    }
    else {
        def action = utils.loadAction(actionName)
        try {
            if (modules.easyActions.contains(actionName) == true) {
                action.func()
            }
            else {
                def stageConfig = modules.configs[stageName].settings
                def stagePreloads = modules.configs[stageName].preloads
                action.func(modules, stageConfig, stagePreloads)
            }
        }
        catch (e) {
            error(message: "${stageName} is unstable " + e)
        }
    }        
}

def daggerSection() {
    def content = "stage('Dagger') {\n"
    content += "    steps {\n"
    content += "        script {\n"
    content += "            sh '''\n"
    content += "                dagger-cue project init\n"
    content += "                dagger-cue project update\n"
    content += "                dagger-cue do hello --log-format=plain\n"
    content += "            '''\n"
    content += "        }\n"
    content += "    }\n"

    return content
}

def format(globalConfig) {
    if (! utils) {
        utils = load 'utils.groovy'
    }
    def stages = globalConfig.stages
    def nodeLabel = ""
    if (globalConfig.nodes.size() > 0) {
        nodeLabel = globalConfig.nodes[0]
    }
    def nodeSection = "def nodeLabel='$nodeLabel'\n"
    def topHalf = readFile file: 'Jenkinsfile.tophalf'
    def sourceOnly = false
    if (globalConfig.dagger) {
        sourceOnly = true
    }
    def content = iterateToFile(stages, sourceOnly)
    if (globalConfig.dagger) {
        content += daggerSection()
    }
    def bottomHalf = readFile file: 'Jenkinsfile.bottomhalf'

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
            if (modules.easyActions.contains(actionName) == false  && modules.configs[stageName] == null) {
                // configurations is necessary for non-easy actions
                print "skip $stageName (not configured)"
                continue
            }

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
                startComposition(stageConfig, stagePreloads)
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
            /*
            else if (modules.coreActions.contains(actionName)) {
                stage(stageDisplayName) {
                    def action = utils.loadAction(actionName)
                    action.func(modules, stageConfig, stagePreloads)
                }
            }
            else {
                stage(stageDisplayName) {
                    def action = utils.loadAction(actionName)
                    try {
                        if (modules.easyActions.contains(actionName) == true) {
                            action.func()
                        }
                        else {
                            action.func(modules, stageConfig, stagePreloads)
                        }
                    }
                    catch (e) {
                        error(message: "${stageName} is unstable " + e)
                    }
                }
            }
            */
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

def parallelBuild(parallelParameters, parallelExcludes, stages, nodeName) {
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
        modules.global_vars.buildBranches << escapedBashVariablename(stageName)
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
                print "Set parallel build WS: ${customWS}"

                ws (customWS) {
                    withEnv(envvar) {
                        stage(stageName) {
                            pascCleanWs()
                            iterateStages(stages)
                        }
                    }
                }
            }
        }
    }

    stage('Parallel') {
        parallel jobs
    }
}

def startComposition(stageConfig, stagePreloads) {
    if (stageConfig.run_type == "SEQUENTIAL") {
        parallelBuild(stageConfig.parallel_parameters, stageConfig.parallel_excludes, stageConfig.stages, stageConfig.node)
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
        parallelBuild(modules.global_vars.parallel_parameters, emptyList, modules.global_vars.parallel_stages, nodeName)
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
