def start() {
    sh """
        pwd && ls -al
    """
    print scm
    scm.GIT_URL
    //def cfg = readJSON file: pf-config.json
}

return this
