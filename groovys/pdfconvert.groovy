def init(stageName) {
    def defaultConfigs = [
        display_name: "PDFWatermark",
        enable: true,
        username: "",
        files: "",
        dst_dir: ".pdfconvert",
        watermark: "FORMAT_1"
    ]

    def utils = load "utils.groovy"
    def config = utils.commonInit(stageName, defaultConfigs)

    return config
}

def func(pipelineAsCode, vars, preloads) {
    if (vars["enable"] == false) {
        print "skip"
        return
    }

    def watermarkFormat
    if (vars.watermark == "FORMAT_1") {
        watermarkFormat = "-F 'WatermarkColor=#4287F5' \
-F 'WatermarkSize=70' \
-F 'WatermarkText=Realtek' \
-F 'WatermarkBoutlineOnly=true'"
    }
    //def stageName = preloads.stageName
    //def baseUrl = "https://pdfservice.realtek.com/ConvertPDF/PDFService" // online
    def baseUrl = "https://pdfservice1.realtek.com:1147/ConvertPDF/PDFService"  // test

    def filesParameter = vars.files
    if (isUnix() == true) {
        if (filesParameter.startsWith("\$")) {
            filesParameter = sh(script: "echo ${vars.files}", returnStdout: true)
        }
    }
    else {
        if (filesParameter.startsWith("%")) {
            def stdout = bat(script: "echo ${vars.files}", returnStdout: true).trim()
            filesParameter = stdout.readLines().drop(1).join(" ")
        }
    }

    def files = filesParameter.split(",")
    for (file in files) {
        def subfiles = findFiles glob: file
        print "Found files: " + subfiles
        for (subfile in subfiles) {
            def response = sh(script: """
                curl -k -X POST -F 'Username=${vars.username}' \
                -F 'File=@${subfile}' \
                ${watermarkFormat} ${baseUrl}
            """, returnStdout: true).trim()
            def filenameTokens = subfile.toString().split(/\\|\//)
            def filename = filenameTokens[filenameTokens.size() - 1]
            def outputFile = filename.substring(0, filename.lastIndexOf(".")) + ".pdf"
            def retJson = readJSON text: response
            if (retJson.Result == "Success") {
                dir(vars.dst_dir) {
                    def downloadUrl = retJson.ResultFileUrl
                    sh """
                        curl -k '${downloadUrl}' \
                        --output '${outputFile}'
                    """
                }
            }
        }
    }

}

return this
