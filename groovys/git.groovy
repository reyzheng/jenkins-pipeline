
def func(configs) {
    def utils = load "${PF_ROOT}/utils.groovy"
    def underUnix = isUnix()
    // manual
    def localBranch = configs["branch"]
    if (configs["branch"] == 'FETCH_HEAD') {
        localBranch = 'PFtest-branch'
    }

    dir (configs["dst"]) {
        print("git: WORKSPACE " + WORKSPACE)
        print("git: pwd " + pwd())
        if (WORKSPACE != pwd()) {
            if (configs["preserve"] == false || configs["preserve"] == 'false') {
                print "git: clean source"
                deleteDir()
            }
            else {
                print "git: preserve source"
                if (underUnix) {
                    sh "pwd && ls -al"
                }
                else {
                    bat "dir"
                }
                if (configs["branch"] != "" && configs["branch"] != "FETCH_HEAD") {
                    try {
                        utils.inlineScript("git branch -D ${configs['branch']}", underUnix, "")
                    }
                    catch (e) {
                    }
                }
            }
        }

        def shallowClone = false
        if (configs["clone_depth"] > 0) {
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
                        depth: configs["clone_depth"],
                        shallow: shallowClone,
                        timeout: 60,
                        reference: configs["clone_reference"],
                        honorRefspec: configs["honor_refspec"]]], 
                userRemoteConfigs: [[
                    url: "${configs.url}", 
                    refspec: "${configs.refspecs}",
                    credentialsId: "${configs.credentials}"]], 
                branches: [[name: "${configs.branch}"]]
            ], poll: true)
        }
        else {
            try {
                def gitExists = fileExists '.git'
                if (gitExists == true) {
                    if (underUnix) {
                        sh "git config fetch.recurseSubmodules no"
                    }
                    else {
                        bat "git config fetch.recurseSubmodules no"
                    }
                }
            }
            catch (e) {}
            checkout(scm: [$class: 'GitSCM', 
                extensions: [
                    [$class: 'LocalBranch', 
                        localBranch: localBranch],
                    [$class: 'SubmoduleOption', 
                        disableSubmodules: true],
                    [$class: 'CloneOption',
                        depth: configs.clone_depth,
                        shallow: shallowClone,
                        timeout: 60,
                        reference: configs["clone_reference"],
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
            unstashPipelineFramework()
        }

        try {
            //if (env.PF_SOURCE_REVISION && localBranch == "PFtest-branch") {
            if (localBranch == "PFtest-branch") {
                // set upstream for URF SBOM generation
                if (underUnix) {
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

return this
