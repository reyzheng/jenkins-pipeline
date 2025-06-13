import sys, getopt
import os, time, logging, json
import utils

def pollSMS(configs):
    utils.cleanEnvAndArchives(configs['WORK_DIR'])
    cmdEnv = dict(os.environ)
    smsAccount = configs['sms_account']
    smsToken = os.getenv('SMS_TOKEN')
    if configs['sms_urf_id'] != '':
        smsURFId = configs['sms_urf_id']
    elif 'PIPELINE_AS_CODE_URF_ID' in os.environ:
        smsURFId = os.getenv('PIPELINE_AS_CODE_URF_ID')
    else:
        utils.heavyLogging('pollSMS: invalid URF id')
        sys.exit(-1)
    utils.heavyLogging('pollSMS: query SMS {} CICDStatus by account {}'.format(smsURFId, smsAccount))

    pollingCount = int(configs['polling_timeout'] * 60 / configs['polling_interval'])
    for i in range(pollingCount):
        ret = -1
        postParam = 'Account={}&Token={}&Id={}'.format(smsAccount, smsToken, smsURFId)
        cmd = ['curl', '-s', '-d', postParam, '-o', os.path.join(configs['WORK_DIR'], 'queryReleaseStatus.json'), 'https://sms.realtek.com/RestApi/ReleaseStatus']
        utils.popenWithStdout(cmd, cmdEnv)
        try:
            fpJSON = open(os.path.join(configs['WORK_DIR'], 'queryReleaseStatus.json'))
            jsonObject = json.load(fpJSON)
            fpJSON.close()
            ret = int(jsonObject['CICDStatus'])
        except:
            pass
        utils.heavyLogging('pollSMS: got SMS CICDStatus {}'.format(ret))

        if ret in configs['expected_cicdstatus']:
            # got
            utils.saveEnv(configs['WORK_DIR'], 'PIPELINE_AS_CODE_SMS_CICD_STATUS', ret)
            return
        else:
            utils.heavyLogging('pollSMS: wait {} seconds'.format(configs['polling_interval']))
            time.sleep(configs['polling_interval'])

def main(argv):
    workDir = ''
    configFile = ''
    skipTranslate = False
    try:
        opts, args = getopt.getopt(argv[1:], 'c:w:f:vs', ["command=", "work_dir=", "config=", "version", "skip_translate"])
    except getopt.GetoptError:
        sys.exit()
    for name, value in opts:
        if name in ('-v', '--version'):
            print("0.1")
            sys.exit(0)
        elif name in ('-s', '--skip_translate'):
            skipTranslate = True
        elif name in ('-f', '--config'):
            configFile = value
        elif name in ('-w', '--work_dir'):
            if os.path.isdir(value) == False:
                os.makedirs(value)
            workDir = value
        elif name in ('-c', '--command'):
            command = value

    logging.basicConfig(filename=os.path.join(workDir, '{}.log'.format(os.path.basename(__file__))), \
                            format='%(asctime)s %(levelname)-8s %(message)s', level=logging.DEBUG, filemode='w')
    if skipTranslate == False:
        utils.translateConfig(configFile)
    configs = utils.loadConfigs(configFile)

    if configs['enable'] == False:
        utils.heavyLogging('Stage {} cancelled manually'.format(configs['stageName']))
        sys.exit(0)
    configs['WORK_DIR'] = workDir
    pollSMS(configs)

if __name__ == '__main__':
    main(sys.argv)