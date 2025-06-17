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

def updateStageConfig(configs) {
    def stageName = configs["stageName"]
    writeJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json", json: configs, pretty: 2
}

// A: preview-report-committer.json: all defects () in the stream
// B: cvssreport.json: all defects (with related cvss info.) in the project
// C: existed issue (in specified project)
// in A, and not triaged as Ignore:      create new
// in A, and triaged as Ignore:          create new, and close
// in C, not in B:                       close (existed)
// note:                                 component policy, in A, and triaged as Ignore, only the Jira issue match exact component will be closed
//                                          author policy, in A, and triaged as Ignore, only one Jira issue so only one will be closed
def copyDefectsArtifacts(upstreamJobName, upstreamBuildNumber, buildBranch) {
    def reportFile
    if (buildBranch == null) {
        reportFile = "preview-report-committer.json"
    }
    else {
        reportFile = "preview-report-committer-${buildBranch}.json"
    }
    print "projectName: " + upstreamJobName
    print "buildNumber: " + upstreamBuildNumber
    def reportExisted = fileExists reportFile
    if (buildBranch == null && reportExisted == true) {
        print "copyDefectsArtifacts: ${reportFile} existed already"
        return true
    }
    // Force copy for parallel builds
    try {
        step([$class: 'CopyArtifact', 
                filter: reportFile, 
                flatten: false, 
                projectName: upstreamJobName, 
                selector: [$class: 'SpecificBuildSelector', buildNumber: "${upstreamBuildNumber}"]])
    }
    catch (e) {
        if (buildBranch == null) {
            // for standalone build, check artifcats at WORKSPACE
            if (fileExists(reportFile) == true) {
                print "Take preview-report-committer.json under WORKSPACE"
                return true
            }
        }
        unstable("JIRA action: copy artifacts ${reportFile} failed " + e)
        return false
    }

    return true
}

def pfParallelInfo(copyPreviewReport) {
    def upstreamJobName = env.JOB_NAME
    def upstreamBuildNumber = env.BUILD_NUMBER
    if (env.UPSTREAM_JOB_NAME) {
        upstreamJobName = env.UPSTREAM_JOB_NAME
    }
    if (env.UPSTREAM_BUILD_NUMBER) {
        upstreamBuildNumber = env.UPSTREAM_BUILD_NUMBER
    }

    def validBranches = []
    if (env.PF_GLOBAL_PARALLELINFO) {
        // get parallel build info.
        def branches
        if (env.UPSTREAM_BRANCHES) {
            // user defined parallel build info.
            // usage: coverity analysis job on the same jenkins host
            //        Coverity job: parallel coverity analysis
            //        JIRA job: copyArtifacts stage + JIRA
            branches = env.UPSTREAM_BRANCHES.split(",")
        }
        else {
            // usage: like composition(parallel) + JIRA
            unstash name: 'pf-global-parallelinfo'
            def parallelInfo = readJSON file: 'parallelInfo.json'
            branches = parallelInfo.branches
        }
        print "pfParallelInfo: branches, " + branches
        if (copyPreviewReport == true) {
            // copy upstream artifacts
            for (def i=0; i<branches.size(); i++) {
                def buildBranch = branches[i]
                def ret = copyDefectsArtifacts(upstreamJobName, upstreamBuildNumber, buildBranch)
                if (ret == true) {
                    validBranches << buildBranch
                }
                else {
                    print "pfParallelInfo: skip branch, ${buildBranch}"
                }
            }
        }
    }
    else {
        print "pfParallelInfo: single build"
        if (copyPreviewReport == true) {
            copyDefectsArtifacts(upstreamJobName, upstreamBuildNumber, null)
        }
    }

    return validBranches
}

def pfDeleteDir(dirToDelete) {
    if (env.PF_BUILD_ENV == "none") {
        dir (dirToDelete) {
            deleteDir()
        }
    }
    else {
        def cmd = decorateCommand("rm -rf ${dirToDelete}")
        print "pfDeleteDir: ${cmd}"
        sh cmd
    }
}

