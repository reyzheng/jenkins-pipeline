// usage: dagger-cue do hello --log-format=plain
package pipeline

import (
	"dagger.io/dagger"
	"dagger.io/dagger/core"
	//"universe.dagger.io/alpine"
	"universe.dagger.io/bash"
	"universe.dagger.io/docker"
	//"universe.dagger.io/netlify"
)

dagger.#Plan & {
	//_nodeModulesMount: "/src/node_modules": {
	//	dest:     "/src/node_modules"
	//	type:     "cache"
	//	contents: core.#CacheDir & {
	//		id: "todoapp-modules-cache"
	//	}
	//
	//}
	client: {
		filesystem: {
			//"./": read: {
			"./source": read: {
				contents: dagger.#FS
				exclude: [
					//"README.md",
					//"_build",
					//"pipeline.cue",
					//"node_modules",
				]
			}
			"./_build": write: contents: actions.build.contents.output
		}
		//env: {
		//	APP_NAME:      string
		//	NETLIFY_TEAM:  string
		//	NETLIFY_TOKEN: dagger.#Secret
		//}
	}
	actions: {
		deps: docker.#Build & {
			steps: [
				//alpine.#Build & {
				//	packages: {
				//		bash: {}
				//		yarn: {}
				//		git: {}
				//	}
				//},
				docker.#Pull & {
					source: "index.docker.io/gcc:12.2"
				},
				docker.#Copy & {
					contents: client.filesystem."./".read.contents
					dest:     "/src"
				},
				//bash.#Run & {
				//	workdir: "/src"
				//	mounts: {
				//		"/cache/yarn": {
				//			dest:     "/cache/yarn"
				//			type:     "cache"
				//			contents: core.#CacheDir & {
				//				id: "todoapp-yarn-cache"
				//			}
				//		}
				//		_nodeModulesMount
				//	}
				//	script: contents: #"""
				//		yarn config set cache-folder /cache/yarn
				//		yarn install
				//		"""#
				//},
			]
		}

		//test: bash.#Run & {
		//	input:   deps.output
		//	workdir: "/src"
		//	mounts:  _nodeModulesMount
		//	script: contents: #"""
		//		yarn run test
		//		"""#
		//}

		build: {
			run: bash.#Run & {
				input:   deps.output
				//mounts:  _nodeModulesMount
				workdir: "/src"
				script: contents: #"""
					#yarn run build
					pwd && ls -al
					#mkdir build
					#gcc source/test.c -o build/test
					#pwd && ls -al
					"""#
			}

			contents: core.#Subdir & {
				input: run.output.rootfs
				path:  "/src/build"
			}
		}

		//deploy: netlify.#Deploy & {
		//	contents: build.contents.output
		//	site:     client.env.APP_NAME
		//	token:    client.env.NETLIFY_TOKEN
		//	team:     client.env.NETLIFY_TEAM
		//}
	}
}
