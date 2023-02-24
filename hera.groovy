def start() {
    sh """
        pwd && ls -al
    """
    def pipelineAsCode
    def buPipelineCfg = readJSON file: "Jenkinsfile.json"
    dir(".pf-bringup") {
        checkout([
            $class: 'GitSCM',
            branches: [[name: "*/${buPipelineCfg.BRANCH}"]],
            extensions: [[
                $class: 'CloneOption',
                shallow: true,
                depth:   1,
                timeout: 30
            ]],
            userRemoteConfigs: [[
                url:           buPipelineCfg.URL,
                credentialsId: ''
            ]]
        ])

        // change to nodes user specified
        def jsonObj
        dir('settings') {
            jsonObj = readJSON file: 'global_config.json'
        }
        def nodeName = ""
        if (jsonObj.nodes.size() > 0 && jsonObj.nodes[0] != "") {
            nodeName = jsonObj.nodes[0]
        }
        print "Bring to node: ${nodeName}"

        node(nodeName) {
            pipelineAsCode = load('rtk_stages.groovy')
            pipelineAsCode.format(jsonObj.stages)
            load 'Jenkinsfile.restartable'
        }
    }
}

return this
