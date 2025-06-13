def init(stageName) {
    def defaultConfigs = [
        display_name: "upload",
        enabled: true,
        src_files: "",
        dst_dir: ""
    ]
    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)

    return config
}

def func(stageName) {
    def configs = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"

    utils.pyExec(configs["actionName"], configs["stageName"], "", [])
}

return this