import os, logging, fnmatch
import re, json, glob
import getopt, sys
import utils, git, time

def parseError(configs):
    pwd = os.getcwd()
    if configs['log_files'] == '':
        utils.heavyLogging('parseError: invalid log file')
        sys.exit(0)
    logFilePatterns = configs['log_files'].split(',')
    sourceBases = configs['source_bases'].split(',')
    idx = 0
    errors = []
    for logFilePattern in logFilePatterns:
        for logFile in glob.glob(logFilePattern):
            utils.heavyLogging('parseError: logFile {}'.format(logFile))
            count = 0
            rootDir = ''
            with open(logFile) as fpLog:
                reEnteringDir = re.compile(r"Entering directory '(.*?)'")
                # error with line, column:
                #     error src/vendor/data_model/rtk/rtk_hosts_host_wanstats.c:58:19: error: unused variable 'entry' [-Werror=unused-variable](252971)
                # error with line only:
                #     drivers/mtd/nand/raw/nand.c:1: fatal error: cannot open drivers/mtd/nand/raw/nand.su for writing: No such file or directory
                #     configure.in:40: error: required file './compile' not found
                #     src/vendor/data_model/rtk/rtk_hosts_host_wanstats.c:51: error: unterminated #ifdef
                # error without line, column:
                #     collect2: error: ld returned 1 exit status
                reErrorAll = re.compile(r'^.*:[0-9]+:[0-9]+: (fatal )*error: ')
                reErrorLineOnly = re.compile(r'^.*:[0-9]+: (fatal )*error: ')
                errorPatterns = [
                    r"recipe for target '.*' failed",  # Common GNU make error
                    r"undefined reference to .*",     # Linker errors
                    r"missing separator.*",           # Missing tab or syntax error in Makefile
                ]
                # TODO:
                #reErrorGeneric = re.compile(r'^.*: (fatal )*error: ')
                while True:
                    line = fpLog.readline()
                    if not line:
                        break
                    count = count + 1
                    if reEnteringDir.search(line):
                        match = reEnteringDir.search(line)
                        rootDir = match.group(1)
                    elif reErrorAll.match(line) or reErrorLineOnly.match(line):
                        line = line.strip()
                        utils.heavyLogging('parseError: errorline, {}({})'.format(line, count))
                        error = dict()
                        tokens = line.split(':')
                        utils.heavyLogging('parseError: tokens {}'.format(tokens))
                        error['build_log'] = logFile
                        error['buildRootDir'] = rootDir
                        error['file'] = os.path.basename(tokens[0])
                        error['line'] = tokens[1]
                        error['error'] = line
                        errors.append(error)
                        if 'BLAME_AND_EMAIL' in configs['operations']:
                            if len(sourceBases) > idx:
                                sourceBase = sourceBases[idx]
                            else:
                                # one source base only
                                sourceBase = sourceBases[0]
                            os.chdir(sourceBase)
                            utils.heavyLogging('parseError: sourceBase {}'.format(sourceBase))

                            baseNameOnly = True
                            if os.path.isabs(tokens[0]):
                                # search level 1 dir,
                                # ex) /home/jenkins/workspace/DailyBuild/pipeline_daily_build_release_usdk_v2_2_0/usdk_6/ca_packages/ca-network-engine/1.0-r0/ca-network-engine-1.0/ni-drv-77c/ca_ni.c
                                # ni-drv-77c/ca_ni.c
                                fullPath = tokens[0]
                                baseDir = os.path.basename(os.path.normpath(os.path.dirname(tokens[0])))
                                error['file'] = os.path.join(baseDir, error['file'])
                                baseNameOnly = False
                                utils.heavyLogging('parseError: change base file to {}'.format(error['file']))
                            else:
                                utils.heavyLogging('parseError: general file {}'.format(error['file']))

                            fullPath = ''
                            lastModifiedDate = time.strptime('1970-01-01', '%Y-%m-%d')
                            for root, dirnames, filenames in os.walk('.'):
                                for filename in filenames:
                                    relPath = os.path.relpath(root, '.')
                                    relFilePath = os.path.join(relPath, filename).replace("\\", "/")  # Ensure consistent path separators
                                    match = False
                                    if baseNameOnly == True:
                                        if os.path.basename(relFilePath) == error['file']:
                                            match = True
                                    else:
                                        if relFilePath.endswith(error['file']):
                                            match = True
                                    if match == True:
                                        tmpFullPath = os.path.abspath(os.path.join(root, filename))
                                        modifiedDate = git.getLastModifiedDate(tmpFullPath)
                                        utils.heavyLogging('parseError: date {}, {}'.format(tmpFullPath, modifiedDate))
                                        if modifiedDate > lastModifiedDate:
                                            fullPath = os.path.abspath(os.path.join(root, filename))
                                            lastModifiedDate = modifiedDate
                            if fullPath != '':
                                os.chdir(os.path.dirname(fullPath))
                                ret = git.findAuthor(error['line'], error['file'])
                                if 'realtek' in ret['authorfull'] or 'realsil' in ret['authorfull']:
                                    error['filefull'] = fullPath
                                    error['author'] = ret['author']
                                    error['authorfull'] = ret['authorfull']
                                    retFileLineRevision = git.getFileLineRevision('', error['file'], error['line'])
                                    if ('realtek' in retFileLineRevision['committerfull'] or 'realsil' in retFileLineRevision['committerfull']) and error['author'] != retFileLineRevision['committer']:
                                        error['committer'] = retFileLineRevision['committer']
                                        error['committerfull'] = retFileLineRevision['committerfull']
                                    else:
                                        utils.heavyLogging('parseError: cannot find committer of {}({})'.format(error['file'], error['line']))
                                    error['revision'] = retFileLineRevision['revision']
                                else:
                                    utils.heavyLogging('parseError: invalid author {}'.format(ret['authorfull']))
                            else:
                                utils.heavyLogging('parseError: file {} not found'.format(error['file']))
                            os.chdir(pwd)
                        if configs['mode'] == 'first':
                            break
                    else:
                        hasOtherError = False
                        for pattern in errorPatterns:
                            if re.search(pattern, line, re.IGNORECASE):
                                hasOtherError = True
                                utils.heavyLogging('parseError: errorline(other), {}({})'.format(line, count))
                                break
                        if hasOtherError == True:
                            error = dict()
                            error['build_log'] = logFile
                            error['buildRootDir'] = rootDir
                            error['file'] = '-'
                            error['line'] = '-'
                            error['error'] = line
                            errors.append(error)
                            if configs['mode'] == 'first':
                                break
        idx = idx + 1
    # sort with author
    authorErrors = dict()
    for error in errors:
        foundAuthorOrCommitter = False
        if 'authorfull' in error and error['authorfull'] != '':
            foundAuthorOrCommitter = True
            if error['authorfull'] not in authorErrors:
                authorErrors[error['authorfull']] = dict()
                authorErrors[error['authorfull']]['author'] = error['author']
                authorErrors[error['authorfull']]['email'] = error['authorfull']
                authorErrors[error['authorfull']]['errors'] = []
            authorErrors[error['authorfull']]['errors'].append(error)
        if 'committerfull' in error and error['committerfull'] != '':
            foundAuthorOrCommitter = True
            if error['committerfull'] not in authorErrors:
                authorErrors[error['committerfull']] = dict()
                authorErrors[error['committerfull']]['author'] = error['committer']
                authorErrors[error['committerfull']]['email'] = error['committerfull']
                authorErrors[error['committerfull']]['errors'] = []
            authorErrors[error['committerfull']]['errors'].append(error)
        if foundAuthorOrCommitter == False:
            # mail to configs['unknowns'] if no author and no committer found
            if configs['unknowns'] != '':
                authorFull = configs['unknowns']
                if authorFull not in authorErrors:
                    authorErrors[authorFull] = dict()
                    authorErrors[authorFull]['author'] = 'UNKNOWN'
                    authorErrors[authorFull]['email'] = authorFull
                    authorErrors[authorFull]['errors'] = []
                authorErrors[authorFull]['errors'].append(error)
    with open(os.path.join(configs['WORK_DIR'], 'errors.json'), 'w') as fp:
        json.dump(errors, fp)
    with open(os.path.join(configs['WORK_DIR'], 'authorErrors.json'), 'w') as fp:
        json.dump(authorErrors, fp)

def main(argv):
    skipTranslate = False

    try:
        opts, args = getopt.getopt(argv[1:], 'c:w:f:v', ["command", "work_dir=", "config=", "version"])
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
        elif name in ('-c', '--command'):
            command = value

    logging.basicConfig(filename=os.path.join(workDir, 'action.log'), format='%(asctime)s %(levelname)-8s %(message)s', level=logging.DEBUG, filemode='w')
    if skipTranslate == False:
        utils.translateConfig(configFile)
    configs = utils.loadConfigs(configFile)
    configs['WORK_DIR'] = workDir
    if configs['enable'] == False:
        print('main: skip builderror action')
        sys.exit(0)
    if command == 'PARSE_ERROR':
        parseError(configs)

if __name__ == "__main__":
    main(sys.argv)