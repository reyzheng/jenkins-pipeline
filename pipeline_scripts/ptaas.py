import os, time, logging
import json
import getopt, sys
import subprocess as sb
import utils

def zapActiveScans(configs):
    scanEnvPrefix = zapActiveScanStartup(configs)
    for i in range(len(configs['zap_scan_urls'])):
        zapActiveScan(scanEnvPrefix, configs, i)

def zapActiveScanStartup(configs):
    cmdEnvs = dict(os.environ)

    if configs['zap_singularity'] == True:
        utils.makeEmptyDirectory(os.path.join(configs['WORK_DIR'], 'owaspzap'))
        cmd = ['git', 'clone', 'https://mirror.rtkbf.com/gerrit/sdlc/jenkins-pipeline/singularity/owaspzap', '-b', 'stable', '--single-branch', '--depth', '1', os.path.join(configs['WORK_DIR'], 'owaspzap')]
        utils.popenWithStdout(cmd, cmdEnvs)
        scanEnvPrefix = ['singularity', 'exec', os.path.join(configs['WORK_DIR'], 'owaspzap', 'owaspzap.sif')]
    else:
        scanEnvPrefix = []
    utils.heavyLogging('zapActiveScanStartup: scanEnvPrefix {}'.format(scanEnvPrefix))

    #singularity exec owaspzap.sif zap.sh -daemon -host 0.0.0.0 \
    #        -port 8090 -config api.addrs.addr.name=.* \
    #        -config api.addrs.addr.regex=true -config api.key=bq0e5mrn9b680t303greng8ci8 -silent
    cmd = scanEnvPrefix + ['zap.sh', '-daemon', '-host', '0.0.0.0', \
            '-port', '8090', '-config', 'api.addrs.addr.name=.*', \
            '-config', 'api.addrs.addr.regex=true', '-config', 'api.key=bq0e5mrn9b680t303greng8ci8', '-loglevel', 'info', '-silent', '-nostdout']
    utils.popenBackground(cmd, cmdEnvs)
    cmd = scanEnvPrefix + ['sleep', '120']
    utils.popenWithStdout(cmd, cmdEnvs)
    #singularity exec owaspzap.sif curl -s -X GET http://localhost:8090/JSON/stats/view/stats/ \
    #        -H 'Accept: application/json' \
    #        -H 'X-ZAP-API-Key: bq0e5mrn9b680t303greng8ci8' 
    cmd = scanEnvPrefix + ['curl', '-X', 'GET', 'http://localhost:8090/JSON/stats/view/stats/', \
            '-H', 'Accept: application/json', \
            '-H', 'X-ZAP-API-Key: bq0e5mrn9b680t303greng8ci8', \
            '-o', os.path.join(configs['WORK_DIR'], 'stats.json')]
    utils.popenWithStdout(cmd, cmdEnvs)

    return scanEnvPrefix

def zapDisableScanner(scanEnvPrefix, jsonConfig, scannerId):
    utils.popenReturnStdout(scanEnvPrefix + ['curl', \
                                '{}/JSON/ascan/action/disableScanners/?ids={}'.format(jsonConfig["zap_api_url"], scannerId), \
                                '-H', 'Accept: application/json', \
                                '-H', 'X-ZAP-API-Key: {}'.format(jsonConfig["zap_token"]), \
                                '-o', os.path.join(jsonConfig['WORK_DIR'], 'disableScanner-{}.json'.format(scannerId))], dict(os.environ))

def zapEnableScanner(scanEnvPrefix, jsonConfig, scannerId):
    utils.popenReturnStdout(scanEnvPrefix + ['curl', \
                                '{}/JSON/ascan/action/enableScanners/?ids={}'.format(jsonConfig["zap_api_url"], scannerId), \
                                '-H', 'Accept: application/json', \
                                '-H', 'X-ZAP-API-Key: {}'.format(jsonConfig["zap_token"]), \
                                '-o', os.path.join(jsonConfig['WORK_DIR'], 'enableScanners-{}.json'.format(scannerId))], dict(os.environ))

