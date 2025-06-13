import json
import sys, getopt
import os, logging, base64, glob, zipfile, shutil
import utils

def fileSign(configs):
    utils.cleanEnvAndArchives(configs['WORK_DIR'])

    artifactFiles = []
    for ite in range(len(configs['hsm_src_files'])):
        filesToSign = glob.glob(configs['hsm_src_files'][ite], recursive=True)
        utils.heavyLogging('fileSign: Found files to sign, {}'.format(filesToSign))
        for srcFile in filesToSign:
            srcFileNameRaw = os.path.basename(srcFile)
            if srcFile.endswith('.zip') == False:
                with zipfile.ZipFile(os.path.join(configs['WORK_DIR'], 'hsmTemporal.zip'), mode='w') as zf:
                    zf.write(srcFile)
                srcFile = os.path.join(configs['WORK_DIR'], 'hsmTemporal.zip')
            else:
                pass

            outputTmp = os.path.join(configs['WORK_DIR'], 'signed-stuff.zip')
            cmdEnv = dict(os.environ)
            # HTTP Request 1.14 required
            utils.popenWithStdout(['curl', '-s', '-k', '-X', 'POST', '-u', '{}:{}'.format(os.getenv('AD_USER'), os.getenv('AD_PASSWORD')), \
                            '--url', 'https://certsign.realtek.com/api/SignAPI/HSMSign', \
                            '-F', 'shaType={}'.format(configs['hsm_sha_types'][ite]), \
                            '-F', 'authCode={}'.format(os.getenv('AUTH_CODE')), \
                            '-F', 'File=@{}'.format(srcFile), \
                            '-o', outputTmp], cmdEnv)

            # test outputTmp is ZIP to throw error message
            try:
                with zipfile.ZipFile(outputTmp, 'r') as zip_ref:
                    zip_ref.extractall(os.path.join(configs['WORK_DIR'], 'test-unzip'))
            except:
                utils.heavyLogging('fileSign: SignAPI/HSMSign failure')
                sys.exit(-1)

            dstFile = configs['hsm_dst_files'][ite]
            if dstFile.endswith("\\") or dstFile.endswith("/"):
                srcFileNameTokens = srcFileNameRaw.split(".")
                os.makedirs(dstFile, exist_ok=True)
                utils.heavyLogging('fileSign: move signed file to folder {}'.format(dstFile))
                # hsm_dst_files is directory
                shutil.move(outputTmp, os.path.join(configs['WORK_DIR'], '{}-signed.zip'.format(srcFileNameTokens[0])))
                shutil.copy(os.path.join(configs['WORK_DIR'], '{}-signed.zip'.format(srcFileNameTokens[0])), \
                                os.path.join(dstFile, '{}-signed.zip'.format(srcFileNameTokens[0])))
                artifactFiles.append('{}-signed.zip'.format(srcFileNameTokens[0]))
            else:
                # unzip if suffix is not ".zip"
                if dstFile.endswith('.zip') == False:
                    hsmTemporalFolder = os.path.join(configs['WORK_DIR'], str(ite))
                    # TODO: cannot determine sign result by HTTP code
                    # catch unzip exception is stupid
                    with zipfile.ZipFile(outputTmp, 'r') as zip_ref:
                        utils.heavyLogging('fileSign: extract to {}'.format(hsmTemporalFolder))
                        zip_ref.extractall(hsmTemporalFolder)
                    dstFileBase = os.path.basename(dstFile)
                    for file in glob.glob('{}/**'.format(hsmTemporalFolder), recursive=True):
                        #utils.heavyLogging('fileSign: test {}'.format(file))
                        if os.path.isfile(file):
                            utils.heavyLogging('fileSign: move signed file {} to {}'.format(file, os.path.join(configs['WORK_DIR'], dstFileBase)))
                            shutil.move(file, os.path.join(configs['WORK_DIR'], dstFileBase))
                            shutil.copy(os.path.join(configs['WORK_DIR'], dstFileBase), dstFile)
                else:
                    dstFileBase = os.path.basename(dstFile)
                    utils.heavyLogging('fileSign: move signed file to {}'.format(os.path.join(configs['WORK_DIR'], dstFileBase)))
                    shutil.move(outputTmp, os.path.join(configs['WORK_DIR'], dstFileBase))
                    shutil.copy(os.path.join(configs['WORK_DIR'], dstFileBase), dstFile)
                artifactFiles.append(dstFileBase)

    fpArtifacts = open(os.path.join(configs['WORK_DIR'], '.artifacts'), 'w')
    fpArtifacts.write(','.join(artifactFiles))
    fpArtifacts.close()

