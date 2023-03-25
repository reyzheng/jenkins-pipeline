def init(stageName) {
    def utils = load "utils.groovy"
    def actionName = utils.extractActionName(stageName)

    def defaultConfigs = [
        // script
        display_name: "",
        enable: true,
        sshcredentials: "",
        types: [],
        contents: [],
        expressions: [],
        // mapping options: 
        //     manytoone: all scripts share one coverity config
        //     onetoone: one script map one coverity config
        //     onetomany: one script for all coverity configs
        buildmapping: "onetoone",
        // coverity
        coverity_scan_enabled: true,
        coverity_local_report: true,
        coverity_analyze_defects: false,
        coverity_report_path: '',
        coverity_analyze_defects_options: "",
        coverity_defects_assign_policy: "committer",
        coverity_analyze_rtkonly: false,
        coverity_host: '172.21.15.146',
        coverity_port: '8080',
        coverity_auth_key_credential: '',
        coverity_scan_path: '',
        coverity_scan_toolbox: '',
        coverity_xml: 'coverity_idir/coverity.xml',
        coverity_build_dir: 'coverity_idir/build',
        coverity_project: [],
        coverity_stream: [],
        coverity_comptype_platform: [],
        coverity_comptype_prefix: [],
        coverity_comptype: [],
        coverity_comptype_gcc: [],
        coverity_comptype_ld: [],
        coverity_build_option: [],
        coverity_clean_builddir: true,
        coverity_analyze_parent: "none",
        coverity_analyze_option: [],
        // default 'default' at def init(stageName)
        coverity_checker_enablement: [],
        coverity_coding_standards: [],
        // coverity_pattern_specified, coverity_pattern_excluded conflicts with coverity_analyze_rtkonly
        coverity_pattern_specified: [],
        coverity_pattern_excluded: [],

        coverity_snapshot_version: [],
        coverity_snapshot_description: [],

        scriptableParams: ["enable", "coverity_scan_enabled", "coverity_analyze_parent", "coverity_project", "coverity_stream", "coverity_comptype", "coverity_comptype_gcc", "coverity_snapshot_version", "coverity_snapshot_description"]
    ]
    def mapConfig = utils.staticInit(stageName, defaultConfigs)

    if (mapConfig.coverity_stream instanceof java.lang.String) {
        // TODO: tell user deprecated
        convertToList(mapConfig)
    }

    // stash scripted params' script file
    utils.stashScriptedParamScripts(mapConfig.plainStageName, mapConfig)

    // stash checker files
    if (mapConfig.coverity_checker_enablement.contains("custom")) {
        dir ("scripts") {
            def checkersCustomExists = fileExists "checkers_custom"
            if (checkersCustomExists == false) {
                error("Coverity: custom checker file scripts/checkers_custom does not exist")
            }
            else {
                stash name: "stash-checkers-custom", includes: "checkers_custom"
            }
        }
    }
    dir ('rtk_coverity') {
        stash name: "stash-checkers-default", includes: "checkers_*"
        dir ('coding-standards') {
            stash name: "stash-coding-standards", includes: ""
        }
    }

    if (mapConfig.coverity_analyze_defects == true) {
        dir ("groovys") {
            stash name: "stash-actions-covanalyze", includes: "covanalyze.groovy"
        }
        def action = utils.loadAction("covanalyze")
        action.stashScriptsConfigs()
    }

    // copy from script.groovy
    def filesToStash = []
    for (def i=0; i<mapConfig.types.size(); i++) {
        if (mapConfig.types[i] != "inline") {
            filesToStash << mapConfig.contents[i]
        }
    }
    mapConfig.has_stashes = false
    if (filesToStash.size() > 0) {
        mapConfig.has_stashes = true
        dir("scripts") {
            print "${stageName}: stash files " + filesToStash.join(",")
            stash name: "stash-script-${mapConfig.plainStageName}", includes: filesToStash.join(",")
        }
    }

    // check credentials
    def underUnix = isUnix()
    if (mapConfig.coverity_auth_key_credential != "" && underUnix == true) {
        withCredentials([file(credentialsId: mapConfig.coverity_auth_key_credential, variable: 'KEY_PATH')]) {
            def keyObj = readJSON file: KEY_PATH
            def checkHealth = utils.captureStdout("set +x && curl --header 'Accept: application/json' --user ${keyObj.username}:${keyObj.key} http://${mapConfig.coverity_host}:${mapConfig.coverity_port}/api/v2/serverInfo/version", underUnix)
            if (checkHealth[0] == "Authentication failed.") {
                error("${stageName}: invalid coverity credentials")
            }
        }
    }

    dir('scripts') {
        try {
            stash name: 'stash-coverity-checkout-parent', includes: 'checkout-*.sh'
        }
        catch(e) {}
    }

    dir ('.pf-coverity') {
		writeJSON file: 'stage-config.json', json: mapConfig
		stash name: "stash-config-${mapConfig.plainStageName}", includes: 'stage-config.json'
	}
}

