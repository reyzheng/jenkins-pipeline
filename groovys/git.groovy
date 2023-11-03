def init(stageName) {
    def defaultConfigs = [
        display_name: "",
        enabled: true,
        url: "",
        branch: "master",
        dst: "",
        credentials: "",
        refspecs: "",
        clone_depth: 0,
        submodules: false,
        recursivesubmodules: false,

        // hidden parameters
        preserve: false
    ]

    def utils = load "utils.groovy"
    def config = utils.commonInit(stageName, defaultConfigs)

    return config
}

//def func(pipelineAsCode, configs, preloads) {
def func(stageName) {
    // manual
    /*
    sshagent(credentials: ["linux-credential"]) {
        def gitExisted = fileExists ".git"
        if (gitExisted == false) {
            sh """
                git init
                git remote remove origin
                git remote add origin ssh://ed@cm2sd6.rtkbf.com:29418/kernel/common
            """
        }
        sh """"
            git pull origin master
            git fetch origin $GERRIT_REFSPEC && git checkout FETCH_HEAD
        """"
    }
    */
    dir ('.pf-source') {
        if (env.BUILD_BRANCH) {
            unstash name: "stash-${stageName}-config-${env.BUILD_BRANCH}"
        }
        else {
            unstash name: "stash-${stageName}-config"
        }
        configs = readJSON file: ".pf-gitconfig"
    }
    //def localBranch = ''
    def localBranch = configs.branch
    if (configs.branch == 'FETCH_HEAD') {
        localBranch = 'PFtest-branch'
    }

    if (configs.enabled == true) {
        dir (configs["dst"]) {
            if (configs["dst"] != "") {
                if (configs.preserve == false || configs.preserve == 'false') {
                    print "git: clean source"
                    deleteDir()
                }
                else {
                    print "git: preserve source"
                    if (isUnix()) {
                        sh "pwd && ls -al"
                    }
                    else {
                        bat "dir"
                    }
                }
            }

            def shallowClone = false
            if (configs.clone_depth > 0) {
                shallowClone = true
            }

            // set "LocalBranch" for URF SBOM generation
            if (configs["submodules"] == true) {
                checkout(scm: [$class: 'GitSCM', 
                    doGenerateSubmoduleConfigurations: false, 
                    extensions: [
                        [$class: 'LocalBranch', 
                            localBranch: localBranch],
                        [$class: 'SubmoduleOption', 
                            disableSubmodules: false, 
                            parentCredentials: true, 
                            recursiveSubmodules: configs["recursivesubmodules"],
                            reference: '', 
                            trackingSubmodules: false],
                        [$class: 'CloneOption',
                            depth: configs.clone_depth,
                            shallow: shallowClone,
                            honorRefspec: configs.honor_refspec]], 
                    userRemoteConfigs: [[
                        url: "${configs.url}", 
                        refspec: "${configs.refspecs}",
                        credentialsId: "${configs.credentials}"]], 
                    branches: [[name: "${configs.branch}"]]
                ], poll: true)
            }
            else {
                checkout(scm: [$class: 'GitSCM', 
                    extensions: [
                        [$class: 'LocalBranch', 
                            localBranch: localBranch],
                        [$class: 'SubmoduleOption', 
                            disableSubmodules: true],
                        [$class: 'CloneOption',
                            depth: configs.clone_depth,
                            shallow: shallowClone,
                            honorRefspec: configs.honor_refspec]],
                    userRemoteConfigs: [[
                        url: "${configs.url}", 
                        refspec: "${configs.refspecs}",
                        credentialsId: "${configs.credentials}"]], 
                    branches: [[name: "${configs.branch}"]]
                ], poll: true)
            }

            if (configs["dst"] == "") {
                // notice: git plugin will clean current folder, recover .pf-all
                utils.unstashPipelineFramework()
            }

            try {
                if (env.PF_SOURCE_REVISION) {
                    // set upstream for URF SBOM generation
                    if (isUnix()) {
                        sh """
                            git branch --set-upstream-to=origin/${configs.branch} ${localBranch}
                        """
                    }
                    else {
                        bat """
                            git branch --set-upstream-to=origin/${configs.branch} ${localBranch}
                        """
                    }
                }
            }
            catch (e) {
            }
        }
    }
}

return this
