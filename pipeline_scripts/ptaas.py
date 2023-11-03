import json
import time
import utils
import getopt, sys
import subprocess as sb

def zapActiveScan(configFile, idx):
    with open(configFile) as fpConfig:
        jsonConfig = json.load(fpConfig)

    print("ZAP active scan: {}".format(jsonConfig["zap_scan_urls"][idx]))
    # Start ajax spider
    cmdAjaxSpider = sb.Popen(['curl', '-X', 'GET', '{}/JSON/ajaxSpider/action/scan/?apikey={}&url={}&inScope=&contextName=&subtreeOnly='.format(jsonConfig["zap_api_url"], jsonConfig["zap_token"], jsonConfig["zap_scan_urls"][idx])], stdout=sb.PIPE)
    cmdAjaxSpider.wait()
    # Ajax spider status
    ajaxSpiderStatus = ""
    while ajaxSpiderStatus != "stopped":
        cmdPollAjaxSpider = sb.check_output(['curl', '-X', 'GET', '{}/JSON/ajaxSpider/view/status/?apikey={}'.format(jsonConfig["zap_api_url"], jsonConfig["zap_token"])])
        line = cmdPollAjaxSpider.decode('utf-8').splitlines()
        line = line[0].strip()
        res = json.loads(line)
        ajaxSpiderStatus = res["status"]
        print("AJAX-spider: {}".format(ajaxSpiderStatus))
        time.sleep(30)

    cmdAjaxSpiderResult = sb.check_output(['curl', '-X', 'GET', '{}/JSON/ajaxSpider/view/numberOfResults/?apikey={}'.format(jsonConfig["zap_api_url"], jsonConfig["zap_token"])])
    line = cmdAjaxSpiderResult.decode('utf-8').splitlines()
    line = line[0].strip()
    res = json.loads(line)
    ajaxSpiderResults = res["numberOfResults"]
    print("AJAX-spider: totoal {}".format(ajaxSpiderResults))
    # Start active scan
    cmdActiveScan = sb.check_output(['curl', '-X', 'GET', \
        '{}/JSON/ascan/action/scan/?apikey={}&url={}&recurse=true&inScopeOnly=&scanPolicyName=&method=&postData=&contextId='.format(jsonConfig["zap_api_url"], jsonConfig["zap_token"], jsonConfig["zap_scan_urls"][idx])])
    line = cmdActiveScan.decode('utf-8').splitlines()
    line = line[0].strip()
    res = json.loads(line)
    actieScanId = res["scan"]
    print("Active-scan ID: {}".format(actieScanId))
    # Check active scan status
    activeScanPercentage = 0
    activeScanTime = 0
    while activeScanPercentage < 100:
        cmdPollActiveScan = sb.check_output(['curl', '{}/JSON/ascan/view/status/?apikey={}&scanId={}'.format(jsonConfig["zap_api_url"], jsonConfig["zap_token"], actieScanId)])
        line = cmdPollActiveScan.decode('utf-8').splitlines()
        line = line[0].strip()
        res = json.loads(line)
        activeScanPercentage = int(res["status"])
        print("Active-scan: {}%".format(activeScanPercentage))
        time.sleep(60)
        activeScanTime = activeScanTime + 1
        if jsonConfig["zap_activescan_timeout"] != 0 and activeScanTime >= jsonConfig["zap_activescan_timeout"]:
            # Stop active scan if timeout
            cmdStop = sb.Popen(['curl', \
                '{}/JSON/ascan/action/stop/?apikey={}&scanId={}'.format(jsonConfig["zap_api_url"], jsonConfig["zap_token"], actieScanId)], stdout=sb.PIPE)
            cmdStop.wait()
            print("Active-scan timeout: {}".format(activeScanTime))
            break
    # Retrieve report
    cmdJsonReport = sb.Popen(['curl', \
        '{}/JSON/alert/view/alerts/?apikey={}&baseurl={}&start=0&count=5000&riskId='.format(jsonConfig["zap_api_url"], jsonConfig["zap_token"], jsonConfig["zap_scan_urls"][idx]), \
        '-o', 'ZAP-ACTIVE-SCAN-{}.json'.format(idx)], stdout=sb.PIPE)
    cmdJsonReport.wait()
    # Could not soecify baseurl for htmlreport API, pending
    cmdHTMLReport = sb.Popen(['curl', '-X', 'GET', \
        '{}/OTHER/core/other/htmlreport/'.format(jsonConfig["zap_api_url"]), \
        '-H', 'Accept: application/json', '-H', 'X-ZAP-API-Key: {}'.format(jsonConfig["zap_token"]), '-o', 'ZAP-ACTIVE-SCAN-{}.html'.format(idx)], stdout=sb.PIPE)
    cmdHTMLReport.wait()

def main(argv):
    try:
        opts, args = getopt.getopt(argv[1:], 'f:v', ["config=", "version"])
    except getopt.GetoptError:
        sys.exit()
    for name, value in opts:
        if name in ('-v', '--version'):
            print("0.1")
            sys.exit(0)
        elif name in ('-f', '--config'):
            config = value

    utils.translateConfig(config)
    with open(config) as fpConfig:
        jsonConfig = json.load(fpConfig)
    for i in range(len(jsonConfig["zap_scan_urls"])):
        zapActiveScan(config, i)

if __name__ == "__main__":
    main(sys.argv)