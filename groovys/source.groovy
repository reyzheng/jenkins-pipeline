def init(stageName) {
    def defaultConfigs = [
        enabled: true,
        repo_path: "repo",
        display_name: "",
        scm_counts: 1,
        scm_types: ["git"],
        scm_urls: [""],
        scm_branchs: ["master"],
        scm_dsts: [""],
        scm_credentials: [""],
        scm_refspecs: [""],
        scm_git_clone_depth: [0],
        scm_git_recursivesubmodules: [false],
        scm_git_honor_refspec: [false],
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
    dir("groovys") {
        stash name: "stash-actions-git", includes: "git.groovy"
        stash name: "stash-actions-repo", includes: "repo.groovy"
    }
    dir("pipeline_scripts") {
        stash name: "git-checkout-parent", includes: "git-checkout-parent.sh"
        stash name: "git-label-submodules", includes: "git-label-submodules.sh"
    }

    // stash scripted params' script file
    utils.stashScriptedParamScripts(config.preloads.plainStageName, config.settings)

    if (env.PF_MAIN_SOURCE_NAME) {
        env.PF_MAIN_SOURCE_NAME += ",${stageName}"
        env.PF_MAIN_SOURCE_PLAINNAME += ",${config.preloads.plainStageName}"
    }
    else {
        env.PF_MAIN_SOURCE_NAME = stageName
        env.PF_MAIN_SOURCE_PLAINNAME = config.preloads.plainStageName
    }

    return config
}


def scm_checkout(vars, i) {
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
            honor_refspec: false,
            clone_depth: 0,
            submodules: false,
            preserve: false
        ]

        gitConfigs.dst = vars.scm_dsts[i]
        gitConfigs.preserve = env.PF_PRESERVE_SOURCE
        gitConfigs.url = vars.scm_urls[i]
        gitConfigs.branch = vars.scm_branchs[i]
        gitConfigs.credentials = vars.scm_credentials[i]
        if (gitConfigs.credentials == "") {
            if (env.PF_GERRIT_CREDENTIALS) {
                gitConfigs.credentials = env.PF_GERRIT_CREDENTIALS
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
        if (vars.scm_git_honor_refspec[i]) {
            gitConfigs.honor_refspec = vars.scm_git_honor_refspec[i]
        }
        def varname
        if (env.BUILD_BRANCH) {
            varname = "${env.BUILD_BRANCH}_SOURCE_DIR${i}"
        }
        else {
            varname = "SOURCE_DIR${i}"
        }
        env."${varname}" = "${WORKSPACE}/${gitConfigs.dst}"
        dir ('.pf-source') {
            writeJSON file: '.pf-gitconfig', json: gitConfigs
            if (env.BUILD_BRANCH) {
                stash name: "stash-git-config-${env.BUILD_BRANCH}", includes: ".pf-gitconfig"
            }
            else {
                stash name: "stash-git-config", includes: ".pf-gitconfig"
            }
        }
        def action = utils.loadAction("git")
        action.func("git")

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

        // revision info for URF SBOM
        if (env.PF_SOURCE_REVISION) {
            dir (".pf-source") {
                def jsonGitInfo
                try {
                    jsonGitInfo = readJSON file: '.pf-revision-info'
                }
                catch (e) {
                    jsonGitInfo = [:]
                    jsonGitInfo.sources = []
                }
                def jsonSource = [:]
                def urlTokens = utils.parseUrl(gitConfigs.url)
                jsonSource.addr = urlTokens[0].toString()
                jsonSource.name = urlTokens[1].toString()
                jsonSource.path = vars.scm_dsts[i]
                jsonSource.revision = revision
                jsonSource.upstream = gitConfigs.branch
                print "Got repo info(git): " + jsonSource
                jsonGitInfo.sources << jsonSource

                writeJSON file: '.pf-revision-info', json: jsonGitInfo
                def stashName = 'pf-revision-info'
                if (env.BUILD_BRANCH) {
                    stashName += "-${env.BUILD_BRANCH}"
                }
                stash name: stashName, includes: '.pf-revision-info'
            }
        }
    }
    else if (vars.scm_types[i] == "repo") {
        if (vars.scm_branchs[i] == "") {
            vars.scm_branchs[i] = "master" 
        }

        def repoPath = vars.repo_path
        def repoGroup = ""
        try {
            repoGroup = vars.scm_repo_manifest_groups[i]
        }
        catch(e) {
            // scm_repo_manifest_groups not configured
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
        repoConfig.preserve = env.PF_PRESERVE_SOURCE

        def action = utils.loadAction("repo")
        action.call(repoConfig)

        // revision info for URF SBOM
        if (env.PF_SOURCE_REVISION) {
            if (isUnix() == true && repoConfig.scm_repo_mirror == "") {
                // repo manifest is only available under non-mirror mode
                def manifest
                dir (repoConfig.scm_dst) {
                    manifest = sh(script: "${repoPath} manifest -r", returnStdout: true).trim()
                }
                dir (".pf-source") {
                    writeFile file: '.pf-revision-info', text: manifest
                    def  stashName = 'pf-revision-info'
                    if (env.BUILD_BRANCH) {
                        stashName += "-${env.BUILD_BRANCH}"
                    }
                    stash name: stashName, includes: '.pf-revision-info'
                    print "Got repo info(manifest): ${manifest}"
                }
            }
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
    dir (".pf-source") {
        print "source: clean .pf-source"
        deleteDir()
    }
    def stageConfigs = [:]
    utils.unstashScriptedParamScripts(stagePreloads.plainStageName, stageConfigsRaw, stageConfigs)
    for (def i=0; i<stageConfigs.scm_counts; i++) {
        // skip, if empty url
        if (stageConfigs.scm_urls[i] == "") {
            return 
        }

        env."PF_SOURCE_DST_${i}" = ""
        if (stageConfigs.scm_dsts.size() > i) {
            env."PF_SOURCE_DST_${i}" = stageConfigs.scm_dsts[i]
        }
        scm_checkout(stageConfigs, i)
    }
}

return this