def unstashPipelineFramework() {
    print "Unstash PF under " + pwd()
    // unstash to PF_ROOT
    env.PF_ROOT = ".pf-all"
    print "env.PF_ROOT ${env.PF_ROOT}"
    dir (WORKSPACE) {
        pfDeleteDir(env.PF_ROOT)
        dir (env.PF_ROOT) {
            // WORKAROUND (windows virus issue ITSDLC-779)
            // windows agent would be disconnected after unstash "stash-pf-framework"
            // call git clone to avoid this issue
            // git clone jenkins-pipeline should be called prior to unstash name: "stash-pf-config", to avoid git "not an empty directory" error
            if (isUnix() == true) {
                //unstash name: "stash-pf-framework"
            }
            else {
                print "git clone (workaround)"
                if (env.PF_DEBUG_RESTARTABLE) {
                    bat """
                    set GIT_SSL_NO_VERIFY=true && git clone ${PF_FRAMEWORK_URL}/gerrit/sdlc/jenkins-pipeline --depth 1 -b ${PF_FRAMEWORK_DEV_BRANCH} .
                    """
                }
                else {
                    bat """
                    set GIT_SSL_NO_VERIFY=true && git clone ${PF_FRAMEWORK_URL}/gerrit/sdlc/jenkins-pipeline --depth 1 -b ${PF_FRAMEWORK_PROD_BRANCH} .
                    """
                }
            }
            print "unstash stash-pf-framework finished"
            unstash name: "stash-pf-config"
            print "unstash stash-pf-config finished (utils)"
        }
    }
}

def isDynamicParameter(parameter) {
    if (parameter == null || parameter == "") {
        return false
    }

    if (parameter instanceof java.lang.String) {
        def dynamicPrefixes = ["sh", "bat", "bash"]
        def tokens = parameter.split()
        if (dynamicPrefixes.contains(tokens[0])) {
            return true
        }
        else {
            return false
        }
    }

    return false
}

// for general commands, like echo "test"
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

def extractRealActionName(stageName) {
    def actionName

    if (stageName.indexOf('@') < 0) {
        // build-dummy -> "build"
        actionName = stageName.split(/-/)
        actionName = actionName[0]
    }
    else {
        // composition@build-dummy -> "build"
        // composition-dummy@build-dummy -> "build"
        def stageNameTokens = stageName.split(/@/)
        actionName = stageNameTokens[1].toString().split(/-/)
        actionName = actionName[0]
    }

    if (actionName == "buildwithcoverity") {
        actionName = "coverity"
    }

    return actionName
}

def extractActionName(stageName) {
    def actionName

    if (stageName.indexOf('@') < 0) {
        // build-dummy -> "build"
        actionName = stageName.split(/-/)
        actionName = actionName[0]
    }
    else {
        // composition@build-dummy -> "build"
        // composition-dummy@build-dummy -> "build"
        // composition-dummy@0@build-dummy -> "build"
        def stageNameTokens = stageName.split(/@/)
        def lastIndex = stageNameTokens.size() - 1
        actionName = stageNameTokens[lastIndex].toString().split(/-/)
        actionName = actionName[0]
    }

    if (actionName == "buildwithcoverity") {
        actionName = "coverity"
    }

    return actionName
}

def finalizeInit(stageName, defaultConfigs) {
    // env.PF_PATH should have / suffix
    writeJSON file: "${env.PF_PATH}settings/${stageName}_config.json", json: defaultConfigs, pretty: 2
    print "PF: writeback ${env.PF_PATH}settings/${stageName}_config.json"
}

def commonInit(stageName, defaultConfigs) {
    def userScripts

    def hasJsonConfig = fileExists env.PF_PATH + "settings/${stageName}_config.json"
    if (hasJsonConfig == true) {
        userScripts = readJSON file: env.PF_PATH + "settings/${stageName}_config.json"
        // retrieve config from userScripts
        for (def key in defaultConfigs.keySet()) {
            if (userScripts."${key}" != null) {
                defaultConfigs."${key}" = userScripts."${key}"
            }
            else {
                // not defined in userScripts
            }
        }
    }
    else {
        try {
            userScripts = load env.PF_PATH + "settings/${stageName}_config.groovy"
            // retrieve config from userScripts
            for (def key in defaultConfigs.keySet()) {
                try {
                    defaultConfigs."${key}" = userScripts."${key}"
                }
                catch (e) {
                    // not defined in userScripts
                }
            }
        }
        catch (e) {
            print "$stageName not configured " + e
            return null
        }
    }

    def config = [:]
    config = defaultConfigs
    config['stageName'] = stageName
    config['plainStageName'] = stageName.replaceAll("@", "at")
    config['actionName'] = extractActionName(stageName)

    return config
}

