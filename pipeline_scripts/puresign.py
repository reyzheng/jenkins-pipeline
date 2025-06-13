import os, logging, json, time
import getopt, sys, threading
import utils, hsmcli

def createPureSign(configs, data, uuid):
    hashAlgoMap = dict()
    hashAlgoMap['MD5'] = '1'
    hashAlgoMap['SHA1'] = '2'
    hashAlgoMap['SHA256'] = '3'
    hashAlgoMap['SHA384'] = '4'
    hashAlgoMap['SHA512'] = '5'
    paddingAlgoMap = dict()
    paddingAlgoMap['no padding'] = '1'
    paddingAlgoMap['p1'] = '2'
    paddingAlgoMap['p1 oaep'] = '3'
    paddingAlgoMap['p1 pss'] = '4'
    # ./hsm-cli file-sign create --uuid 9f9c7662-462d-4fd3-b316-e5f7edc60488
    cmds = [hsmcli.hsmCliExec(configs['work_dir']), '-c', os.path.join(configs['work_dir'], 'hsm.config.yaml'), \
                'pure-sign', 'create', \
                '--uuid', uuid, \
                '--data-encode', configs['encode'],\
                '--hash-algo', hashAlgoMap[configs['hash_algo']],\
                '--padding-algo', paddingAlgoMap[configs['padding_algo']], \
                '--data', data]
    ret = utils.popenReturnStdout(cmds, dict(os.environ))
    if ret['code'] == 0:
        return json.loads(ret['lines'][0])
    else:
        utils.heavyLogging('createPureSign: fail')
        sys.exit(1)

def checkPureSignStatus(configs, id):
    # 12*10 sec max
    cmds = [hsmcli.hsmCliExec(configs['work_dir']), '-c', os.path.join(configs['work_dir'], 'hsm.config.yaml'), 'pure-sign', 'status', '--id', id]
    fpStdout = os.path.join(configs['work_dir'], 'puresign-status-{}.stdout'.format(id))
    fpStderr = os.path.join(configs['work_dir'], 'puresign-status-{}.stderr'.format(id))
    for i in range(12):
        ret = utils.popenToFile(cmds, dict(os.environ), fpStdout, fpStderr)
        if ret == 0:
            with open(fpStdout, errors='ignore') as f:
                jsonStatus = json.load(f)
                if jsonStatus['status'] == "SUCCESS":
                    break
                utils.heavyLogging('checkPureSignStatus: status {}'.format(jsonStatus['status']))
        time.sleep(30)

def downloadPureSign(signeds, configs, id, idx):
    checkPureSignStatus(configs, id)
    #./hsm-cli pure-sign download --id 2025.04.18-281ed
    outputFilename = os.path.join(configs['work_dir'], 'signed-data-{}'.format(idx))
    if 'BUILD_BRANCH' in os.environ:
        outputFilename = '{}-{}'.format(outputFilename, os.getenv('BUILD_BRANCH'))
    cmds = [hsmcli.hsmCliExec(configs['work_dir']), '-c', os.path.join(configs['work_dir'], 'hsm.config.yaml'), \
                            'pure-sign', 'download', \
                            '--output', outputFilename, \
                            '--id', id]
    ret = utils.popenReturnStdout(cmds, dict(os.environ))
    if ret['code'] == 0:
        utils.heavyLogging('downloadPureSign: {}'.format(ret['lines'][0]))
        signeds[idx] = os.path.basename(outputFilename)
    else:
        utils.heavyLogging('downloadPureSign: fail')
        sys.exit(1)

def pureSign(configs):
    # download hsm-cli
    hsmcli.downloadHSMCli(configs['work_dir'])
    hsmcli.hsmConfig(configs['work_dir'])
    availableAlgos = hsmcli.listAvailableAlgos(configs['work_dir'])
    if len(availableAlgos) == 0:
        sys.exit(1)

    uuid = ''
    for availableAlgo in availableAlgos:
        if availableAlgo['algoName'] == configs['sign_algo']:
            uuid = availableAlgo['hsmSettingUuid']
            utils.heavyLogging('pureSign: algo {}, uuid {}'.format(availableAlgo['algoName'], uuid))
            break
    if uuid == '':
        utils.heavyLogging('pureSign: unknown algo. {}'.format(configs['sign_algo']))
        sys.exit(-1)

    signIds = []
    signeds = [None] * len(configs['sign_datas'])
    for sign_data in configs['sign_datas']:
        with open(sign_data) as fpInput:
            hexData = fpInput.read()
        jsonCreation = createPureSign(configs, hexData.strip(), uuid)
        signIds.append(jsonCreation['id'])
    utils.heavyLogging('pureSign: signIds {}'.format(signIds))

    downloadThreads = []
    for i in range(len(signIds)):
        downloadThreads.append(threading.Thread(target = downloadPureSign, args = (signeds, configs, signIds[i], i,)))
        downloadThreads[i].start()
    for i in range(len(signIds)):
        downloadThreads[i].join()

    fpArtifacts = open(os.path.join(configs['work_dir'], '.artifacts'), 'w')
    fpArtifacts.write(','.join(signeds))
    fpArtifacts.close()

def main(argv):
    workDir = ''
    try:
        opts, args = getopt.getopt(argv[1:], 'w:f:c:v', ["work_dir=", "config=", "version"])
    except getopt.GetoptError:
        sys.exit()
    for name, value in opts:
        if name in ('-v', '--version'):
            print("0.1")
            sys.exit(0)
        elif name in ('-f', '--config'):
            configFile = value
        elif name in ('-w', '--work_dir'):
            workDir = value

    utils.makeEmptyDirectory(workDir)
    logging.basicConfig(filename=os.path.join(workDir, '{}.log'.format(os.path.basename(__file__))), level=logging.DEBUG, filemode='w')
    utils.translateConfig(configFile)
    configs = utils.loadConfigs(configFile)
    configs['work_dir'] = workDir
    if configs['enable'] == False:
        print('main: skip {}'.format(os.path.basename(__file__)))
        sys.exit(0)
    pureSign(configs)

if __name__ == "__main__":
    main(sys.argv)
