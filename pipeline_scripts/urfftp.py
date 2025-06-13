import os, logging, shutil
import getopt, sys
import zipfile
import utils

def downloadFtp(configs, sftpHost):
    cmdEnv = dict(os.environ)
    if len(configs['files']) > 0:
        for file in configs['files']:
            if 'RELEASE_NAME' in os.environ:
                # URF triggered Jenkins job, download files under release.out
                downloadFile = 'release.out/{}/{}'.format(os.getenv('RELEASE_NAME'), file)
            else:
                downloadFile = file
            code = utils.popenReturnCode(['scp', '-o', 'StrictHostKeyChecking=no', '-c', 'aes256-cbc', '-i', os.getenv('MFT_KEY'), '-rp', \
                                '{}@{}:{}'.format(os.getenv('MFT_USER'), sftpHost, downloadFile), \
                                configs['dst']], cmdEnv)
            utils.heavyLogging('download: {} to {}'.format(downloadFile, configs['dst']))
            if code != 0:
                sys.exit(code)
            if configs['auto_zipunzip'] == True and downloadFile.endswith('.zip'):
                pwd = os.getcwd()
                if os.path.isdir(configs['dst']):
                    fileToExtract = os.path.basename(downloadFile)
                    workDir = configs['dst']
                else:
                    fileToExtract = os.path.basename(configs['dst'])
                    workDir = os.path.dirname(configs['dst'])
                os.chdir(workDir)
                utils.heavyLogging('downloadFtp: extract {} to {}'.format(fileToExtract, workDir))
                with zipfile.ZipFile(fileToExtract, 'r') as zObject: 
                    zObject.extractall(path='.') 
                os.chdir(pwd)
    elif 'RELEASE_NAME' in os.environ:
        code = utils.popenReturnCode(['scp', '-o', 'StrictHostKeyChecking=no', '-c', 'aes256-cbc', '-i', os.getenv('MFT_KEY'), '-rp', \
                            '{}@{}:release.out/{}/'.format(os.getenv('MFT_USER'), sftpHost, os.getenv('RELEASE_NAME')), \
                            configs['dst']], cmdEnv)
        utils.heavyLogging('download: {} to {}'.format(os.getenv('RELEASE_NAME'), configs['dst']))
        if code != 0:
            sys.exit(code)
    else:
        utils.heavyLogging('download: skip')

def uploadFtp(configs, sftpHost):
    cmdEnv = dict(os.environ)
    if len(configs['files']) > 0:
        for file in configs['files']:
            uploadFile = file
            if configs['auto_zipunzip'] == True:
                if os.path.isdir(file):
                    # directory
                    uploadFile = '{}.zip'.format(file)
                    # .zip suffix would be added in make_archive()
                    utils.heavyLogging('uploadFtp: zip {} to {}'.format(file, uploadFile))
                    shutil.make_archive(file, 'zip', file)
                else:
                    # file
                    uploadFile = '{}.zip'.format(os.path.splitext(file)[0])
                    utils.heavyLogging('uploadFtp: zip {} to {}'.format(file, uploadFile))
                    zipfile.ZipFile(uploadFile, mode='w').write(file)

            code = utils.popenReturnCode(['scp', '-o', 'StrictHostKeyChecking=no', '-c', 'aes256-cbc', \
                                '-i', os.getenv('MFT_KEY'), '-rp', uploadFile, \
                                '{}@{}:{}'.format(os.getenv('MFT_USER'), sftpHost, configs['dst'])], \
                                cmdEnv)
            utils.heavyLogging('upload: {} to {}'.format(uploadFile, configs['dst']))
            if code != 0:
                utils.heavyLogging('upload: failure {}'.format(code))
                sys.exit(code)

def urfFtp(configs):
    cmdEnv = dict(os.environ)
    sftpHost = 'sdmft.rtkbf.com'
    if 'JENKINS_URL' in os.environ and '-infra' in os.getenv('JENKINS_URL'):
        sftpHost = 'rsdmft.rtkbf.com'

    if configs['dst'].strip() == '':
        configs['dst'] = '.'
    else:
        os.makedirs(configs['dst'], exist_ok=True)
    if 'MFT_KEY' not in os.environ:
        print('urfFtp: MFT_KEY not defined')
        sys.exit(1)

    if os.name != "posix":
        # windows
        outputs = utils.popenReturnStdout(['whoami'], cmdEnv)
        if outputs['code'] == 0:
            userName = bytes.decode(outputs['lines'][0], 'utf-8')
        else:
            utils.heavyLogging('urfFtp: whoami error')
            sys.exit(outputs['code'])
        utils.popenWithStdout(['Icacls', os.getenv('MFT_KEY'), '/c', '/t', '/Inheritance:d'], cmdEnv)
        utils.popenWithStdout(['Icacls', os.getenv('MFT_KEY'), '/c', '/t', '/Grant', '{}:F'.format(userName)], cmdEnv)
        utils.popenWithStdout(['Icacls', os.getenv('MFT_KEY'), '/c', '/t', '/Grant:r', '{}:F'.format(userName)], cmdEnv)
        utils.popenWithStdout(['Icacls', os.getenv('MFT_KEY'), '/c', '/t', '/Remove:g', \
                                'Authenticated Users', 'BUILTIN\Administrators', 'BUILTIN', 'Everyone', 'System', 'Users'], cmdEnv)
        utils.popenWithStdout(['Icacls', os.getenv('MFT_KEY')], cmdEnv)
        utils.heavyLogging('urfFtp: change {} read only'.format(os.getenv('MFT_KEY')))
    if configs['operation'] == 'DOWNLOAD':
        downloadFtp(configs, sftpHost)
    else:
        uploadFtp(configs, sftpHost)

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
    logging.basicConfig(filename=os.path.join(workDir, 'urfftp.log'), level=logging.DEBUG, filemode='w')
    #utils.translateConfig(configFile)
    configs = utils.loadConfigs(configFile)
    configs['WORK_DIR'] = workDir

    if configs['enable'] == False:
        print('main: skip')
        sys.exit(0)
    urfFtp(configs)

if __name__ == "__main__":
    main(sys.argv)