def buildEnvPrefix(pfBuildEnv, pfBuildParams) {
    def prefix = ""
    def delimiter = pfBuildEnv.indexOf(":")
    def buildEnv = pfBuildEnv.substring(0, delimiter)
    def buildImage = pfBuildEnv.substring(delimiter + 1)
    if (buildEnv == "docker") {
        // --user \$(id -u):\$(id -g) would cause non-existed user error
        //command = "docker run --rm --env-file <(env) -v ${WORKSPACE}:${WORKSPACE} -w ${WORKSPACE} ${buildImage} ${buildEnvParams} ${command}"
        sh """
            printenv > .pf-env
        """
        prefix = "docker run --rm --env-file .pf-env -v ${WORKSPACE}:${WORKSPACE} -w ${WORKSPACE} ${pfBuildParams} ${buildImage}"
    }
    else if (buildEnv == "singularity") {
        def buildImages = buildImage.split(",")
        def overlay = ""
        if (buildImages.size() > 1) {
            overlay = "--overlay ${buildImages[1]}"
        }
        // bind tmp to avoid COV_AUTH_KEY not found error
        prefix = "singularity exec ${overlay} -B ${WORKSPACE}:${WORKSPACE} -B ${WORKSPACE_TMP}:${WORKSPACE_TMP} ${pfBuildParams} ${buildImages[0]}"
    }
    /*
    else if (buildEnv == "slurm") {
        def pythonExec = getPython()
        command = "${pythonExec} ${env.PF_ROOT}/pipeline_scripts/slurmWrapper.py -h ${buildImage} ${command}"
    }
    */
    return prefix
}

def decorateCommand(command) {
    if (env.PF_BUILD_ENV && env.PF_BUILD_ENV != "none") {
        def prefix = buildEnvPrefix(env.PF_BUILD_ENV, env.PF_BUILD_ENV_PARAMS)
        command = "${prefix} ${command}"
    }

    print "decorateCommand: ${command}"
    return command
}

/*
def resetPython() {
    def pyEnv = "PF_PYEXEC"
    if (env.BUILD_BRANCH) {
        pyEnv = "PF_PYEXEC_${env.BUILD_BRANCH}"
    }
    env."${pyEnv}" = ""
}
*/

def getPython() {
    def pyEnv = "PF_PYEXEC"
    if (env.BUILD_BRANCH) {
        pyEnv = "PF_PYEXEC_${env.BUILD_BRANCH}"
    }
    if (env."${pyEnv}") {
        return env."${pyEnv}"
    }
    else {
        def testPython = decorateCommand("python --version")
        def testPython3 = decorateCommand("python3 --version")
        if (isUnix()) {
            def statusPython3 = sh script: testPython3, returnStatus: true
            if (statusPython3 == 0) {
                env."${pyEnv}" = "python3"
            }
            else {
                def statusPython = sh script: testPython, returnStatus: true
                if (statusPython == 0) {
                    env."${pyEnv}" = "python"
                }
                else {
                    error("Please install python or switch to stable-pyless branch")
                }
            }
        }
        else {
            def statusPython = bat script: testPython, returnStatus: true
            if (statusPython == 0) {
                env."${pyEnv}" = "python"
            }
            else {
                def statusPython3 = bat script: testPython3, returnStatus: true
                if (statusPython3 == 0) {
                    env."${pyEnv}" = "python3"
                }
                else {
                    error("Please install python or switch to stable-pyless branch")
                }
            }
        }
        return env."${pyEnv}"
    }
}

def downloadSif(pyEnv) {
    def gerritProject = ""
    def image = ""
    def lfs = false

    if (pyEnv == "python") {
        gerritProject = "python"
        image = "python.sif"
    }
    else if (pyEnv == "openai") {
        gerritProject = "openai"
        image = "linux.sif"
        lfs = true
    }

    def imageExists = fileExists "${gerritProject}/${image}"
    if (imageExists == false) {
        sh """
        GIT_SSL_NO_VERIFY=true git clone https://mirror.rtkbf.com/gerrit/sdlc/jenkins-pipeline/singularity/${gerritProject} --depth 1
        """
        if (lfs == true) {
            dir (gerritProject) {
                sh """
                git lfs pull
                """
            }
        }
    }

    return "${gerritProject}/${image}"
}

