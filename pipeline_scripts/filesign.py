import os, logging, time, json, re, shutil
import getopt, sys, zipfile, threading
import utils, hsmcli

def createFileSign(fileSingIds, idx, configs, uuid):
    hsmcli.preapareHookConfig(configs)
    # ./hsm-cli file-sign create --uuid 9f9c7662-462d-4fd3-b316-e5f7edc60488

    cmds = [hsmcli.hsmCliExec(configs['work_dir']), '-c', os.path.join(configs['work_dir'], 'hsm.config.yaml'), 'file-sign', 'create', '--uuid', uuid]
    ret = utils.popenReturnStdout(cmds, dict(os.environ))
    if ret['code'] == 0:
        retJson = json.loads(ret['lines'][0])
        fileSingIds[idx] = retJson['id']
    else:
        utils.heavyLogging('createFileSign: fail')
        sys.exit(1)

def find_matching_files(regex_pattern, root_dir="."):
    # Normalize regex path (handle Windows paths)
    regex_path = regex_pattern.replace("\\", "/")

    # Extract base path prefix before the first regex-like token
    parts = regex_path.split('/')
    base_parts = []
    for part in parts:
        if re.search(r"[.*+?^${}()|\[\]\\]", part):
            break
        base_parts.append(part)

    base_dir = os.path.join(root_dir, *base_parts) if base_parts else root_dir
    regex = re.compile(regex_path)
    utils.lightLogging('find_matching_files: base_dir {}'.format(base_dir))
    utils.lightLogging('find_matching_files: regex_path {}'.format(regex_path))

    matches = []
    for dirpath, _, filenames in os.walk(base_dir):
        for fname in filenames:
            full_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(full_path, root_dir).replace(os.sep, "/")
            utils.lightLogging('find_matching_files: test rel_path {}'.format(rel_path))
            if regex.fullmatch(rel_path):
                matches.append(full_path)

    return matches

def uploadFileSign(configs, srcFile, hsmId):
    tempDir = os.path.join(configs['work_dir'], 'tosign')
    utils.makeEmptyDirectory(tempDir)

    filesToSign = find_matching_files(srcFile)
    utils.heavyLogging('uploadFileSign: files {}({})'.format(filesToSign, srcFile))
    for fileToSign in filesToSign:
        shutil.copy(fileToSign, tempDir)
    # ./hsm-cli file-sign upload --folder ./test  --id 2025.04.21-5c173
    if len(filesToSign) > 1:
        # multiple files
        cmds = [hsmcli.hsmCliExec(configs['work_dir']), '-c', os.path.join(configs['work_dir'], 'hsm.config.yaml'), 'file-sign', \
                                'upload', '--folder', tempDir, '--id', hsmId]
    else:
        cmds = [hsmcli.hsmCliExec(configs['work_dir']), '-c', os.path.join(configs['work_dir'], 'hsm.config.yaml'), 'file-sign', \
                                'upload', '--file', os.path.join(tempDir, os.path.basename(filesToSign[0])), '--id', hsmId]
    ret = utils.popenWithStdout(cmds, dict(os.environ))
    if ret != 0:
        utils.heavyLogging('uploadFileSign: upload failed')
        sys.exit(-1)
    # ./hsm-cli file-sign start --id 2025.04.21-5c173
    cmds = [hsmcli.hsmCliExec(configs['work_dir']), '-c', os.path.join(configs['work_dir'], 'hsm.config.yaml'), 'file-sign', 'start', '--id', hsmId]
    ret = utils.popenReturnStdout(cmds, dict(os.environ))
    if ret['code'] == 0:
        utils.heavyLogging('uploadFileSign: status {}'.format(ret['lines']))
    else:
        utils.heavyLogging('uploadFileSign: file-sign start unknown error {}'.format(ret['code']))
        sys.exit(-1)

def checkFileSignStatus(configs, id):
    # 12*10 sec max
    successStatus = False
    cmds = [hsmcli.hsmCliExec(configs['work_dir']), '-c', os.path.join(configs['work_dir'], 'hsm.config.yaml'), 'file-sign', 'status', '--id', id]
    fpStdout = os.path.join(configs['work_dir'], 'filesign-status-{}.stdout'.format(id))
    fpStderr = os.path.join(configs['work_dir'], 'filesign-status-{}.stderr'.format(id))
    for i in range(12):
        ret = utils.popenToFile(cmds, dict(os.environ), fpStdout, fpStderr)
        if ret == 0:
            with open(fpStdout, errors='ignore') as f:
                jsonStatus = json.load(f)
                if jsonStatus['status'] == "SUCCESS":
                    successStatus = True
                    break
                utils.heavyLogging('checkFileSignStatus: status {}'.format(jsonStatus['status']))
        time.sleep(60)
    if successStatus == False:
        utils.heavyLogging('checkFileSignStatus: timeout')
        sys.exit(-1)

