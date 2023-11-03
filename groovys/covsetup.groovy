def init(stageName) {
    def utils = load "utils.groovy"
    def defaultConfigs = [
        display_name: "Coverity-Setup",
        url: "http://172.21.15.146:8080",
        credentials: "",
        admin_account: "",
        user_account: "",
        project: "",
        stream: "",

        scriptableParams: ["project", "stream"]
    ]
    def config = utils.commonInit(stageName, defaultConfigs)
    utils.stashScriptedParamScripts(config.settings)

    return config
}

def checkProjectExistence(configs) {
    def projectExists = false

    if (configs.project.trim() == "") {
        projectExists = true
    }
    else {
        withCredentials([file(credentialsId: configs.credentials, variable: 'KEY_PATH')]) {
            def secret = readJSON file: KEY_PATH
            def responseTxt = sh (script: """
                            curl "${configs.url}/api/v2/projects/${configs.project}?includeChildren=true&includeStreams=true&locale=en_us" \
                            -X GET \
                            -H "accept: application/json" \
                            --user "${secret.username}:${secret.key}"
                        """, returnStdout: true).trim()
            def response = readJSON text: responseTxt
            if (response.code != 1302) {
                projectExists = true
            }
            // Not exists: {"projects":null,"code":1302,"message":"No project found for name CTCSOC_Test."}
        }
    }

    return projectExists
}

def checkStreamExistence(configs) {
    def streamExists = false

    if (configs.stream.trim() == "") {
        streamExists = true
    }
    else {
        withCredentials([file(credentialsId: configs.credentials, variable: 'KEY_PATH')]) {
            def secret = readJSON file: KEY_PATH
            def responseTxt = sh (script: """
                            curl "${configs.url}/api/v2/streams/${configs.stream}?locale=en_us" \
                            -X GET \
                            -H "accept: application/json" \
                            --user "${secret.username}:${secret.key}"
                        """, returnStdout: true).trim()
            def response = readJSON text: responseTxt
            if (response.code != 1300) {
                streamExists = true
            }
            // Not exists: {"streams":null,"code":1300,"message":"Stream \"CTCSOC_ttest_test\" does not exist or you do not have permission to access it."}
        }
    }

    return streamExists
}

def createProject(configs) {
	def payload = """
        {
	        "name": "${configs.project}",
	        "description": "This is a ${configs.project} project",
	        "roleAssignments": [
		        {
		            "roleAssignmentType": "user",
		            "roleName": "projectOwner",
		            "scope": "project",
		            "username": "${configs.admin_account}"
		        },
		        {
			        "group": {
				        "name": "Users"
			        },
			        "roleAssignmentType": "group",
			        "roleName": "noAccess",
			        "scope": "project"
                }
	        ]
	}"""
	
    withCredentials([file(credentialsId: configs.credentials, variable: 'KEY_PATH')]) {
        def secret = readJSON file: KEY_PATH
	    def response = sh (script: """
		                    curl "${configs.url}/api/v2/projects?locale=en_us" \
		                    -X POST \
		                    -d '${payload}'\
		                    -H "Content-type: application/json" \
		                    -H "accept: application/json" \
		                    --user "${secret.username}:${secret.key}"
	                """, returnStdout: true).trim()
	    println response
    }
}

def createStream(configs) {
    def payload = """
        {
            "name": "${configs.stream}",
            "triageStoreName": "Default Triage Store",
            "primaryProjectName": "'${configs.project}'",
            "ownerAssignmentOption": "default_component_owner",
            "autoDeleteOnExpiry": true,
            "enableDesktopAnalysis": true,
            "summaryExpirationDays": 30,
            "analysisVersionOverride": "2021.06",
            "pluginVersionOverride": "1.7.5",
            "componentMapName": "Default",
            "versionMismatchMessage": "wrong version",
            "roleAssignments": [
                {
                    "roleAssignmentType": "user",
                    "roleName": "streamOwner",
                    "scope": "stream",
                    "username": "${configs.admin_account}"
                },
                {
                    "roleAssignmentType": "user",
                    "roleName": "committer",
                    "scope": "stream",
                    "username": "${configs.user_account}"
                }
            ]
    }"""

    withCredentials([file(credentialsId: configs.credentials, variable: 'KEY_PATH')]) {
        def secret = readJSON file: KEY_PATH
	    def response = sh (script: """
		                    curl "${configs.url}/api/v2/streams?locale=en_us" \
		                    -X POST \
		                    -d '${payload}'\
		                    -H "Content-type: application/json" \
		                    -H "accept: application/json" \
		                    --user "${secret.username}:${secret.key}"
	                """, returnStdout: true).trim()
	    println response
    }
}

def func(pipelineAsCode, configsRaw, preloads) {
    unstash name: "stash-script-utils"
    def utils = load "utils.groovy"
    def configs = [:]
    utils.unstashScriptedParamScripts(preloads.plainStageName, configsRaw, configs)

    lock ("COVSETUP") {
        if (checkProjectExistence(configs) == false) {
            print "Create coverity project ${configs.project}"
            createProject(configs)
        }
        else {
            print "Coverity project ${configs.project} was already existed."
        }
    }

    lock ("COVSETUP") {
        if (checkStreamExistence(configs) == false) {
            print "Create coverity stream ${configs.stream}"
            createStream(configs)
        }
        else {
            print "Coverity stream ${configs.stream} was already existed."
        }
    }
}

return this