def pyExec(actionName, stageName, command, args, pyEnv="RAW") {
    def currentENV = env.PF_BUILD_ENV

    print "pyExec: pyEnv ${pyEnv}"
    if (pyEnv != "RAW") {
        if (isUnix() == true) {
            def img = ""
            dir ("${env.PF_ROOT}/singularity") {
                if (env.BUILD_URL.indexOf("apiproxy") >= 0) {
                    // TODO: ugly workaround for apiproxy.rtkbf.com
                    copyArtifacts filter: "python.sif", projectName: "Admin/download-pipelineframework"
                    img = "python.sif"
                }
                else {
                    img = downloadSif(pyEnv)
                }
            }
            env.PF_BUILD_ENV = "singularity:${env.PF_ROOT}/singularity/${img}"
            print "pyExec: PF_BUILD_ENV ${env.PF_BUILD_ENV}"
        }
    }

    def plainStageName = stageName.replaceAll("@", "at")
    def pythonExec = getPython()
    def pyCmd = decorateCommand("${pythonExec} ${env.PF_ROOT}/pipeline_scripts/${actionName}.py -f ${env.PF_ROOT}/settings/${stageName}_config.json -w .pf-${plainStageName}")
    if (command != "") {
        pyCmd = "${pyCmd} -c ${command}"
    }
    for (def i=0; i<args.size(); ) {
        pyCmd = "${pyCmd} ${args[i]} ${args[i + 1]}"
        i += 2
    }

    if (isUnix()) {
        sh pyCmd
    }
    else {
        bat pyCmd
    }

    env.PF_BUILD_ENV = currentENV
}

def shellScript(underUnix, dstFile, toolbox, workDir) {
    if (dstFile.endsWith(".py")) {
        def pythonExec = utils.getPython()
        if (underUnix == true) {
            sh "PF_WORK_DIR=${workDir} ${pythonExec} ${dstFile}"
        }
        else {
            bat "set PF_WORK_DIR=${workDir} && ${pythonExec} ${dstFile}"
        }
        return
    }

    if (underUnix == true || dstFile.endsWith(".sh")) {
        if (toolbox != "") {
            toolbox = "${toolbox} "
        }
        def statusCode = sh script: "${toolbox}bash", returnStatus: true
        if (statusCode == 0) {
            sh "${toolbox}bash -xe '${dstFile}'"
        }
        else {
            sh "${toolbox}sh -xe '${dstFile}'"
        }
    }
    else {
        bat "\"${dstFile}\""
    }
}

def fileScript(underUnix, type, script, toolbox, sshcredentials, workDir) {
    def dstFile
    if (underUnix == true || script.endsWith(".sh")) {
        def userScripts = fileExists "${env.PF_ROOT}/scripts/${script}"
        if (userScripts) {
            dstFile = "${env.PF_ROOT}/scripts/${script}"
        }
        else {
            dstFile = "${env.PF_ROOT}/pipeline_scripts/${script}"
        }
    }
    else {
        dstFile = "${env.PF_ROOT}\\scripts\\${script}"
    }
    if (type == "source") {
        // TODO: support configs.types[i] == "." for sh/dash
        // notice: shebang should be written at first line
        sh """#!/bin/bash
            mypwd=\$PWD
            printenv > .private-source-before
            . ${dstFile}
            cd \$mypwd
            printenv > .private-source-after
        """
        def lines = sh(script: "diff -u .private-source-before .private-source-after | grep -E '^\\+'", returnStdout: true).trim()
        lines = lines.readLines().drop(1) // drop first line
        for (def line in lines) {
            if (line.startsWith("+")) {
                def tokens = line.split("=")
                if (tokens[0] == "+_" || tokens[0] == "+OLDPWD") {
                    // skip self (printenv), OLDPWD
                }
                else {
                    def varname = tokens[0].substring(1, tokens[0].length())
                    def varvalue = tokens[1]

                    exportEnvVar(varname, varvalue)
                }
            }
        }
    }
    else if (type == "groovy") {
        def externalMethod = load(dstFile)
        externalMethod.func()
    }
    else if (type == "file") {
        if (sshcredentials == "") {
            shellScript(underUnix, dstFile, toolbox, workDir)
        }
        else {
            sshagent(credentials: [sshcredentials]) {
                shellScript(underUnix, dstFile, toolbox, workDir)
            }
        }
    }
}