def convertToList(rawConfig) {
    def coverity_stream = rawConfig.coverity_stream
    rawConfig.coverity_stream = []
    rawConfig.coverity_stream << coverity_stream

    // coverity_comptype was later added
    try {
        def coverity_comptype = rawConfig.coverity_comptype
        rawConfig.coverity_comptype = []
        rawConfig.coverity_comptype << coverity_comptype
    }
    catch (e) {
        rawConfig.coverity_comptype = []
        rawConfig.coverity_comptype << ""
    }

    def coverity_comptype_prefix = rawConfig.coverity_comptype_prefix
    rawConfig.coverity_comptype_prefix = []
    rawConfig.coverity_comptype_prefix << coverity_comptype_prefix

    def coverity_comptype_gcc = rawConfig.coverity_comptype_gcc
    rawConfig.coverity_comptype_gcc = []
    rawConfig.coverity_comptype_gcc << coverity_comptype_gcc

    def coverity_comptype_ld = rawConfig.coverity_comptype_ld
    rawConfig.coverity_comptype_ld = []
    rawConfig.coverity_comptype_ld << coverity_comptype_ld

    def coverity_checker_enablement = rawConfig.coverity_checker_enablement
    rawConfig.coverity_checker_enablement = []
    rawConfig.coverity_checker_enablement << coverity_checker_enablement

    //return rawConfig
}

def configurationFillup(pipelineAsCode, coverityConfig) {
    if (coverityConfig.coverity_analyze_defects_options instanceof java.lang.String) {
        if (coverityConfig.coverity_analyze_defects_options == "") {
            coverityConfig.coverity_analyze_defects_options = [:]
        }
        else {
            coverityConfig.coverity_analyze_defects_options = readJSON text: coverityConfig.coverity_analyze_defects_options
        }
    }
    if (coverityConfig.coverity_auth_key_credential == "") {
        try {
            // test global_config.coverity_credentials
            coverityConfig.coverity_auth_key_credential = pipelineAsCode.global_vars.coverity_credentials
        }
        catch(e) {
        }
    }

    return coverityConfig
}

def pickChecker(versionText, checkerText) {
    def version = versionText.split("-")
    version = version[1].trim()
    print "Pickup version ${version}"
    def checkerObject = readJSON text: checkerText
    if (checkerObject."${version}" == null) {
        version = "default"
    }
    writeFile(file: 'checkers', text: checkerObject."${version}".options)
}

def captureStdout(command, underUnix) {
    def stdout = ""
    try {
        if (underUnix == true) {
            stdout = sh(script: command, returnStdout: true).trim()
            stdout = stdout.readLines()
        }
        else {
            //command = command.replaceAll("%", "%%")
            stdout = bat(script: command, returnStdout: true).trim()
            stdout = stdout.readLines().drop(1)
        }
    }
    catch (e) {
    }
    return stdout
}

