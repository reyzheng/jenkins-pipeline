import groovy.transform.Field

def init(stageName) {
    def defaultConfigs = [
        display_name: "",
        src_files: "",
        dst_dir: ""
    ]
    def utils = load "utils.groovy"
    def config = utils.commonInit(stageName, defaultConfigs)

    dir(env.PF_PATH + 'scripts') {
        print "Upload: " + config.settings.src_files
        stash name: "stash-${config.preloads.plainStageName}-files", includes: config.settings.src_files
    }

    return config
}

def func(pipelineAsCode, config, preloads) {
    dir(config.dst_dir) {
        unstash "stash-${preloads.plainStageName}-files"
    }
}

return this