def inlineScript(command, underUnix, toolbox) {
    if (underUnix == true) {
        if (toolbox != "") {
            toolbox = "${toolbox} "
        }
        sh toolbox + command
    }
    else {
        bat command
    }
}

def archiveStageArtifacts(stageName) {
    def artifacts = []
    def plainStageName = stageName.replaceAll("@", "at")
    dir (".pf-${plainStageName}") {
        def hasArtifacts = fileExists ".artifacts"
        if (hasArtifacts == true) {
            def line = readFile file: ".artifacts"
            artifacts = line.split(",")
            print "archiveStageArtifacts: ${artifacts}"
        }
    }
    for (def artifact in artifacts) {
        if (artifact != "") {
            if (artifact.startsWith("WORKSPACE:")) {
                archiveArtifacts artifacts: artifact.substring(artifact.indexOf(':') + 1), allowEmptyArchive: true
            }
            else {
                dir (".pf-${plainStageName}") {
                    archiveArtifacts artifacts: artifact, allowEmptyArchive: true
                }
            }
        }
    }
}

def exportEnvVar(varname, varvalue) {
    // Note: BUILD_BRANCH prefix should be add to variable name,
    // or redundant variables will be declared
    if (env.BUILD_BRANCH != null) {
        if (varname.startsWith("PIPELINEGLOBAL_")) {
            varname = varname.substring(15)
            //print "Export general pipeline env. variables(aux.): ${varname} ${varvalue}"
            env."$varname" = varvalue
        }
        varname = "BR${env.BUILD_BRANCH}_${varname}"
        //print "Export parallel-build pipeline env. variables: ${varname} ${varvalue}"
        env."$varname" = varvalue
    }
    else {
        //print "Export general pipeline env. variables: ${varname} ${varvalue}"
        env."$varname" = varvalue
    }

    if (varname.indexOf("PASS") >= 0 || varname.indexOf("TOKEN") >= 0) {
        print "Export pipeline env. variables: ${varname} ******"
    }
    else {
        print "Export pipeline env. variables: ${varname} ${varvalue}"
    }
}

def exportEnv() {
    def gitExists = fileExists 'env'
    if (gitExists == true) {
        def fp = readFile 'env'
        def lines = fp.readLines()
        for (def line in lines) {
            def tokens = line.split("=")
            if (tokens.size() > 1) {
                if (tokens[1].startsWith("TEXT_")) {
                    tokens[1] = tokens[1].substring(5)
                    exportEnvVar(tokens[0], tokens[1].replaceAll(",", "\n"))
                }
                else {
                    exportEnvVar(tokens[0], tokens[1])
                }
            }
            else {
                // empty env. var is not allowed in Jenkins
                exportEnvVar(tokens[0], "PF_NONE")
            }
        }
    }
}

def loadCoreAction(relativePath, actionName) {
    def action = null

    dir (relativePath) {
        dir ("groovys") {
            action = load "${actionName}.groovy"
        }
    }

    return action
}

def loadUserAction(relativePath, actionName) {
    def action = null

    dir (relativePath) {
        dir ("scripts") {
            action = load "${actionName}.groovy"
        }
    }

    return action
}

def jsonArrayToString(jsonArray, delimiter) {
    def pureArray = []
    for (def i=0; i<jsonArray.size(); i++) {
        pureArray.add(jsonArray[i])
    }
    if (pureArray.size() == 0) {
        return ""
    }
    else {
        return pureArray.join(delimiter)
    }
}

def translateConfig(stageName) {
    def pythonExec = utils.getPython()
    def translateCmd = "${pythonExec} ${env.PF_ROOT}/pipeline_scripts/utils.py -f ${env.PF_ROOT}/settings/${stageName}_config.json -c TRANSLATE_CONFIG"
    if (isUnix()) {
        sh translateCmd
    }
    else {
        bat translateCmd
    }
}

return this