def extractAnalyzeArgs(coverityConfig, idx, underUnix) {
    def extraAnalyzeArgs = ""
    if (coverityConfig.coverity_analyze_option[idx]) {
        extraAnalyzeArgs = coverityConfig.coverity_analyze_option[idx]
        extraAnalyzeArgs = extraAnalyzeArgs.split(",")
        extraAnalyzeArgs = extraAnalyzeArgs.join(" ")
    }
    def sourcePath = env."PF_SOURCE_DST_${idx}"
    // analyze realtek commit file only
    if (coverityConfig.coverity_analyze_rtkonly == true) {
        def rtkFiles = [:]
        def tuPatterns = []
        def gitLogScript
        if (underUnix) {
            gitLogScript = "git log --committer=\"realtek\" --committer=\"realsil\" --format=\"\" --name-only --no-merges HEAD | uniq"
        }
        else {
            gitLogScript = "git log --committer=\"realtek\" --committer=\"realsil\" --format=\"\" --name-only --no-merges HEAD | sort /unique"
        }
        def gitLogOutput
        print "Move to path: ${sourcePath}"
        if (sourcePath == "") {
            gitLogOutput = captureStdout(gitLogScript, underUnix)
        }
        else {
            dir(sourcePath) {
                gitLogOutput = captureStdout(gitLogScript, underUnix)
            }
        }
        for (def i=0; i<gitLogOutput.size(); i++) {
            tuPatterns << "file('${gitLogOutput[i]}')"
        }
        def tuPattern = tuPatterns.join("||")
        extraAnalyzeArgs += " --tu-pattern \"${tuPattern}\""
    }
    return extraAnalyzeArgs
}

def codingStandards(coverityConfig, idx) {
    def command = ""
    if (coverityConfig.coverity_coding_standards[idx]) {
        command += "--security"
        def standards = coverityConfig.coverity_coding_standards[idx].split(",")
        dir('.coding-standards') {
            unstash name: "stash-coding-standards"
        }
        for (def i=0; i<standards.size(); i++) {
            command += " --coding-standard-config=.coding-standards/${standards[i]}.config"
        }
    }
    return command
}

