def init(stageName) {
    def defaultConfigs = [
        enabled: true,
        repo_path: "repo",
        display_name: "",
        scm_main: -1,
        scm_counts: 1,
        scm_types: ["git"],
        scm_urls: [""],
        scm_branchs: ["master"],
        scm_dsts: [""],
        scm_credentials: [""],
        scm_refspecs: [""],
        scm_git_clone_depth: [0],
        scm_git_recursivesubmodules: [false],
        scm_repo_manifest_files: ["default.xml"],
        scm_repo_manifest_groups: [""],
        scm_repo_manifest_currentbranchs: [true],
        scm_repo_manifest_notags: [true],
        scm_repo_manifest_depths: [1],
        scm_repo_manifest_platforms: ["linux"],
        scm_repo_reference: [""],
        scm_repo_mirror: [""],

        scriptableParams: ["scm_dsts", "scm_branchs"]
    ]

    def utils = load "utils.groovy"
    def config = utils.commonInit(stageName, defaultConfigs)
    dir ("groovys") {
        if (config.settings.scm_types.contains("git")) {
            stash name: "stash-actions-git", includes: "git.groovy"
        }
        if (config.settings.scm_types.contains("repo")) {
            stash name: "stash-actions-repo", includes: "repo.groovy"
        }
    }

    // stash scripted params' script file
    utils.stashScriptedParamScripts(config.preloads.plainStageName, config.settings)

    return config
}

def parseUrl(url) {
    def ret = []

    // separate url and path, ssh://psp.sdlc.rd.realtek.com:29418/test/test ->
    // ret[0] ssh://psp.sdlc.rd.realtek.com:29418
    // ret[1] test/test
    def tokens = url.split("//")
    if (tokens.size() == 1) {
        // git@github.com:reyzheng/test.git
        tokens = url.split(":")
        ret << tokens[0]
        ret << tokens[1]
    }
    else {
        def protocol = tokens[0] // https: or ssh:
        def addr = tokens[1].substring(0, tokens[1].indexOf('/')) // psp.sdlc.rd.realtek.com:29418
        def path = tokens[1].substring(tokens[1].indexOf('/') + 1 , tokens[1].length()) // test/test        
        ret << "${protocol}//${addr}"
        ret << path
    }

    return ret
}

