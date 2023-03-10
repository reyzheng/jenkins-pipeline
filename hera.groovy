def start(URL, BRANCH, CREDENTIALS) {
    def pipelineAsCode
    dir(".pf-settings") {
        checkout([
            $class: 'GitSCM',
            branches: [[name: "*/${BRANCH}"]],
            extensions: [[
                $class: 'CloneOption',
                shallow: true,
                depth:   1,
                timeout: 30
            ]],
            userRemoteConfigs: [[
                url: URL,
                credentialsId: CREDENTIALS
            ]]
        ])
        if (isUnix() == true) {
            sh 'cp -a * ../.pf-bringup'
        }
        else {
            bat "xcopy .pf-settings\\* .\\.pf-bringup /E /H /Y"
        }
    }
    // change to nodes user specified
    def jsonObj
    def nodeName = ""
    dir('.pf-bringup') {
        dir('settings') {
            jsonObj = readJSON file: 'global_config.json'
        }
        if (jsonObj.nodes.size() > 0 && jsonObj.nodes[0] != "") {
            nodeName = jsonObj.nodes[0]
        }
        pipelineAsCode = load('rtk_stages.groovy')
        print "Bring to node: ${nodeName}"
        stash name: "pf-basics", includes: "**"
    }
    sh """
        echo test1
        pwd && ls -al
    """
    
    node(nodeName) {
        unstash name: "pf-basics"
        pipelineAsCode.format(jsonObj.stages)
        load 'Jenkinsfile.restartable'
    }
}

return this