//def coverity_scan(pipelineAsCode, coverityConfig, coverityPreloads, buildScriptType, buildScript, idx, withScriptAction) {
def coverity_scan(coverityConfig, coverityPreloads, buildScriptType, buildScript, idx, withScriptAction) {
    def coverity_report_path = coverityConfig.coverity_report_path
    def coverity_scan_toolbox = coverityConfig.coverity_scan_toolbox
    def coverity_scan_path = coverityConfig.coverity_scan_path
    def coverity_xml = coverityConfig.coverity_xml
    def coverity_build_dir = coverityConfig.coverity_build_dir + idx
    def coverity_host = coverityConfig.coverity_host
    def coverity_port = coverityConfig.coverity_port
    def coverity_stream = coverityConfig.coverity_stream[idx]
    def coverity_comptype = coverityConfig.coverity_comptype[idx]
    def coverity_comptype_prefix = coverityConfig.coverity_comptype_prefix[idx]
    def coverity_comptype_gcc = coverityConfig.coverity_comptype_gcc[idx]
    def coverity_comptype_ld = coverityConfig.coverity_comptype_ld[idx]
    def checkerEnablement = coverityConfig.coverity_checker_enablement[idx]
    def checkerText
	
    if (coverityConfig.coverity_auth_key_credential == "") {
        error("Invalid coverity token credentials")
    }
    dir(".coverity-checker") {
        if (checkerEnablement == "custom") {
            unstash "stash-checkers-custom"
            checkerText = readFile "checkers_custom"
        }
        else {
            unstash "stash-checkers-default"
            if (checkerEnablement == "none") {
                checkerText = readFile "checkers_none"
            }
            else if (checkerEnablement == "heavy") {
                checkerText = readFile "checkers_heavy"
            }
            else if (checkerEnablement == "medium") {
                checkerText = readFile "checkers_medium"
            }
            else if (checkerEnablement == "medium-light") {
                checkerText = readFile "checkers_medium-light"
            }
            else if (checkerEnablement == "default-light") {
                checkerText = readFile "checkers_default-light"
            }
            else {
                checkerText = readFile "checkers_default"
            }
        }
        deleteDir()
    }

    def underUnix = isUnix()
    def pwdPath
    if (underUnix == true) {
        pwdPath = sh (script: "pwd", returnStdout: true).trim()
    }
    else {
        pwdPath = bat (script: "echo %cd%", returnStdout: true).trim()
        pwdPath = pwdPath.readLines().drop(1).join(" ")
        // auto replace back slash
		coverity_build_dir = coverity_build_dir.replaceAll("/", "\\\\")
		coverity_xml = coverity_xml.replaceAll("/", "\\\\")
    }

    def coverity_command_prefix = ""
    if (coverity_scan_toolbox != "") {
        // check if coverity_scan_toolbox_bindpath defined
        def bindPath = "-B ${WORKSPACE}:${WORKSPACE} "
        try {
            def bindPaths = coverityConfig.coverity_scan_toolbox_bindpath
            if (bindPaths.trim() != "") {
                bindPaths = coverityConfig.coverity_scan_toolbox_bindpath.split(",")
                for (def i=0; i<bindPaths.size(); i++) {
                    bindPath = bindPath + "-B ${bindPaths[i]} "
                }
            }
        }
        catch(e) {
            // coverity_scan_toolbox_bindpath not defined
        }
        coverity_command_prefix = "singularity exec $bindPath -H $pwdPath " + coverity_scan_toolbox + " "
    }
    else if (coverity_scan_path != "") {
        if (underUnix == true) {
            coverity_command_prefix = coverity_scan_path + "/"
        }
        else {
            // handle space character
            coverity_command_prefix = "\"" + coverity_scan_path + "\"\\"
        }
    }
    // TODO: empty coverity_scan_path for PATH

    try {
        // cov-configure
        if (coverityConfig.coverity_clean_builddir == true) {
            if (underUnix == true) {
                sh "rm -rf ${coverity_build_dir}"
            }
            else {
                bat "if exist ${coverity_build_dir} rd ${coverity_build_dir} /s /q"
            }
        }
        if (underUnix == true) {
            sh "rm -f ${coverity_xml}"
            sh 'mkdir -p ' + coverity_build_dir
        }
        else {
            bat "if exist ${coverity_xml} del ${coverity_xml} /f"
            bat 'md ' + coverity_build_dir
        }
        if (coverityConfig.coverity_comptype_platform[idx] && coverityConfig.coverity_comptype_platform[idx] != "") {
            def buildPlatforms = coverityConfig.coverity_comptype_platform[idx]
            buildPlatforms = buildPlatforms.split(",")
            buildPlatforms.each { buildPlatform ->
                if (underUnix == true) {
                    sh coverity_command_prefix + "cov-configure --config $coverity_xml --${buildPlatform} --template"
                }
                else {
                    bat coverity_command_prefix + "cov-configure --config $coverity_xml --${buildPlatform} --template"
                }
            }
        }
        if (coverity_comptype_prefix && coverity_comptype_prefix != "") {
            if (underUnix == true) {
                sh coverity_command_prefix + "cov-configure --config $coverity_xml --comptype prefix --compiler $coverity_comptype_prefix --template"
            }
            else {
                bat coverity_command_prefix + "cov-configure --config $coverity_xml --comptype prefix --compiler $coverity_comptype_prefix --template"
            }
        }

        def scriptedComptype = coverity_comptype
        def scriptedCompiler = coverity_comptype_gcc
        if (scriptedCompiler && scriptedCompiler != "") {
            def compilers = scriptedCompiler.split(",")
            def comptypes = scriptedComptype.split(",")
            def j
            for (j=0; j<compilers.length; j++) {
                def compiler = compilers[j]
                def comptype = ""
                try {
                    comptype = comptypes[j]
                }
                catch (e) {
                    // coverity_comptype not configured
                }
                def configureCompilerCommand
                if (comptype == "") {
                    configureCompilerCommand = coverity_command_prefix + "cov-configure --config $coverity_xml --compiler $compiler --template"
                }
                else {
                    configureCompilerCommand = coverity_command_prefix + "cov-configure --config $coverity_xml --comptype $comptype --compiler $compiler --template"
                }
                if (underUnix == true) {
                    sh configureCompilerCommand
                }
                else {
                    bat configureCompilerCommand
                }
            }
        }
        if (coverity_comptype_ld && coverity_comptype_ld != "") {
            def configureLoaderCommand = coverity_command_prefix + "cov-configure --config $coverity_xml --comptype ld --compiler $coverity_comptype_ld --template"
            if (underUnix == true) {
                sh configureLoaderCommand
            }
            else {
                bat configureLoaderCommand
            }
        }

        // prepare cov-build, cov-analyze options
        def extraBuildArgs = ""
        def extraAnalyzeArgs = extractAnalyzeArgs(coverityConfig, idx, underUnix)
        if (coverityConfig.coverity_pattern_specified.size() > idx) {
            def patterns = coverityConfig.coverity_pattern_specified[idx].split(",")
            // --tu-pattern "file('path/to/dira/.*') || file('path/to/dirb/.*')"
            for (def i=0; i<patterns.size(); i++) {
                if (patterns[i].endsWith("/") || patterns[i].endsWith("\\")) {
                    // directory
                    patterns[i] = patterns[i] + ".*"
                }
                patterns[i] = "file('" + patterns[i] + "')"
            }
            def tuPattern = patterns.join("||")
            extraAnalyzeArgs += " --tu-pattern \"${tuPattern}\""
        }
        else if (coverityConfig.coverity_pattern_excluded.size() > idx) {
            def patterns = coverityConfig.coverity_pattern_excluded[idx].split(",")
            // --tu-pattern "!file('.*/mydir/.*')"
            for (def i=0; i<patterns.size(); i++) {
                if (patterns[i].endsWith("/") || patterns[i].endsWith("\\")) {
                    // directory
                    patterns[i] = patterns[i] + ".*"
                }
                patterns[i] = "!file('" + patterns[i] + "')"
            }
            def tuPattern = patterns.join("&&")
            extraAnalyzeArgs += " --tu-pattern \"${tuPattern}\""
        }
        if (extraAnalyzeArgs.indexOf("--coding-standard-config") >= 0 || checkerText.indexOf("--coding-standard-config") >= 0) {
            extraBuildArgs = "--emit-complementary-info "
        }
        if (checkerEnablement == "custom") {
            writeFile(file: 'checkers', text: checkerText)
        }
        else {
            def coverityVersionScript = "${coverity_command_prefix}cov-analyze --version"
            def version = captureStdout(coverityVersionScript, underUnix)
            pickChecker(version[0], checkerText)
        }

        // cov-build
        if (coverityConfig.coverity_build_option[idx]) {
            def buildArgs = coverityConfig.coverity_build_option[idx]
            buildArgs = buildArgs.split(",")
            extraBuildArgs += buildArgs.join(" ")
        }
        if (buildScriptType == "inline") {
            def buildCommand = coverity_command_prefix + "cov-build --dir $coverity_build_dir --config $coverity_xml $extraBuildArgs " + buildScript
            if (underUnix == true) {
                sh buildCommand
            }
            else {
                bat buildCommand
            }
        }
        else {
            def dstFile
            if (withScriptAction == true) {
                if (underUnix == true) {
                    dstFile = ".script/${buildScript}"
                }
                else {
                    dstFile = ".script\\${buildScript}"
                }
            }
            else {
                dstFile = env.WORKSPACE + "/script-covbuild-" + currentBuild.startTimeInMillis + ".bat"
                writeFile(file: dstFile , text: buildScript)
            }
            if (underUnix == true) {
                def shell = "sh"
                def statusCode = sh script: "bash", returnStatus: true
                if (statusCode == 0) {
                    shell = "bash"
                }
                sh coverity_command_prefix + "cov-build --dir $coverity_build_dir --config $coverity_xml $extraBuildArgs $shell '${dstFile}'"
            }
            else {
                bat coverity_command_prefix + "cov-build --dir $coverity_build_dir --config $coverity_xml $extraBuildArgs \"${dstFile}\""
            }
        }
    
        // cov-analyze
        def licenseServer = "#FLEXnet (do not delete this line)\nlicense-server 1123@papyrus.realtek.com\n"
        writeFile file: '.coverity.license.config', text: licenseServer
        def coverityCodingStandards = codingStandards(coverityConfig, idx)
        def coverityAnalyzeScript = coverity_command_prefix + "cov-analyze -sf .coverity.license.config --dir $coverity_build_dir ${extraAnalyzeArgs} @@checkers ${coverityCodingStandards}"
        if (underUnix == true) {
            sh coverityAnalyzeScript
        }
        else {
            bat coverityAnalyzeScript
        }

        // cov-commit
        def stream = coverity_stream
        // COVERITY_KEY_USER configured in jenkins credentials
        withCredentials([file(credentialsId: coverityConfig.coverity_auth_key_credential, variable: 'KEY_PATH')]) { //set SECRET with the credential content
            if (underUnix == true) {
                sh "chmod 600 \$KEY_PATH"
            }
            def snapshotID = 0
            def commitScript = coverity_command_prefix + "cov-commit-defects -sf .coverity.license.config --dir $coverity_build_dir --url http://$coverity_host:$coverity_port --stream \"$stream\" --auth-key-file ${KEY_PATH} --encryption none"
            if (coverityConfig.coverity_snapshot_version.size() > idx) {
                // coverity_snapshot_version has been specified
                def snapshotVersion = coverityConfig.coverity_snapshot_version[idx]
                if (snapshotVersion != "") {
                    commitScript += " --version ${snapshotVersion}"
                }
            }
            if (coverityConfig.coverity_snapshot_description.size() > idx) {
                // coverity_snapshot_description has been specified
                def snapshotDescription = coverityConfig.coverity_snapshot_description[idx]
                if (snapshotDescription != "") {
                    commitScript += " --description ${snapshotDescription}"
                }
            }

            def htmlReportScript
            if (coverityConfig.coverity_local_report == true) {
                htmlReportScript = coverity_command_prefix + "cov-format-errors -sf .coverity.license.config --dir $coverity_build_dir --html-output coverityReport"
            }
            else {
                htmlReportScript = "echo skip_local_report"
            }
            def commitOutputLines = captureStdout(commitScript, underUnix)
            if (underUnix == true) {
                sh "rm -rf coverityReport"
                sh htmlReportScript
            }
            else {
                bat "if exist coverityReport rd coverityReport /s /q"
                bat htmlReportScript
            }
            for (commitOutputLine in commitOutputLines) {
                if (commitOutputLine.startsWith("New snapshot ID ")) {
                    def tokens = commitOutputLine.split(" ")
                    snapshotID = tokens[3].toInteger()
                }
            }
            //snapshotID = 29285
            print "Got snapshotID ${snapshotID}"
            if (env.BUILD_BRANCH != null) {
                if (coverityConfig.refParent == true) {
                    env."${env.BUILD_BRANCH}_COV_STREAM_PARENT" = stream
                    env."${env.BUILD_BRANCH}_COV_SNAPSHOT_PARENT" = snapshotID
                }
                else {
                    env."${env.BUILD_BRANCH}_COV_STREAM" = stream
                    env."${env.BUILD_BRANCH}_COV_SNAPSHOT" = snapshotID
                }
            }
            else {
                if (coverityConfig.refParent == true) {
                    env."COV_STREAM_PARENT" = stream
                    env."COV_SNAPSHOT_PARENT" = snapshotID
                }
                else {
                    env."COV_STREAM" = stream
                    env."COV_SNAPSHOT" = snapshotID
                }
            }
            // cov-format-errors defects occurrence is more precise than that on cov-connect
            if (coverityConfig.coverity_local_report == true) {
                def reportFileName
                if (env.BUILD_BRANCH != null) {
                    reportFileName = "coverityReport-${env.BUILD_BRANCH}.zip"
                }
                else {
                    reportFileName = "coverityReport.zip"
                }
                if (underUnix == true) {
                    sh "rm -f ${reportFileName}"
                }
                else {
                    bat "if exist ${reportFileName} del ${reportFileName} /s /q"
                }
                zip zipFile: reportFileName, dir: "coverityReport"
                archiveArtifacts artifacts: reportFileName
            }

            // call covanalyze to do coverity analysis
            if (coverityConfig.coverity_analyze_defects == true) {
                def covanalyzeConfigs = coverityConfig

                covanalyzeConfigs.coverity_build_dir = coverityConfig.coverity_build_dir + idx
                covanalyzeConfigs.coverity_project = coverityConfig.coverity_project[idx]
                covanalyzeConfigs.coverity_stream = stream
                covanalyzeConfigs.coverity_snapshot = snapshotID
                covanalyzeConfigs.coverity_build_root = pwdPath
                def action = utils.loadAction("covanalyze")
                action.func(null, covanalyzeConfigs, null)
            }
        }
    }
    catch (e) {
        unstable(message: "Coverity build is unstable " + e)
    }
}

