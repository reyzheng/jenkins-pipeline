import sys, getopt, zipfile, glob
import os, shutil, logging, yaml, ruamel.yaml
import utils

def generateConfig(configs, mapFile):
    yaml = ruamel.yaml.YAML()

    srcConfig = os.path.join(os.getenv('PF_ROOT'), 'vendor', 'linkerscope', 'sample_config.yaml')
    with open(srcConfig) as stream:
        try:
            srcData = yaml.load(stream)
            dstData = dict()
            dstData['size'] = srcData['size']
            dstData['variables'] = srcData['variables']
            dstData['style'] = srcData['style']

            areaObject = dict()
            areaObject['area'] = dict()
            areaObject['area']['title'] = configs['title'] + '#{}'.format(os.getenv('BUILD_NUMBER'))
            areaObject['area']['sections'] = []
            # fill sections
            with open(mapFile) as fpYaml:
                mapYaml = yaml.load(fpYaml)
                utils.heavyLogging('generateConfig: {}'.format(mapYaml))
                counter = 0
                for memArea in mapYaml['map']:
                    # len(configs['graphs']) == 0: add all memArea
                    # memArea['id'] in configs['graphs']: add memArea defined in config
                    if len(configs['graphs']) == 0 or memArea['id'] in configs['graphs']:
                        section = dict()
                        section['names'] = yaml.seq([memArea['id']])
                        section['style'] = dict()
                        if counter % 6 == 0:
                            section['style']['fill'] = srcData['variables']['pastel_red']
                        elif counter % 6 == 1:
                            section['style']['fill'] = srcData['variables']['pastel_orange']
                        elif counter % 6 == 2:
                            section['style']['fill'] = srcData['variables']['pastel_yellow']
                        elif counter % 6 == 3:
                            section['style']['fill'] = srcData['variables']['pastel_green']
                        elif counter % 6 == 4:
                            section['style']['fill'] = srcData['variables']['pastel_blue']
                        elif counter % 6 == 5:
                            section['style']['fill'] = srcData['variables']['pastel_purple']
                        areaObject['area']['sections'].append(section)
                        counter = counter + 1
            dstData['areas'] = [areaObject]
            fpOutput = open(os.path.join(configs['WORK_DIR'], 'sample_config.yaml'), 'w')
            yaml.dump(dstData, fpOutput)
            fpOutput.close()
        except Exception as e:
            print(e)

def get_key(fp):
    filename = os.path.splitext(os.path.basename(fp))[0]
    int_part = filename.split('-')[1]
    return int(int_part)

def htmlReport(configs):
    svgFiles = sorted(glob.glob(os.path.join(configs['WORK_DIR'], 'memorymap-*.svg')), key=get_key)
    utils.heavyLogging('htmlReport: svgFiles, {}'.format(svgFiles))
    htmlTxt = ''
    for svgFile in svgFiles:
        htmlTxt += '<img src="{}" alt="Memory Map"/>\n'.format(os.path.basename(svgFile))
    fp = open(os.path.join(configs['WORK_DIR'], 'pf-htmlreport.html'), 'w')
    fp.write(htmlTxt)
    fp.close()
    fp = open(os.path.join(configs['WORK_DIR'], '.artifacts'), 'w')
    fp.write('memorymap-{}.svg'.format(os.getenv('BUILD_NUMBER')))
    fp.close()

def outputSVG(configs):
    pyExec = 'python'
    cmdPieces = ['python3', '--version']
    ret = utils.popenReturnCode(cmdPieces, dict(os.environ))
    if ret == 0:
        pyExec = 'python3'
    # ./linkerscope.py linker.map --config config.yaml --output map.svg
    linkerScope = os.path.join(configs['WORK_DIR'], 'linkerscope', 'linkerscope.py')
    mapFile = os.path.join(configs['WORK_DIR'], 'map-pruned.yaml')
    generateConfig(configs, mapFile)
    cmdPieces = [pyExec, linkerScope, mapFile, '--config', os.path.join(configs['WORK_DIR'], 'sample_config.yaml'), '--output', os.path.join(configs['WORK_DIR'], 'memorymap-{}.svg'.format(os.getenv('BUILD_NUMBER')))]
    utils.popenWithStdout(cmdPieces, dict(os.environ))
    htmlReport(configs)

def convertYAML(configs):
    pyExec = 'python'
    cmdPieces = ['python3', '--version']
    ret = utils.popenReturnCode(cmdPieces, dict(os.environ))
    if ret == 0:
        pyExec = 'python3'
    # ./linkerscope.py examples/sample_map.map --convert 
    linkerScope = os.path.join(configs['WORK_DIR'], 'linkerscope', 'linkerscope.py')
    # convert to map.yaml
    cmdPieces = [pyExec, linkerScope, configs['map_file_path'], '--convert']
    utils.popenWithStdout(cmdPieces, dict(os.environ))
    shutil.move('map.yaml', os.path.join(configs['WORK_DIR'], 'map.yaml'))
    # prune
    with open(os.path.join(configs['WORK_DIR'], 'map.yaml')) as stream:
        try:
            data = yaml.safe_load(stream)
            dataPruned = dict()
            dataPruned['map'] = []
            for addressObject in data['map']:
                if addressObject['type'] == 'area':
                    if 'flags' in addressObject:
                        del addressObject['flags']
                    dataPruned['map'].append(addressObject)
            fpOutput = open(os.path.join(configs['WORK_DIR'], 'map-pruned.yaml'), 'w')
            yaml.dump(dataPruned, fpOutput, allow_unicode=True)
            fpOutput.close()
        except yaml.YAMLError as exc:
            print(exc)

def initMemoryMap(configs):
    zipSrc = os.path.join(os.getenv('PF_ROOT'), 'vendor', 'linkerscope.zip')
    with zipfile.ZipFile(zipSrc, 'r') as zipRef:
        utils.heavyLogging('initMemoryMap: extract {} to {}'.format(zipSrc, configs['WORK_DIR']))
        zipRef.extractall(configs['WORK_DIR'])

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
        elif name in ('-c', '--command'):
            command = value
        elif name in ('-s', '--skip_translate'):
            skipTranslate = True
        elif name in ('-f', '--config'):
            configFile = value
        elif name in ('-w', '--work_dir'):
            if os.path.isdir(value) == False:
                os.makedirs(value)
            workDir = value

    logging.basicConfig(filename=os.path.join(workDir, 'memorymap.log'), format='%(asctime)s %(levelname)-8s %(message)s', level=logging.DEBUG, filemode='w')
    if skipTranslate == False:
        utils.translateConfig(configFile)
    configs = utils.loadConfigs(configFile)
    if configs['enabled'] == False:
        print('main: skip memorymap')
        sys.exit(0)
    configs['WORK_DIR'] = workDir
    if command == 'INIT':
        initMemoryMap(configs)
    elif command == 'CONVERT_YAML':
        convertYAML(configs)
    elif command == 'OUTPUT_SVG':
        outputSVG(configs)

if __name__ == '__main__':
    main(sys.argv)