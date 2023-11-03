def init(stageName) {
    def defaultConfigs = [
        display_name: "Earthly",
        dst: "",
        credentials: "",
        archive: false,
        container_name: "earthly-debug",
        files: [],

        scriptableParams: []
    ]

    def utils = load "utils.groovy"
    def config = utils.commonInit(stageName, defaultConfigs)

    dir ('pipeline_scripts') {
        stash name: "stash-script-${config.preloads.plainStageName}", includes: 'Earthfile'
    }

    return config
}

def func(pipelineAsCode, configsRaw, preloads) {
    if (isUnix() == false) {
        print "Only available "
        return
    }

    unstash name: "stash-script-utils"
    def utils = load "utils.groovy"
    def configs = [:]
    utils.unstashScriptedParamScripts(preloads.plainStageName, configsRaw, configs)

    unstash name: "stash-script-${preloads.plainStageName}"
    print "Build earthly image and run"
    sh """
        randompass=`cat /dev/urandom | tr -dc A-Za-z0-9 | head -c 8`
        echo "random password \${randompass}"
        sed -i \"s/    RUN echo.*/    RUN echo 'root:\${randompass}' | chpasswd/g\" Earthfile
        sed -i \"s/    SAVE IMAGE.*/    SAVE IMAGE ${configs.container_name}:latest/g\" Earthfile
        #earthly .pf-earthly+docker
        earthly +docker
        timeout 600 docker run -p 2222:22 --rm earthly-debug
    """
}

return this