//def func(pipelineAsCode, buildConfig, buildPreloads) {
def func(stageName) {
    unstash name: "stash-script-utils"
    def utils = load "utils.groovy"
	utils.unstashConfig(stageName)
	def python = utils.execPython(stageName)
	if (isUnix()) {
		sh "$python \.pf-configs/stage-config.json"
	}
	else {
		bat "$python \.pf-configs\stage-config.json"		
	}
/*
    def validScriptTypes = ["inline", "file", "source", "groovy"]
    if (buildPreloads.actionName == "coverity") {
		// buildwithcoverity
        coverityConfig = buildConfig
        //coverityPreloads = buildPreloads
    }
    else {
		// build + coverity
        coverityConfig = pipelineAsCode.configs["coverity"].settings
        //coverityPreloads = pipelineAsCode.configs["coverity"].preloads
    }
    def buildDirs = []
    if (env.PF_MAIN_SOURCE_NAME) {
        def sourceNames = env.PF_MAIN_SOURCE_NAME.split(',')
        buildDirs = pipelineAsCode.configs[sourceNames[0]].settings.scm_dsts
    }
    else {
    }
    def branchSubDescription = ""
    if (env.BUILD_BRANCH) {
        branchSubDescription = env.BUILD_BRANCH
    }

    def scriptTypes
    def scriptContents
    def scriptAction = false
    if (buildConfig.types) {
        // do cov-analysis with script action
        scriptAction = true
        scriptTypes = buildConfig.types
        scriptContents = buildConfig.contents
        if (buildConfig.has_stashes == true) {
            dir(".script") {
                unstash "stash-script-${buildPreloads.plainStageName}"
            }
        }
    }
    else {
        // do cov-analysis with common_stage action
        scriptTypes = buildPreloads.scriptTypes
        scriptContents = buildPreloads.scripts
    }

    coverityConfig = configurationFillup(pipelineAsCode, coverityConfig)

    def coverityConfigScripted = [:]
    utils.unstashScriptedParamScripts(coverityPreloads.plainStageName, coverityConfig, coverityConfigScripted)

    if (coverityConfigScripted.coverity_scan_enabled == false || coverityConfigScripted.coverity_scan_enabled == "false") {
        print "Skip coverity analysis, build only"
        def action = utils.loadAction("script")
        action.func(pipelineAsCode, coverityConfigScripted, coverityPreloads)

        return
    }

    try {
        for (def i=0; i<scriptTypes.size(); i++) {
            if (validScriptTypes.contains(scriptTypes[i]) == false) {
                continue
            }

            if (scriptAction == true) {
                if (coverityConfigScripted.expressions[i] && coverityConfigScripted.expressions[i] != "") {
                    def expr = evaluate(coverityConfigScripted.expressions[i])
                    if (expr == false) {
                        print "skip ${i}th script"
                        continue
                    }
                }
            }

            def buildDir = ""
            if (scriptAction == false && buildDirs[i] != null) {
                buildDir = buildDirs[i]
            }
            def coverityConfigIdx = i
            if (coverityConfigScripted.buildmapping == "manytoone") {
                coverityConfigIdx = 0
            }
            def secondScanCleanDir = coverityConfigScripted.coverity_clean_builddir
            if (coverityConfigScripted.coverity_analyze_parent == "prev" ||
                    coverityConfigScripted.coverity_analyze_parent == "branch" ||
                    coverityConfigScripted.coverity_analyze_parent == "custom") {
                def varname
                secondScanCleanDir = false
                if (env.BUILD_BRANCH) {
                    varname = "${env.BUILD_BRANCH}_SOURCE_DIR${i}"
                }
                else {
                    varname = "SOURCE_DIR${i}"
                }
                def sourceDst = env."${varname}"

                if (coverityConfigScripted.coverity_analyze_parent == "custom") {
                    dir(".gitscript") {
                        unstash name: 'stash-coverity-checkout-parent'
                        unstash name: 'stash-script-bdsh'
                    }
                    sh """
                        sh .gitscript/bdsh.sh .gitscript/checkout-parent.sh
                    """
                }
                else {
                    dir(".gitscript") {
                        unstash name: "git-label-submodules"
                        unstash name: "git-checkout-parent"
                    }
                    sh """
                        sh .gitscript/git-label-submodules.sh ${sourceDst}
                        sh .gitscript/git-checkout-parent.sh ${sourceDst} ${coverityConfigScripted.coverity_analyze_parent}
                    """
                }
                dir(buildDir) {
                    coverityConfigScripted.refParent = true
                    coverity_scan(coverityConfigScripted, coverityPreloads, scriptTypes[i], scriptContents[i], coverityConfigIdx, scriptAction)
                }
                if (coverityConfigScripted.coverity_analyze_parent == "custom") {
                    dir(".gitscript") {
                        unstash name: 'stash-coverity-checkout-parent'
                        unstash name: 'stash-script-bdsh'
                    }
                    sh """
                        sh .gitscript/bdsh.sh .gitscript/checkout-current.sh
                    """
                }
                else {
                    dir(".gitscript") {
                        unstash name: "git-checkout-parent"
                    }
                    sh """
                        sh .gitscript/git-checkout-parent.sh ${sourceDst} forward
                    """
                }
            }
            dir(buildDir) {
                coverityConfigScripted.refParent = false
                coverityConfigScripted.coverity_clean_builddir = secondScanCleanDir
                coverity_scan(coverityConfigScripted, coverityPreloads, scriptTypes[i], scriptContents[i], coverityConfigIdx, scriptAction)
            }
        }
        env.PIPELINE_AS_CODE_STAGE_BUILD_RESULTS += "Build $branchSubDescription SUCCESS;"
    }
    catch (e) {
        // Set the result and add to map as UNSTABLE on failure
        unstable(message: "Coverity build $branchSubDescription is unstable " + e)
        env.PIPELINE_AS_CODE_STAGE_BUILD_RESULTS += "Build $branchSubDescription UNSTABLE;"
    }
*/
}

return this
