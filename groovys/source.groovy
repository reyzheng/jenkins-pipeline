def init(stageName) {
    def defaultConfigs = [
        enabled: true,
        repo_path: "repo",
        display_name: "",
        export_diff_result: false,
        scm_counts: 1,
        scm_types: ["git"],
        scm_urls: [""],
        scm_branchs: ["master"],
        scm_dsts: [""],
        scm_credentials: [""],
        scm_refspecs: [""],
        scm_git_clone_depth: [0],
        scm_git_submodules: [false],
        scm_git_recursivesubmodules: [false],
        scm_git_honor_refspec: [false],
        scm_git_reference: [""],
        scm_repo_manifest_files: ["default.xml"],
        scm_repo_manifest_groups: [""],
        scm_repo_manifest_currentbranchs: [true],
        scm_repo_manifest_notags: [true],
        scm_repo_manifest_depths: [1],
        scm_repo_manifest_platforms: ["linux"],
        scm_repo_reference: [""],
        scm_repo_mirror: [""]
    ]

    def config = utils.commonInit(stageName, defaultConfigs)
    for (def i=0; i<config.scm_counts; i++) {
        def scmDst = config.scm_dsts[i]
        if (env.PF_SOURCE_DSTS) {
            env.PF_SOURCE_DSTS += ",${scmDst}"
        }
        else {
            env.PF_SOURCE_DSTS = scmDst
        }
    }
    utils.finalizeInit(stageName, config)

    return config
}

def scm_checkout(vars, i) {
    echo "checkout repository ${vars.scm_types[i]} ${vars.scm_urls[i]}"

    //if (env.PF_BUILD_ENV.startsWith("slurm:")) {
    if (1 == 2) {
        // TODO: slurm on-going
        utils.pyExec(vars["actionName"], vars["stageName"], "CHECK_OUT", ['-i', i])
    }
    else {
        def plainStageName = vars["plainStageName"]
        def scmConfigs
        dir (".pf-${plainStageName}") {
            scmConfigs = readJSON file: "source-${i}-config.json"
        }
        if (vars.scm_types[i] == "git") {
            def action = utils.loadCoreAction(env.PF_ROOT, "git")
            action.func(scmConfigs)
        }
        else if (vars.scm_types[i] == "repo") {
            def action = utils.loadCoreAction(env.PF_ROOT, "repo")
            action.call(scmConfigs, vars["plainStageName"])
        }
        else if (vars.scm_types[i] == "svn") {
            checkout([
                $class: 'SubversionSCM',
                additionalCredentials: [],
                excludedCommitMessages: '',
                excludedRegions: '',
                excludedRevprop: '',
                excludedUsers: '',
                filterChangelog: false,
                ignoreDirPropChanges: false,
                includedRegions: '',
                locations: [[
                    cancelProcessOnExternalsFail: true,
                    credentialsId: vars.scm_credentials[i],
                    depthOption: 'infinity',
                    ignoreExternalsOption: true,
                    local: vars.scm_dsts[i],
                    remote: vars.scm_urls[i]
                ]],
                quietOperation: false,
                workspaceUpdater: [$class: 'UpdateUpdater']
            ])
        }
        else {
            echo "skip scm_checkout"
        }
    }

    utils.pyExec(vars["actionName"], vars["stageName"], "REVISION_INFO", ['-i', i])
    if (vars["export_diff_result"] == true) {
        // calculate diff files
        utils.pyExec(vars["actionName"], vars["stageName"], "DIFF_FILES", ['-i', i])
    }
}

def func(stageName) {
    def stageConfigs = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"
    def plainStageName = stageConfigs["plainStageName"]

    print "Running on " + env.NODE_NAME
    if (stageConfigs["enabled"] == false) {
        return
    }
    utils.pyExec(stageConfigs["actionName"], stageConfigs["stageName"], "TRANSLATE_CONFIG", [])
    stageConfigs = readJSON file: ".pf-all/settings/${stageName}_config.json"
    utils.pyExec(stageConfigs["actionName"], stageConfigs["stageName"], "INIT_WORKDIR", [])
    utils.pyExec(stageConfigs["actionName"], stageConfigs["stageName"], "PARSE_CONFIG", [])
    for (def i=0; i<stageConfigs["scm_counts"]; i++) {
        // skip, if empty url
        if (stageConfigs["scm_urls"][i] == "") {
            return 
        }
        scm_checkout(stageConfigs, i)
    }
    utils.pyExec(stageConfigs["actionName"], stageConfigs["stageName"], "SAVE_ENV", [])

    utils.exportEnvVar("PF_SOURCE_WORKDIR", ".pf-${plainStageName}")
    dir (".pf-${plainStageName}") {
        def stashName = 'pf-revision-info'
        if (env.BUILD_BRANCH) {
            stashName += "-${env.BUILD_BRANCH}"
        }
        stash name: stashName, includes: '.pf-revision-info'
        utils.exportEnv()
    }
}

return this