def pureSign(configs):
    utils.cleanEnvAndArchives(configs['WORK_DIR'])

    dstFile = "sshsigned"
    if 'BUILD_BRANCH' in os.environ:
        dstFile = dstFile + '-' + os.getenv('BUILD_BRANCH')

    outputFiles = []
    for ite in range(len(configs['sshsign_sha'])):

        hsmPureSignParameter = dict()
        hsmPureSignParameter['keyName'] = configs['sshsign_sha'][ite]
        with open(configs['sshsign_hex'][ite]) as fpInput:
            hexData = fpInput.read()
        hsmPureSignParameter['hexData'] = hexData.strip()
        if 'system_account' in configs and configs['system_account'] == True:
            hsmPureSignParameter['signUser'] = configs['sign_user']
        hsmPureSignParameter['authCode'] = os.getenv('AUTH_CODE')
        try:
            hsmPureSignParameter['hashAlgo'] = int(configs['sshsign_hash_algo'][ite])
        except:
            utils.lightLogging('pureSign: take default hashAlgo 3')
            hsmPureSignParameter['hashAlgo'] = 3
        try:
            hsmPureSignParameter['paddingAlgo'] = int(configs['sshsign_padding_algo'][ite])
        except:
            utils.lightLogging('pureSign: take default paddingAlgo 1')
            hsmPureSignParameter['paddingAlgo'] = 1

        with open(os.path.join(configs['WORK_DIR'], 'body.json'), "w") as outfile:
            json.dump(hsmPureSignParameter, outfile)
        utils.heavyLogging('pureSign: ite {}'.format(ite))
        utils.lightLogging('pureSign: sign {} with keyname {}'.format(hsmPureSignParameter['hexData'], hsmPureSignParameter['keyName']))
        cmdEnv = dict(os.environ)
        utils.popenWithStdout(['curl', '-s', '-k', '-X', 'POST', '-u', '{}:{}'.format(os.getenv('AD_USER'), os.getenv('AD_PASSWORD')), \
                        '--url', 'https://certsign.realtek.com/api/SignAPI/HSMPureSign', \
                        '-H', 'Content-Type: application/json', \
                        '-d', '@{}'.format(os.path.join(configs['WORK_DIR'], 'body.json')), \
                        '-o', '{}'.format(os.path.join(configs['WORK_DIR'], 'output-{}.json'.format(ite)))], cmdEnv)
        
        with open(os.path.join(configs['WORK_DIR'], 'output-{}.json'.format(ite))) as f:
            output = json.load(f)
            if 'errorCode' in output:
                utils.heavyLogging('pureSign: result code {}'.format(output['errorCode']))
            if 'errorCode' in output and output['errorCode'] == '0':
                #utils.heavyLogging('pureSign: output(base64) {}'.format(output['data']['signature']))
                convertedbytes = base64.b64decode(output['data']['signature'])
                #utils.heavyLogging('pureSign: output(binary) {}({})'.format(convertedbytes, len(convertedbytes)))
                dstFileBase64 = dstFile + '-{}-base64'.format(ite)
                dstFileBytes = dstFile + '-{}-bytes'.format(ite)
                with open(os.path.join(configs['WORK_DIR'], dstFileBase64), 'w') as fpOutput:
                    fpOutput.write(output['data']['signature'])
                with open(os.path.join(configs['WORK_DIR'], dstFileBytes), 'wb') as fpOutput:
                    fpOutput.write(convertedbytes)
                outputFiles.append(dstFileBase64)
                outputFiles.append(dstFileBytes)
            else:
                sys.exit(output)

    fpArtifacts = open(os.path.join(configs['WORK_DIR'], '.artifacts'), 'w')
    fpArtifacts.write(','.join(outputFiles))
    fpArtifacts.close()

def main(argv):
    if "AUTH_CODE" not in os.environ:
        sys.exit("Environment variable AUTH_CODE not defined")
    if "AD_USER" not in os.environ:
        sys.exit("Environment variable AD_USER not defined")
    if "AD_PASSWORD" not in os.environ:
        sys.exit("Environment variable AD_PASSWORD not defined")

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

    logging.basicConfig(filename=os.path.join(workDir, 'sshsign.log'), format='%(asctime)s %(levelname)-8s %(message)s', level=logging.DEBUG, filemode='w')
    if skipTranslate == False:
        utils.translateConfig(configFile)
    configs = utils.loadConfigs(configFile)
    if configs['enable'] == False:
        print('main: skip sshsign')
        sys.exit(0)
    configs['WORK_DIR'] = workDir
    if command == 'PURE_SIGN':
        pureSign(configs)
    elif command == 'FILE_SIGN':
        fileSign(configs)
    else:
        utils.heavyLogging('main: invalid command {}'.format(command))

if __name__ == '__main__':
    main(sys.argv)