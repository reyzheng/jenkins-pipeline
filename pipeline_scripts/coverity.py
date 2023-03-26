# coverity.py
import getopt
import sys

def coverity(configFile):
    fpJSON = open(configFile)
    coverityConfig = json.load(f)

    for i in range(0, len(coverityConfig["type"])):
        # TODO: check scriptTypes
        
        if (scriptAction == true) {
            if (coverityConfigScripted.expressions[i] && coverityConfigScripted.expressions[i] != "") {
                def expr = evaluate(coverityConfigScripted.expressions[i])
                if (expr == false) {
                    print "skip ${i}th script"
                    continue
                }
            }
        }

        def buildDir = ""
        if (scriptAction == false && buildDirs[i] != null) {
            buildDir = buildDirs[i]
        }
        def coverityConfigIdx = i
        if (coverityConfigScripted.buildmapping == "manytoone") {
            coverityConfigIdx = 0
        }
        def secondScanCleanDir = coverityConfigScripted.coverity_clean_builddir
        if (coverityConfigScripted.coverity_analyze_parent == "prev" ||
                coverityConfigScripted.coverity_analyze_parent == "branch" ||
                coverityConfigScripted.coverity_analyze_parent == "custom") {
            def varname
            secondScanCleanDir = false
            if (env.BUILD_BRANCH) {
                varname = "${env.BUILD_BRANCH}_SOURCE_DIR${i}"
            }
            else {
                varname = "SOURCE_DIR${i}"
            }
            def sourceDst = env."${varname}"

            if (coverityConfigScripted.coverity_analyze_parent == "custom") {
                dir(".gitscript") {
                    unstash name: 'stash-coverity-checkout-parent'
                    unstash name: 'stash-script-bdsh'
                }
                sh """
                    sh .gitscript/bdsh.sh .gitscript/checkout-parent.sh
                """
            }
            else {
                dir(".gitscript") {
                    unstash name: "git-label-submodules"
                    unstash name: "git-checkout-parent"
                }
                sh """
                    sh .gitscript/git-label-submodules.sh ${sourceDst}
                    sh .gitscript/git-checkout-parent.sh ${sourceDst} ${coverityConfigScripted.coverity_analyze_parent}
                """
            }
            dir(buildDir) {
                coverityConfigScripted.refParent = true
                coverity_scan(coverityConfigScripted, coverityPreloads, scriptTypes[i], scriptContents[i], coverityConfigIdx, scriptAction)
            }
            if (coverityConfigScripted.coverity_analyze_parent == "custom") {
                dir(".gitscript") {
                    unstash name: 'stash-coverity-checkout-parent'
                    unstash name: 'stash-script-bdsh'
                }
                sh """
                    sh .gitscript/bdsh.sh .gitscript/checkout-current.sh
                """
            }
            else {
                dir(".gitscript") {
                    unstash name: "git-checkout-parent"
                }
                sh """
                    sh .gitscript/git-checkout-parent.sh ${sourceDst} forward
                """
            }
        }
        dir(buildDir) {
            coverityConfigScripted.refParent = false
            coverityConfigScripted.coverity_clean_builddir = secondScanCleanDir
            coverity_scan(coverityConfigScripted, coverityPreloads, scriptTypes[i], scriptContents[i], coverityConfigIdx, scriptAction)
        }
    }


    fpJSON.close()

if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], "c:", ["config="])
    except getopt.GetoptError as err:
        print(err)
        sys.exit(2)
  
    for opt, arg in opts:
        if opt in ['-c']:
            config = arg

    coverity(config)