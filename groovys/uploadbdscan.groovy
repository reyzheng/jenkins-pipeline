def init(stageName) {
    def defaultConfigs = [
        display_name: "",
        blackduck_url: "https://blackduck.rtkbf.com",
        blackduck_token_credential: "",
        scanfiles: []
    ]

    def utils = load "utils.groovy"
    def config = utils.commonInit(stageName, defaultConfigs)

    return config
}

def func(pipelineAsCode, vars, preloads) {
    dir("uploadbdscan") {
        // get Rest API BearerToken
        def bearerToken
        def curlCommand
        withCredentials([string(credentialsId: vars.blackduck_token_credential, variable: 'TOKEN')]) {
            curlCommand = "curl --insecure -X POST ${vars.blackduck_url}/api/tokens/authenticate -H \"Authorization: token $TOKEN\" -H \"cache-control: no-cache\""
            def jsonBearerToken = sh(script: curlCommand, returnStdout: true)
            def jsonObjBearerToken = readJSON text: jsonBearerToken
            bearerToken = jsonObjBearerToken["bearerToken"]

            for (def i=0; i<vars.scanfiles.size(); i++) {
                def scanFile = vars.scanfiles[i]
                if (scanFile.startsWith("artifacts:")) {
                    scanFile = scanFile.split(":")
                    scanFile = scanFile[1].trim()
                    copyArtifacts filter: scanFile, projectName: env.JOB_NAME, selector: specific(env.BUILD_NUMBER)
                    def bdioFiles = findFiles(glob: '**.bdio')
                    for (def bdioFile in bdioFiles) {
                        curlCommand = "curl --insecure -X POST ${vars.blackduck_url}/api/scan/data -F \"file=@${bdioFile}\" -H \"Authorization: Bearer ${bearerToken}\""
                        sh curlCommand
                    }
                }
                else {
                    curlCommand = "curl --insecure -X POST ${vars.blackduck_url}/api/scan/data -F \"file=@${scanFile}\" -H \"Authorization: Bearer ${bearerToken}\""
                    sh curlCommand
                }
            }
        }

        deleteDir()
    }
}

return this