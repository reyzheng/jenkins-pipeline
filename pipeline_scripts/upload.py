import sys, getopt
import os, logging, glob, shutil
import utils

def upload(configs):
    if configs['dst_dir'] == '':
        configs['dst_dir'] = os.getcwd()
    os.makedirs(configs['dst_dir'], exist_ok=True)
    patterns = configs['src_files'].split(',')
    utils.heavyLogging('upload: patterns {}'.format(patterns))
    for pattern in patterns:
        files = glob.glob(os.path.join(os.getenv('PF_ROOT'), 'scripts', pattern))
        utils.heavyLogging('upload: pattern {}, match {}'.format(pattern, files))
        for file in files:
            shutil.copy(file, configs['dst_dir'])
            utils.heavyLogging('upload: copy {} to {}'.format(file, configs['dst_dir']))

def main(argv):
    workDir = ''
    configFile = ''
    try:
        opts, args = getopt.getopt(argv[1:], 'w:f:v', ["work_dir=", "config=", "version"])
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

    logging.basicConfig(filename=os.path.join(workDir, 'upload.log'), format='%(asctime)s %(levelname)-8s %(message)s', level=logging.DEBUG, filemode='w')
    configs = utils.loadConfigs(configFile)
    if configs['enabled'] == False:
        print('main: skip upload')
        sys.exit(0)
    configs['WORK_DIR'] = workDir
    upload(configs)

if __name__ == '__main__':
    main(sys.argv)
