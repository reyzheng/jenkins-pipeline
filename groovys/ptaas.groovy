def init(stageName) {
    def defaultConfigs = [
        display_name: "PTaaS",
        node: "docker:owasp/zap2docker-stable",
        zap_api_url: "http://172.22.139.7:8090",
        zap_token: "bq0e5mrn9b680t303greng8ci8",
        zap_activescan_timeout: 0,
        zap_scan_urls: [],

        scriptableParams: ["zap_scan_urls"]
    ]
    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)

    return config
}

def func(stageName) {
    def configs = readJSON file: ".pf-all/settings/${stageName}_config.json"
    
    sh """
        zap.sh -daemon -host 0.0.0.0 -port 8090 -config api.addrs.addr.name=.* -config api.addrs.addr.regex=true -config api.key=bq0e5mrn9b680t303greng8ci8 &
        # wait 90 seconds
        sleep 90
        # test connection
        curl -X GET http://localhost:8090/JSON/stats/view/stats/ \
                    -H 'Accept: application/json' \
                    -H 'X-ZAP-API-Key: bq0e5mrn9b680t303greng8ci8'
    """
    def pythonExec = utils.getPython()
    sh """
        ${pythonExec} .pf-all/pipeline_scripts/ptaas.py -f .pf-all/settings/${stageName}_config.json
    """
    archiveArtifacts artifacts: "ZAP-ACTIVE-SCAN*"
}

return this
