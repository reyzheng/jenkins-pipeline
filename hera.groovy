def start() {
    sh """
        pwd && ls -al
    """
    print scm
    //def cfg = readJSON file: pf-config.json
}

return this
