import os
import utils

def script(configs):
    validScriptTypes = ["inline", "file", "source", "groovy"]
    if configs['toolbox'] != '':
        execPrefix = 'singularity exec {}'.format(configs['toolbox'])
        utils.heavyLogging('script: execPrefix {}'.format(execPrefix))

    if configs['enable'] == False:
        utils.heavyLogging("Stage {} cancelld manually".format(configs['stageName']))
        return

    displayName = configs["display_name"]
    if displayName == "":
        displayName = configs['stageName']

    reportStageName = displayName
    if 'BUILD_BRANCH' in os.environ:
        reportStageName = "{} {}".format(reportStageName, os.getenv('BUILD_BRANCH'))

    try:
        for i in range(len(configs['types'])):
            if configs['types'][i] not in validScriptTypes:
                return

            #if (configs.expressions[i] && configs.expressions[i] != "") {
            #    def expr = evaluate(configs.expressions[i])
            #    if (expr == false) {
            #        print "skip ${i}th script"
            #        continue
            #    }
            #}

            utils.makeEmptyDirectory(".pf-{}".format(configs['plainStageName']))
            if configs['types'][i] == "inline":
                if (configs.sshcredentials == "") {
                    utils.inlineScript(configs.contents[i], underUnix, toolbox)
                }
                else {
                    sshagent(credentials: [configs.sshcredentials]) {
                        utils.inlineScript(configs.contents[i], underUnix, toolbox)
                    }
                }
            else:
                if (configs.sshcredentials == "") {
                    utils.fileScript(underUnix, configs.types[i], configs.contents[i], toolbox, configs["sshcredentials"], ".pf-${configs.plainStageName}")
                }
                else {
                    sshagent(credentials: [configs.sshcredentials]) {
                        utils.fileScript(underUnix, configs.types[i], configs.contents[i], toolbox, configs["sshcredentials"], ".pf-${configs.plainStageName}")
                    }
                }
            }
            utils.archiveStageArtifacts(configs["stageName"])
            dir (".pf-${configs.plainStageName}") {
                // export environment variables generated in py
                utils.exportEnv()
            }
        }

        if (env."PIPELINE_AS_CODE_STAGE_${displayName}_RESULTS") {
            env."PIPELINE_AS_CODE_STAGE_${displayName}_RESULTS" += "$reportStageName SUCCESS;"
        }
        else {
            env."PIPELINE_AS_CODE_STAGE_${displayName}_RESULTS" = "$reportStageName SUCCESS;"
        }
    }
    catch (e) {
        if (configs["failfast"] == true) {
            error(message: "${stageName} " + e)
        }
        unstable(message: "${stageName} is unstable " + e)
        if (env."PIPELINE_AS_CODE_STAGE_${displayName}_RESULTS") {
            env."PIPELINE_AS_CODE_STAGE_${displayName}_RESULTS" += "$reportStageName UNSTABLE;"
        }
        else {
            env."PIPELINE_AS_CODE_STAGE_${displayName}_RESULTS" = "$reportStageName UNSTABLE;"
        }
    }

def main(argv):
    #configs = utils.actionMain(argv)
    workDir = ''
    configFile = ''
    command = ''
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
        elif name in ('-c', '--command'):
            command = value
        elif name in ('-w', '--work_dir'):
            workDir = value

    if os.path.isdir(workDir) == False:
        os.makedirs(workDir)
    logging.basicConfig(filename=os.path.join(workDir, 'codeprompt.log'), format='%(asctime)s %(levelname)-8s %(message)s', level=logging.DEBUG, filemode='w')
    utils.translateConfig(configFile)
    configs = utils.loadConfigs(configFile)
    utils.cleanEnvAndArchives(workDir)
    if configs['enable'] == 'false' or configs['enable'] == False:
        utils.heavyLogging('main: skip codeprompt')
        sys.exit(0)
    configs['WORK_DIR'] = workDir
    utils.cleanEnvAndArchives(workDir)
    script(configs)
    if command == 'CHECK_ENV':
        utils.checkSingularity(workDir)
    else:
        codeprompt(configs)

if __name__ == '__main__':
    main(sys.argv)