def zapEnableAllScanner(scanEnvPrefix, jsonConfig):
    utils.popenReturnStdout(scanEnvPrefix + ['curl', \
                                '{}/JSON/ascan/action/enableAllScanners/'.format(jsonConfig["zap_api_url"]), \
                                '-H', 'Accept: application/json', \
                                '-H', 'X-ZAP-API-Key: {}'.format(jsonConfig["zap_token"]), \
                                '-o', os.path.join(jsonConfig['WORK_DIR'], 'enableAllScanners.json')], dict(os.environ))

def zapActiveScan(scanEnvPrefix, jsonConfig, idx):
    cmdEnvs = dict(os.environ)

    utils.heavyLogging('zapActiveScan: url {}'.format(jsonConfig["zap_scan_urls"][idx]))
    # Load context
    fileContext = os.path.join(os.getenv('WORKSPACE'), jsonConfig['WORK_DIR'], 'zap.context')
    fpContext = open(fileContext, 'w')
    fpSampleContext = open(os.path.join(os.getenv('PF_ROOT'), 'pipeline_scripts', 'zap.context'), 'r')
    lines = fpSampleContext.readlines()
    for line in lines:
        if line.strip().startswith('<incregexes>'):
            fpContext.write('        <incregexes>{}.*</incregexes>\n'.format(jsonConfig['zap_scan_urls'][idx]))
            fpContext.write('        <excregexes>https://.*mozilla.*</excregexes>\n')
        else:
            fpContext.write(line)
    fpSampleContext.close()
    fpContext.close()

    #singularity exec owaspzap.sif curl -X GET \
    #        "http://localhost:8090/JSON/context/action/importContext/?contextFile=/home/reycheng/sdlc/sdlc_singularity/owaspzap/zap.context" \
    #        -H 'Accept: application/json' \
    #        -H 'X-ZAP-API-Key: bq0e5mrn9b680t303greng8ci8'
    utils.popenWithStdout(scanEnvPrefix + ['curl', '-X', 'GET', \
                                '{}/JSON/context/action/importContext/?contextFile={}'.format(jsonConfig["zap_api_url"], fileContext), \
                                '-H', 'Accept: application/json', \
                                '-H', 'X-ZAP-API-Key: {}'.format(jsonConfig["zap_token"]), \
                                '-o', os.path.join(jsonConfig['WORK_DIR'], 'importContext.json')], cmdEnvs)
    with open(os.path.join(jsonConfig['WORK_DIR'], 'importContext.json')) as fpImportContext:
        jsonfpImportContext = json.load(fpImportContext)
        if 'contextId' in jsonfpImportContext:
            utils.heavyLogging('zapActiveScan: contextId {}'.format(jsonfpImportContext['contextId']))
        else:
            utils.heavyLogging('zapActiveScan: invalid contextId')
            sys.exit(-1)
    # Start ajax spider
    # max. crawl duration 1 min.
    utils.popenWithStdout(scanEnvPrefix + ['curl', '-X', 'GET', \
                                '{}/JSON/ajaxSpider/action/setOptionMaxDuration/?Integer=1'.format(jsonConfig["zap_api_url"]), \
                                '-H', 'X-ZAP-API-Key: {}'.format(jsonConfig["zap_token"])], cmdEnvs)
    utils.popenWithStdout(scanEnvPrefix + ['curl', '-s', '-X', 'GET', \
                                '{}/JSON/ajaxSpider/action/scan/?apikey={}&url={}&inScope=&contextName=&subtreeOnly='.format(jsonConfig["zap_api_url"], jsonConfig["zap_token"], jsonConfig["zap_scan_urls"][idx])], cmdEnvs)
    # Ajax spider status
    ajaxCount = 0
    ajaxSpiderStatus = ""
    while ajaxSpiderStatus != "stopped":
        cmdPollAjaxSpider = sb.check_output(scanEnvPrefix + ['curl', '-s', '-X', 'GET', \
                                                '{}/JSON/ajaxSpider/view/status/?apikey={}'.format(jsonConfig["zap_api_url"], jsonConfig["zap_token"])])
        line = cmdPollAjaxSpider.decode('utf-8').splitlines()
        line = line[0].strip()
        res = json.loads(line)
        ajaxSpiderStatus = res["status"]
        utils.heavyLogging('zapActiveScan: AJAX-spider status {}'.format(ajaxSpiderStatus))
        time.sleep(30)
        ajaxCount = ajaxCount + 1
        if ajaxCount == 3:
            # setOptionMaxDuration fails sometimes
            utils.heavyLogging('zapActiveScan: stop AJAX-spider manually')
            utils.popenReturnStdout(scanEnvPrefix + ['curl', '-X', 'GET', \
                                            '{}/JSON/ajaxSpider/action/stop/'.format(jsonConfig["zap_api_url"]), \
                                            '-H', 'X-ZAP-API-Key: {}'.format(jsonConfig["zap_token"])], cmdEnvs)

    ajaxSpiderRet = utils.popenReturnStdout(scanEnvPrefix + ['curl', '-s', '-X', 'GET', \
                                            '{}/JSON/ajaxSpider/view/numberOfResults/?apikey={}'.format(jsonConfig["zap_api_url"], jsonConfig["zap_token"])], cmdEnvs)
    utils.heavyLogging('zapActiveScan: AJAX-spider totoal {}'.format(ajaxSpiderRet))
    res = json.loads(bytes.decode(ajaxSpiderRet['lines'][0], 'utf-8'))
    ajaxSpiderResults = res["numberOfResults"]
    utils.heavyLogging('zapActiveScan: AJAX-spider totoal {}'.format(ajaxSpiderResults))
    # Start active scan
    # setOptionMaxRuleDurationInMins, setOptionMaxScanDurationInMins has no effect

    # disable all scanners
    #utils.popenReturnStdout(scanEnvPrefix + ['curl', \
    #                            '{}/JSON/ascan/action/disableAllScanners/'.format(jsonConfig["zap_api_url"]), \
    #                            '-H', 'Accept: application/json', \
    #                            '-H', 'X-ZAP-API-Key: {}'.format(jsonConfig["zap_token"]), \
    #                            '-o', os.path.join(jsonConfig['WORK_DIR'], 'disableAllScanners.json')], dict(os.environ))

    zapEnableAllScanner(scanEnvPrefix, jsonConfig)
    # disable dom based XSS
    #zapDisableScanner(scanEnvPrefix, jsonConfig, 40026)
    # enable dom based XSS
    #zapEnableScanner(scanEnvPrefix, jsonConfig, 40026)

    # dom based XSS strength
    #utils.popenReturnStdout(scanEnvPrefix + ['curl', \
    #                            '{}/JSON/ascan/action/setScannerAttackStrength/?id=40026&attackStrength=LOW'.format(jsonConfig["zap_api_url"]), \
    #                            '-H', 'Accept: application/json', \
    #                            '-H', 'X-ZAP-API-Key: {}'.format(jsonConfig["zap_token"]), \
    #                            '-o', os.path.join(jsonConfig['WORK_DIR'], 'setScannerAttackStrength.json')], cmdEnvs)
    activeScanRet = utils.popenReturnStdout(scanEnvPrefix + ['curl', '-m', '60', '-X', 'GET', \
        '{}/JSON/ascan/action/scan/?apikey={}&url={}&recurse=true&inScopeOnly=true&scanPolicyName=&method=&postData=&contextId={}'.format(jsonConfig["zap_api_url"], jsonConfig["zap_token"], jsonConfig["zap_scan_urls"][idx], jsonfpImportContext['contextId'])], cmdEnvs)
    utils.heavyLogging('zapActiveScan: Active-scan start {}'.format(activeScanRet))
    res = json.loads(bytes.decode(activeScanRet['lines'][0], 'utf-8'))
    actieScanId = res["scan"]
    utils.heavyLogging('zapActiveScan: Active-scan ID {}'.format(actieScanId))
    # Check active scan status
    activeScanPercentage = 0
    activeScanTime = 0
    while activeScanPercentage < 100:
        cmdPollActiveScan = sb.check_output(scanEnvPrefix + ['curl', '{}/JSON/ascan/view/status/?apikey={}&scanId={}'.format(jsonConfig["zap_api_url"], jsonConfig["zap_token"], actieScanId)])
        line = cmdPollActiveScan.decode('utf-8').splitlines()
        line = line[0].strip()
        res = json.loads(line)
        activeScanPercentage = int(res["status"])
        utils.heavyLogging('zapActiveScan: progress {}%'.format(activeScanPercentage))
        time.sleep(60)
        activeScanTime = activeScanTime + 1
        if jsonConfig["zap_activescan_timeout"] != 0 and activeScanTime >= jsonConfig["zap_activescan_timeout"]:
            # Stop active scan if timeout
            utils.heavyLogging('zapActiveScan: Active-scan timeout {}'.format(activeScanTime))
            utils.popenWithStdout(scanEnvPrefix + ['curl', '-m', '60', \
                '{}/JSON/ascan/action/stop/?apikey={}&scanId={}'.format(jsonConfig["zap_api_url"], jsonConfig["zap_token"], actieScanId)], cmdEnvs)
            break
    # Retrieve report
    cmdJsonReport = sb.Popen(scanEnvPrefix + ['curl', \
        '{}/JSON/alert/view/alerts/?apikey={}&baseurl={}&start=0&count=5000&riskId='.format(jsonConfig["zap_api_url"], jsonConfig["zap_token"], jsonConfig["zap_scan_urls"][idx]), \
        '-o', 'ZAP-ACTIVE-SCAN-{}.json'.format(idx)], stdout=sb.PIPE)
    cmdJsonReport.wait()
    # Could not soecify baseurl for htmlreport API, pending
    cmdHTMLReport = sb.Popen(scanEnvPrefix + ['curl', '-X', 'GET', \
        '{}/OTHER/core/other/htmlreport/'.format(jsonConfig["zap_api_url"]), \
        '-H', 'Accept: application/json', '-H', 'X-ZAP-API-Key: {}'.format(jsonConfig["zap_token"]), '-o', 'ZAP-ACTIVE-SCAN-{}.html'.format(idx)], stdout=sb.PIPE)
    cmdHTMLReport.wait()

def main(argv):
    skipTranslate = False

    try:
        opts, args = getopt.getopt(argv[1:], 'c:w:f:v', ["command", "work_dir=", "config=", "version"])
    except getopt.GetoptError:
        sys.exit()
    for name, value in opts:
        if name in ('-v', '--version'):
            print("0.1")
            sys.exit(0)
        elif name in ('-f', '--config'):
            configFile = value
        elif name in ('-w', '--work_dir'):
            if os.path.isdir(value) == False:
                os.makedirs(value)
            workDir = value
        elif name in ('-c', '--command'):
            command = value

    logging.basicConfig(filename=os.path.join(workDir, 'bdba.log'), format='%(asctime)s %(levelname)-8s %(message)s', level=logging.DEBUG, filemode='w')
    if skipTranslate == False:
        utils.translateConfig(configFile)
    configs = utils.loadConfigs(configFile)
    configs['WORK_DIR'] = workDir
    if configs['enable'] == False:
        print('main: skip ptaas')
        sys.exit(0)
    if command == 'ZAP_ACTIVE_SCAN':
        zapActiveScans(configs)

if __name__ == "__main__":
    main(sys.argv)