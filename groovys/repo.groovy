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

def cliRepo(defaultConfig, repoCommand, repoUser, repoKey, repoInitParams, repoSyncParams, underUnix) {
    // Sample
    // ssh -p 29418 $REPO_USER@psp.sdlc.rd.realtek.com gerrit version
    def repoExists = fileExists '.repo'
    def gitSSHCommand = ''
    if (repoUser != '') {
        if (underUnix) {
            gitSSHCommand = "GIT_SSH_COMMAND=\"ssh -l ${repoUser} -i ${repoKey}\" "
        }
        else {
            gitSSHCommand = "set GIT_SSH_COMMAND=ssh -l ${repoUser} -i ${repoKey}&&"
        }
    }
    if (defaultConfig.scm_repo_mirror.trim() != "" && repoExists == true) {
        // sync only if mirror mode and .repo exists
        def cmd = "${gitSSHCommand}${repoCommand} sync -d --force-sync --jobs=4 ${repoSyncParams}"
        utils.inlineScript(cmd, underUnix, "")
    }
    else {
        def cmd
        cmd = "${gitSSHCommand}${repoCommand} init -u ${defaultConfig.scm_urls} ${repoInitParams}"
        utils.inlineScript(cmd, underUnix, "")
        cmd = "${gitSSHCommand}${repoCommand} sync -v -d --force-sync --jobs=4 ${repoSyncParams}"
        //env.GIT_SSH_COMMAND = gitSSHCommand
        //cmd = "${repoCommand} sync -v -d --force-sync --jobs=4 ${repoSyncParams}"
        utils.inlineScript(cmd, underUnix, "")
    }
}

def call(defaultConfig, plainStageName) {
    def dst = defaultConfig["scm_dst"]
    if (defaultConfig.scm_repo_mirror != "") {
        // scm_repo_mirror has higher priority
        dst = defaultConfig.scm_repo_mirror
    }

    def underUnix = isUnix()
    dir (dst) {
        print("repo: WORKSPACE " + WORKSPACE)
        print("repo: pwd " + pwd())
        if (WORKSPACE != pwd()) {
        //if (dst != "") {
            if (defaultConfig["preserve"] == false || defaultConfig["preserve"] == "false") {
                print "repo: clean source"
                deleteDir()
            }
            else {
                print "repo: preserve source"
                if (underUnix) {
                    sh "pwd && ls -al"
                }
                else {
                    bat "dir"
                }
            }
        }

        def repoCLI = false
        // REPO plugin is not supported on windows (ctcsoc-win01, ctcsoc-win01-mingw tested)
        if (defaultConfig["scm_credentials"] != "" \
                || defaultConfig["scm_repo_mirror"] != "" \
                || defaultConfig["repo_path"] != "repo" \
                || underUnix == false) {
            repoCLI = true
        }
        if (repoCLI == true) {
            // Credentials, --mirror is invalid in Jenkins REPO plugin
            def repoCommand = defaultConfig["repo_path"]
            if (defaultConfig["repo_path"] == "repo" && underUnix) {
                dir (".repo-tool") {
                    deleteDir()
                    sh "GIT_SSL_NO_VERIFY=true git clone https://mirror.rtkbf.com/gerrit/repo -b stable ."
                    repoCommand = ".repo-tool/repo"
                }
            }
            print "repoCommand: ${repoCommand}"

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

            /*
            if (underUnix == true) {
                sshagent(credentials: [defaultConfig.scm_credentials]) {
                    cliRepo(defaultConfig, repoCommand, repoInitParams, repoSyncParams, underUnix)
                }
            }
            else {
                cliRepo(defaultConfig, repoCommand, repoInitParams, repoSyncParams, underUnix)
            }
            */
            if (defaultConfig["scm_credentials"] != '') {
                withCredentials([sshUserPrivateKey(credentialsId: defaultConfig["scm_credentials"], usernameVariable: "REPO_USER", keyFileVariable: "REPO_KEY")]) {
                    cliRepo(defaultConfig, repoCommand, REPO_USER, REPO_KEY, repoInitParams, repoSyncParams, underUnix)
                }
            }
            else {
                cliRepo(defaultConfig, repoCommand, '', '', repoInitParams, repoSyncParams, underUnix)
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
    if (underUnix == true && defaultConfig.scm_credentials != "") {
        sshagent(credentials: [defaultConfig.scm_credentials]) {
            utils.inlineScript(pyCmd, underUnix, "")
        }
    }
    else {
        utils.inlineScript(pyCmd, underUnix, "")
    }
}

return this