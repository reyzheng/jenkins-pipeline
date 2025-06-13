def init(stageName) {
    def defaultConfigs = [
        stages: [],
        short_workspace: false,
        run_type: "SEQUENTIAL",
        parallel_parameters: [:],
        parallel_excludes: [],
        node: ""
    ]

    def config = utils.commonInit(stageName, defaultConfigs)
    if (config["short_workspace"] == true) {
        env.PF_SHORT_WORKSPACE = "1"
    }
    utils.finalizeInit(stageName, config)

    return null
}

def func(stageName) {
}

return this
