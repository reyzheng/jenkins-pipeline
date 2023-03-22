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
    dir ('.pf-composition') {
        writeJSON file: 'temporal.json', json: config.settings
        stash name: "pf-${stageName}-config", includes: 'temporal.json'
    }

    return null
}

def func(pipelineAsCode, configs, preloads) {
}

return this
