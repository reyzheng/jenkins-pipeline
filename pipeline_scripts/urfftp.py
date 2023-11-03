import os, logging, shutil
import getopt, sys
import utils

def urfFtp(configs):
    cmdEnv = dict(os.environ)
    sftpHost = 'sdmft.rtkbf.com'
    if 'JENKINS_URL' in os.environ and '-infra' in os.getenv('JENKINS_URL'):
        sftpHost = 'rsdmft.rtkbf.com'

    os.makedirs(configs['dst'], exist_ok=True)
    if len(configs['files']) > 0:
        for file in configs['files']:
            code = utils.popenReturnCode(['scp', '-o', 'StrictHostKeyChecking=no', '-c', 'aes256-cbc', '-i', os.getenv('MFT_KEY'), '-rp', \
                                '{}@{}:release.out/{}/{}'.format(os.getenv('MFT_USER'), sftpHost, os.getenv('RELEASE_NAME'), file), \
                                configs['dst']], cmdEnv)
            if code != 0:
                sys.exit(code)
    else:
        code = utils.popenReturnCode(['scp', '-o', 'StrictHostKeyChecking=no', '-c', 'aes256-cbc', '-i', os.getenv('MFT_KEY'), '-rp', \
                            '{}@{}:release.out/{}/'.format(os.getenv('MFT_USER'), sftpHost, os.getenv('RELEASE_NAME')), \
                            configs['dst']], cmdEnv)
        if code != 0:
            sys.exit(code)

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
    
    if os.path.isdir(workDir) == True:
        shutil.rmtree(workDir)
    os.makedirs(workDir)
    logging.basicConfig(filename=os.path.join(workDir, 'urfftp.log'), level=logging.DEBUG, filemode='w')
    #utils.translateConfig(configFile)
    configs = utils.loadConfigs(configFile)
    configs['WORK_DIR'] = workDir

    #if configs['enable'] == False:
    #    print('main: skip')
    #    sys.exit(0)
    urfFtp(configs)

if __name__ == "__main__":
    main(sys.argv)