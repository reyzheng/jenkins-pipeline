def init(stageName) {
    def defaultConfigs = [
        stages: [],
        run_type: "SEQUENTIAL",
        parallel_parameters: [:],
        parallel_excludes: [],
        node: ""
    ]

    def utils = load "utils.groovy"
    def config = utils.commonInit(stageName, defaultConfigs)
    config.settings.parallel_parameters = utils.extractParallelParameters(config.settings.parallel_parameters)
    config.settings.parallel_excludes = utils.extractParameters(config.settings.parallel_excludes)

    return config
}

def func(pipelineAsCode, configs, preloads) {
}

return this
