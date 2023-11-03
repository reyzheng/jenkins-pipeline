def init(stageName) {
    def defaultConfig = [
        scm_dst: "",
        repo_path: "repo",
        scm_credentials: "",
        scm_urls: "",
        scm_branchs: "master",
        scm_repo_mirror: "",
        scm_repo_reference: "",
        scm_repo_manifest_files: "default.xml",
        scm_repo_manifest_platforms: "linux",
        scm_repo_manifest_groups: "",
        scm_repo_manifest_notags: true,
        scm_repo_manifest_currentbranchs: true,
        scm_repo_manifest_depths: 1,

        // hidden parameters
        preserve: false
    ]

    def utils = load "utils.groovy"
    def config = utils.commonInit(stageName, defaultConfig)

    return config
}

def call(Map repoConfig = [:], plainStageName) {
    // TODO: duplicated def defaultConfig
    def defaultConfig = [
        scm_dst: "",
        repo_path: "repo",
        scm_credentials: "",
        scm_urls: "",
        scm_branchs: "master",
        scm_repo_mirror: "",
        scm_repo_reference: "",
        scm_repo_manifest_files: "default.xml",
        scm_repo_manifest_platforms: "linux",
        scm_repo_manifest_groups: "",
        scm_repo_manifest_notags: true,
        scm_repo_manifest_currentbranchs: true,
        scm_repo_manifest_depths: 1,

        // hidden parameters
        preserve: false
    ]
    defaultConfig << repoConfig

    def dst = defaultConfig["scm_dst"]
    if (defaultConfig.scm_repo_mirror != "") {
        // scm_repo_mirror has higher priority
        dst = defaultConfig.scm_repo_mirror
    }

    dir (dst) {
        if (dst != "") {
            if (defaultConfig["preserve"] == false || defaultConfig["preserve"] == "false") {
                print "repo: clean source"
                deleteDir()
            }
        }
        if (defaultConfig.scm_credentials != "" || defaultConfig.scm_repo_mirror != "") {
            // Credentials, --mirror is invalid in Jenkins REPO plugin
            //def repoCommand = defaultConfig.repo_path
            dir (".repo-tool") {
                deleteDir()
                sh """
                    git clone https://mirror.rtkbf.com/gerrit/repo -b stable .
                """
            }
            def repoCommand = ".repo-tool/repo"
            def repoInitParams = ""
            def repoSyncParams = ""
            if (defaultConfig.scm_branchs.trim() == "") {
                defaultConfig.scm_branchs = "master"
            }
            repoInitParams += "-b ${defaultConfig.scm_branchs} "
            if (defaultConfig.scm_repo_manifest_files.trim() == "") {
                defaultConfig.scm_repo_manifest_files = "default.xml"
            }
            repoInitParams += "-m ${defaultConfig.scm_repo_manifest_files} "
            if (defaultConfig.scm_repo_manifest_platforms.trim() != "") {
                repoInitParams += "-p ${defaultConfig.scm_repo_manifest_platforms} "
            }
            if (defaultConfig.scm_repo_manifest_groups.trim() != "") {
                repoInitParams += "-g ${defaultConfig.scm_repo_manifest_groups} "
            }
            if (defaultConfig.scm_repo_reference.trim() != "") {
                repoInitParams += "--reference ${defaultConfig.scm_repo_reference} "
            }
            if (defaultConfig.scm_repo_mirror.trim() != "") {
                repoInitParams += "--mirror "
            }
            else {
                // --no-tags, --current-branch, --depth is only valid without mirror
                if (defaultConfig.scm_repo_manifest_notags == true) {
                    repoInitParams += "--no-tags "
                    repoSyncParams += "--no-tags "
                }
                if (defaultConfig.scm_repo_manifest_currentbranchs == true) {
                    repoInitParams += "--current-branch "
                    repoSyncParams += "--current-branch "
                }
                repoInitParams += "--depth=${defaultConfig.scm_repo_manifest_depths} "
            }
            sshagent(credentials: [defaultConfig.scm_credentials]) {
                // Sample
                // ssh -p 29418 $REPO_USER@psp.sdlc.rd.realtek.com gerrit version
                def repoExists = fileExists '.repo'
                if (defaultConfig.scm_repo_mirror.trim() != "" && repoExists == true) {
                    // sync only if mirror mode and .repo exists
                    sh """
                        ${repoCommand} sync -d --force-sync --jobs=4 ${repoSyncParams}
                    """
                }
                else {
                    sh """
                        echo 'current directory'
                        pwd && ls -a
                        ${repoCommand} init -u ${defaultConfig.scm_urls} ${repoInitParams}
                        ${repoCommand} sync -d --force-sync --jobs=4 ${repoSyncParams}
                    """
                }
            }
        }
        else {
            checkout([$class: 'RepoScm',
                    forceSync: true, 
                    jobs: 4, 
                    manifestPlatform: defaultConfig.scm_repo_manifest_platforms,
                    manifestBranch: defaultConfig.scm_branchs,
                    manifestFile: defaultConfig.scm_repo_manifest_files, 
                    mirrorDir: defaultConfig.scm_repo_reference, 
                    manifestGroup: defaultConfig.scm_repo_manifest_groups,
                    manifestRepositoryUrl: defaultConfig.scm_urls,
                    quiet: false,
                    noTags: defaultConfig.scm_repo_manifest_notags,
                    currentBranch: defaultConfig.scm_repo_manifest_currentbranchs,
                    depth: defaultConfig.scm_repo_manifest_depths])
        }
    }
    // sync GERRIT_REFSPEC if GERRIT_EVENT_TYPE == 'patchset-created'
    def pythonExec = utils.getPython()
    def pyCmd = "${pythonExec} .pf-all/pipeline_scripts/repo.py -c REPO_SYNC_REFSPEC -w .pf-${plainStageName}"
    if (dst != "") {
        pyCmd += " -d ${dst}"
    }
    if (isUnix()) {
        sh pyCmd
    }
    else {
        bat pyCmd
    }
}

def func(pipelineAsCode, stageConfigs, stagePreloads) {
    call(stageConfigs)
}

return this
