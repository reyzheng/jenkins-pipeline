def init(stageName) {
    def utils = load "utils.groovy"
    def actionName = utils.extractActionName(stageName)

    def defaultConfigs = [
        display_name: "",
        enable: true,
        sshsign_credential: "",
        sshsign_authcode: "",
        sshsign_sha: "",
        sshsign_hex: ""
    ]
    def config = utils.commonInit(stageName, defaultConfigs)

    return config
}

def func(pipelineAsCode, config, preloads) {
    def dstFile = "sshsigned"
    def buildBranch = null
    if (env.BUILD_BRANCH) {
        dstFile = dstFile + "-" + env.BUILD_BRANCH
    }

    if (config.enable == false) {
        print "Skip stage ${preloads.stageName}"
        return
    }

    withCredentials([string(credentialsId: config.sshsign_authcode, variable: 'AUTH_CODE')]) {
        for (def ite=0; ite<config.sshsign_sha.size(); ite++) {
            dstFile = dstFile + "-${ite}"
            def hexData = readFile file: config.sshsign_hex[ite]
            def body
            dir(".sshsign") {
                def hsmPureSignParameter = [:]
                hsmPureSignParameter.keyName = config.sshsign_sha[ite]
                hsmPureSignParameter.hexData = hexData.trim()
                hsmPureSignParameter.authCode = AUTH_CODE
                writeJSON file: "body.json", json: hsmPureSignParameter
                body = readFile "body.json"
                deleteDir()
            }
            def response = httpRequest httpMode: 'POST',
                            contentType: 'APPLICATION_JSON',
                            authentication: config.sshsign_credential, 
                            requestBody: body,
                            url: 'https://certsign.realtek.com/api/SignAPI/HSMPureSign', 
                            ignoreSslErrors: true
            if (response.status == 200) {
                def responseObject = readJSON text: response.content
                writeFile file: dstFile, text: responseObject.data.signature
                archiveArtifacts artifacts: dstFile
            }
        }
    }
}

return this
