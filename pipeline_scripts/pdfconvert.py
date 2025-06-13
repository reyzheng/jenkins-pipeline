import json
import shutil
import sys, getopt, glob
import os, logging
import utils

def pdfConvert(configs):
    cmdEnv = dict(os.environ)

    watermarkFormat = []
    if configs['watermark'] == 'FORMAT_1':
        watermarkFormat = ['-F', 'WatermarkColor=#4287F5', \
                            '-F', 'WatermarkSize=70', \
                            '-F', 'WatermarkText=Realtek', \
                            '-F', 'WatermarkBoutlineOnly=true']
    # online url "https://pdfservice.realtek.com/ConvertPDF/PDFService"
    # test url
    baseUrl = 'https://pdfservice1.realtek.com:1147/ConvertPDF/PDFService'

    if configs['dst_dir'] != '':
        utils.makeEmptyDirectory(configs['dst_dir'])
    files = configs['files'].split(',')
    for file in files:
        subfiles = glob.glob(file)
        utils.heavyLogging('pdfConvert: found files {}({})'.format(subfiles, file))
        for subfile in subfiles:
            cmdCurl = ['curl', '-s', '-k', '-X', 'POST', baseUrl, \
                        '-F', 'Username={}'.format(configs['username']), \
                        '-F', 'File=@{}'.format(subfile)] + watermarkFormat
            ret = utils.popenReturnStdout(cmdCurl, cmdEnv)
            try:
                retJson = json.loads(ret['lines'][0])
            except:
                utils.heavyLogging('pdfConvert: unknown error {}'.format(ret))
                sys.exit(-1)
            filename = os.path.basename(subfile)
            outputFile = '{}.pdf'.format(os.path.splitext(filename)[0])
            if retJson['Result'] == 'Success':
                downloadUrl = retJson['ResultFileUrl']
                #cmdCurl = ['curl', '-s', '-k', downloadUrl, '-o', os.path.join(configs['dst_dir'], outputFile)]
                cmdCurl = ['curl', '-s', '-k', downloadUrl, '-o', outputFile]
                utils.popenWithStdout(cmdCurl, cmdEnv)
                utils.heavyLogging('pdfConvert: download {}'.format(os.path.join(configs['dst_dir'], outputFile)))
                if configs['dst_dir'] != '':
                    shutil.move(outputFile, configs['dst_dir'])

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
    pdfConvert(configs)

if __name__ == '__main__':
    main(sys.argv)