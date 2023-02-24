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

        // hidden parameters
        preserve: false
    ]

    def utils = load "utils.groovy"
    def config = utils.commonInit(stageName, defaultConfigs)

    return config
}

def func(pipelineAsCode, configs, preloads) {
    if (configs.enabled == true) {
        dir (configs.dst) {
            if (configs.preserve == false) {
                deleteDir()
            }

            def shallowClone = false
            if (configs.clone_depth > 0) {
                shallowClone = true
            }

            // set "LocalBranch" for URF SBOM generation
            if (configs.submodules == true) {
                checkout(scm: [$class: 'GitSCM', 
                    doGenerateSubmoduleConfigurations: false, 
                    extensions: [
                        [$class: 'LocalBranch', 
                            localBranch: ""],
                        [$class: 'SubmoduleOption', 
                            disableSubmodules: false, 
                            parentCredentials: true, 
                            recursiveSubmodules: true, 
                            reference: '', 
                            trackingSubmodules: false],
                        [$class: 'CloneOption',
                            depth: configs.clone_depth,
                            shallow: shallowClone,
                            honorRefspec: true]], 
                    userRemoteConfigs: [[
                        url: "${configs.url}", 
                        refspec: "${configs.refspecs}",
                        credentialsId: "${configs.credentials}"]], 
                    branches: [[name: "${configs.branch}"]]
                ])
            }
            else {
                checkout(scm: [$class: 'GitSCM', 
                    extensions: [
                        [$class: 'LocalBranch', 
                            localBranch: ""],
                        [$class: 'SubmoduleOption', 
                            disableSubmodules: true],
                        [$class: 'CloneOption',
                            depth: configs.clone_depth,
                            shallow: shallowClone,
                            honorRefspec: true]],
                    userRemoteConfigs: [[
                        url: "${configs.url}", 
                        refspec: "${configs.refspecs}",
                        credentialsId: "${configs.credentials}"]], 
                    branches: [[name: "${configs.branch}"]]
                ])
            }
            try {
                // set upstream for URF SBOM generation
                if (isUnix()) {
                    sh """
                        git branch --set-upstream-to=origin/${configs.branch} ${configs.branch}
                    """
                }
                else {
                    bat """
                        git branch --set-upstream-to=origin/${configs.branch} ${configs.branch}
                    """
                }
            }
            catch (e) {
            }
        }
    }
}

return this