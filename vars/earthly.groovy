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

    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)

    return config
}

//def func(pipelineAsCode, configsRaw, preloads) {
def func(stageName) {
    if (isUnix() == false) {
        print "Only available under linux"
        return
    }
    def pythonExec = utils.getPython()
    def translateCmd = "${pythonExec} ${env.PF_ROOT}/pipeline_scripts/utils.py -f ${env.PF_ROOT}/settings/${stageName}_config.json -c TRANSLATE_CONFIG"
    if (isUnix()) {
        sh translateCmd
    }
    else {
        bat translateCmd
    }
    def configs = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"

    print "Build earthly image and run"
    sh """
        randompass=`cat /dev/urandom | tr -dc A-Za-z0-9 | head -c 8`
        echo "random password \${randompass}"
        sed -i \"s/    RUN echo.*/    RUN echo 'root:\${randompass}' | chpasswd/g\" ${env.PF_ROOT}/scripts/Earthfile
        sed -i \"s/    SAVE IMAGE.*/    SAVE IMAGE ${configs.container_name}:latest/g\" ${env.PF_ROOT}/scripts/Earthfile
        #earthly .pf-earthly+docker
        earthly +docker
        timeout 600 docker run -p 2222:22 --rm earthly-debug
    """
}

return this