def downloadFileSign(artifacts, configs, hsmId, idx):
    checkFileSignStatus(configs, hsmId)
    outputFile = os.path.join(configs['work_dir'], '{}-signed-{}.zip'.format(configs['plainStageName'],idx))
    if 'BUILD_BRANCH' in os.environ:
        filename, file_extension = os.path.splitext(outputFile)
        outputFile = '{}-{}{}'.format(filename, os.getenv('BUILD_BRANCH'), file_extension)
    # ./hsm-cli file-sign download --output OUTPUT --id 2025.04.21-5c173
    cmds = [hsmcli.hsmCliExec(configs['work_dir']), '-c', os.path.join(configs['work_dir'], 'hsm.config.yaml'), \
                            'file-sign', 'download', \
                            '--output', outputFile, \
                            '--id', hsmId]
    utils.popenWithStdout(cmds, dict(os.environ))
    if len(configs['dst_files']) > idx:
        # use has define dst_files
        if configs['dst_files'][idx].endswith('/') or configs['dst_files'][idx].endswith('\\'):
            os.makedirs(configs['dst_files'][idx], exist_ok=True)
            dest = os.path.join(configs['dst_files'][idx], os.path.basename(outputFile))
            if os.path.exists(dest):
                os.remove(dest)
            os.rename(outputFile, dest)
            artifacts[idx] = 'WORKSPACE:{}'.format(dest)
        elif configs['dst_files'][idx].endswith('.zip'):
            os.rename(outputFile, configs['dst_files'][idx])
            artifacts[idx] = 'WORKSPACE:{}'.format(configs['dst_files'][idx])
        else:
            with zipfile.ZipFile(outputFile, 'r') as zObject:
                zObject.extractall(path=os.path.join(configs['work_dir'], 'extract'))
            file_count = 0
            for root, dirs, files in os.walk(os.path.join(configs['work_dir'], 'extract')):
                file_count += len(files)
            if file_count > 1:
                utils.heavyLogging('downloadFileSign: cannot rename to {}'.format(configs['dst_files'][idx]))
                sys.exit(-1)
            else:
                utils.heavyLogging('downloadFileSign: rename {} to {}'.format(os.path.join(root, files[0]), configs['dst_files'][idx]))
                os.rename(os.path.join(root, files[0]), configs['dst_files'][idx])
                artifacts[idx] = 'WORKSPACE:{}'.format(configs['dst_files'][idx])
    else:
        artifacts[idx] = os.path.basename(outputFile)

def fileSign(configs):
    # download hsm-cli
    hsmcli.downloadHSMCli(configs['work_dir'])
    hsmcli.hsmConfig(configs['work_dir'])
    availableAlgos = hsmcli.listAvailableAlgos(configs['work_dir'])
    if len(availableAlgos) == 0:
        sys.exit(1)

    uuid = ''
    for availableAlgo in availableAlgos:
        if availableAlgo['algoName'] == configs['sign_algo'] or availableAlgo['keyName'] == configs['sign_algo']:
            utils.heavyLogging('fileSign: found match algo. {}'.format(availableAlgo['algoName']))
            uuid = availableAlgo['hsmSettingUuid']
            break
    if uuid == '':
        utils.heavyLogging('fileSign: unknown algo. {}'.format(configs['sign_algo']))
        sys.exit(-1)

    fileSignIds = [None] * len(configs['src_files'])
    for i in range(len(configs['src_files'])):
        createFileSign(fileSignIds, i, configs, uuid)
        uploadFileSign(configs, configs['src_files'][i], fileSignIds[i])
    utils.heavyLogging('fileSign: signIds {}'.format(fileSignIds))

    artifacts = [None] * len(fileSignIds)
    if configs['download'] == True:
        downloadThreads = []
        for i in range(len(fileSignIds)):
            downloadThreads.append(threading.Thread(target = downloadFileSign, args = (artifacts, configs, fileSignIds[i], i,)))
            downloadThreads[i].start()
        for i in range(len(fileSignIds)):
            downloadThreads[i].join()

    fpArtifacts = open(os.path.join(configs['work_dir'], '.artifacts'), 'w')
    fpArtifacts.write(','.join(artifacts))
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
    fileSign(configs)

if __name__ == "__main__":
    main(sys.argv)