def scm_checkout(pipelineAsCode, vars, i) {
    def scmMain = vars.scm_main

    unstash name: "stash-script-utils"
    def utils = load "utils.groovy"
    def url = utils.captureStdout("echo ${vars.scm_urls[i]}", isUnix())
    vars.scm_urls[i] = url[0]

    echo "checkout repository ${vars.scm_types[i]} ${vars.scm_urls[i]}"
    if (vars.scm_types[i] == "git") {
        if (vars.scm_branchs[i] == "") {
            if (vars.scm_refspecs[i] == "") {
                vars.scm_branchs[i] = "master"
            }
            else {
                vars.scm_branchs[i] = "FETCH_HEAD" 
            }
        }

        def gitConfigs = [
            display_name: "",
            enabled: true,
            url: "",
            branch: "master",
            dst: "",
            credentials: "",
            refspecs: "",
            clone_depth: 0,
            submodules: false,
            preserve: false
        ]

        gitConfigs.dst = vars.scm_dsts[i]
        gitConfigs.preserve = pipelineAsCode.global_vars.preserve_source
        gitConfigs.url = vars.scm_urls[i]
        gitConfigs.branch = vars.scm_branchs[i]
        gitConfigs.credentials = vars.scm_credentials[i]
        if (gitConfigs.credentials == "") {
            try {
                gitConfigs.credentials = pipelineAsCode.global_vars.gerrit_credentials
            }
            catch(e) {
            }
        }
        // later added vars
        if (vars.scm_refspecs[i]) {
            gitConfigs.refspecs = vars.scm_refspecs[i]
        }
        if (vars.scm_git_recursivesubmodules[i]) {
            gitConfigs.submodules = vars.scm_git_recursivesubmodules[i]
        }
        if (vars.scm_git_clone_depth[i]) {
            gitConfigs.clone_depth = vars.scm_git_clone_depth[i]
        }
        def action = utils.loadAction("git")
        action.func(pipelineAsCode, gitConfigs, null)

        // get revision number for URF
        def revision
        dir (vars.scm_dsts[i]) {
            if (isUnix() == true) {
                revision = sh(script: "git rev-parse HEAD", returnStdout: true).trim()
            }
            else {
                def stdout = bat(script: "git rev-parse HEAD", returnStdout: true).trim()
                revision = stdout.readLines().drop(1).join(" ")       
            }
        }

        def saveIdx, scmIdx
        if (scmMain == -1) {
            // save rev info
            saveIdx = i
            scmIdx = i
        }
        else if (scmMain == i) {
            // save rev info for this src only
            saveIdx = 0
            scmIdx = i
        }
        else {
            // skip
            return
        }

        if (pipelineAsCode.srcRevisions.containsKey(saveIdx) == false) {
            def urlTokens = parseUrl(gitConfigs.url)
            pipelineAsCode.srcRevisions."${saveIdx}".addr = urlTokens[0]
            pipelineAsCode.srcRevisions."${saveIdx}".name = urlTokens[1]
            pipelineAsCode.srcRevisions."${saveIdx}".path = vars.scm_dsts[scmIdx]
            pipelineAsCode.srcRevisions."${saveIdx}".revision = revision
            pipelineAsCode.srcRevisions."${saveIdx}".upstream = gitConfigs.branch
            print "Got repo info ${saveIdx}: " + pipelineAsCode.srcRevisions."${saveIdx}"
        }
    }
    else if (vars.scm_types[i] == "repo") {
        if (vars.scm_branchs[i] == "") {
            vars.scm_branchs[i] = "master" 
        }

        def repoPath = vars.repo_path
        def repoGroup = ""
        try {
            repoGroup = vars.scm_repo_manifest_goups[i]
        }
        catch(e) {
            // scm_repo_manifest_goups not configured
        }
        def repoConfig = [:]
        def repoMirror = ""
        repoConfig.repo_path = repoPath
        repoConfig.scm_credentials = vars.scm_credentials[i]
        repoConfig.scm_repo_manifest_platforms = vars.scm_repo_manifest_platforms[i]
        repoConfig.scm_branchs = vars.scm_branchs[i]
        repoConfig.scm_repo_manifest_files = vars.scm_repo_manifest_files[i]
        repoConfig.scm_urls = vars.scm_urls[i]
        repoConfig.scm_repo_manifest_notags = vars.scm_repo_manifest_notags[i]
        repoConfig.scm_repo_manifest_currentbranchs = vars.scm_repo_manifest_currentbranchs[i]
        repoConfig.scm_repo_manifest_depths = vars.scm_repo_manifest_depths[i]
        repoConfig.scm_repo_manifest_groups = repoGroup
        try {
            repoConfig.scm_repo_manifest_groups = vars.scm_repo_manifest_groups[i]
        }
        catch (e) {
            // scm_repo_manifest_groups not defined
        }
        try {
            repoConfig.scm_repo_reference = vars.scm_repo_reference[i]
        }
        catch (e) {
            // scm_repo_reference not defined
        }
        try {
            repoMirror = vars.scm_repo_mirror[i]
        }
        catch (e) {
            // scm_repo_mirror not defined
        }
        repoConfig.scm_repo_mirror = repoMirror
        repoConfig.scm_dst = vars.scm_dsts[i]
        repoConfig.preserve = pipelineAsCode.global_vars.preserve_source

        def action = utils.loadAction("repo")
        action.call(repoConfig)
        if (scmMain == -1 || scmMain == i) {
            // save rev info
            if (isUnix() == true && pipelineAsCode.srcRevisions.manifest == null && repoConfig.scm_repo_mirror == "") {
                // repo manifest is only available under non-mirror mode
                dir (repoConfig.scm_dst) {
                    pipelineAsCode.srcRevisions.manifest = sh(script: "${repoPath} manifest -r", returnStdout: true).trim()
                }
                print "Got repo info(manifest): " + pipelineAsCode.srcRevisions.manifest
            }
        }
        else {
            // skip
            return
        }
    }
    else {
        echo "skip scm_checkout"
    }
}

def func(pipelineAsCode, stageConfigsRaw, stagePreloads) {
    unstash name: "stash-script-utils"
    def utils = load "utils.groovy"

    print "Running on " + env.NODE_NAME
    if (stageConfigsRaw.enabled == false) {
        return
    }
    def stageConfigs = [:]
    utils.unstashScriptedParamScripts(stagePreloads.plainStageName, stageConfigsRaw, stageConfigs)
    for (def i=0; i<stageConfigs.scm_counts; i++) {
        // skip, if empty url
        if (stageConfigs.scm_urls[i] == "") {
            return 
        }

        scm_checkout(pipelineAsCode, stageConfigs, i)
    }
}

return this
