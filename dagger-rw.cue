package main

import (
	"dagger.io/dagger"
	"dagger.io/dagger/core"
	"universe.dagger.io/bash"
	"universe.dagger.io/docker"
)

goBuilder:  _goBuilder.output
_goBuilder: docker.#Build & {
	steps: [
		docker.#Pull & {
			source: "index.docker.io/gcc:12.2"
		}
	]
}

dagger.#Plan & {
    client: {
        // Context: Interact with filesystem on host
        filesystem: {
			".": {
				read: {
					// Load the '.' directory (host filesystem) into dagger's runtime
					// Specify to Dagger runtime that it is a `dagger.#FS`
					contents: dagger.#FS
					//exclude: ["node_modules"]
				}
			}
			"a.out": write: contents: actions.up.res.contents
			//"tmp.out": write: contents: actions.up.res2.export.files["/tmp/workspace/source/a.out"]
			"tmp.out": write: contents: actions.up.res2.export.files["/output"]
        }
    }
	actions: {
		up: {
			build: bash.#Run & {
				input: goBuilder
				//mounts: kubeconfig: {
				//	dest:     "/run/secrets/kubeconfig"
				//	contents: client.commands.kubeconfig.stdout
				//}
				script: contents: #"""
					cd /tmp/workspace/source && gcc test.c
					cp /tmp/workspace/source/a.out /tmp
					ls -al /tmp/workspace/source
					"""#
				mounts: "Local FS": {
					// Path key has to reference the client filesystem you read '.' above
					contents: client.filesystem.".".read.contents
					// Where to mount the FS, in your container image
					dest: "/tmp/workspace"
				}
			}
			//res: dagger.#ReadFile & {
			res: core.#ReadFile & {
				input: build.output.rootfs
				path:  "/tmp/a.out"
			}
			res2: bash.#Run & {
				input: goBuilder
				script: contents: #"""
					echo res2
					ls -al /tmp/workspace/source
					echo haha > /output
				"""#
				mounts: "Local FS": {
					// Path key has to reference the client filesystem you read '.' above
					contents: client.filesystem.".".read.contents
					// Where to mount the FS, in your container image
					dest: "/tmp/workspace"
				}
				export: files: "/output": _
				//export: files: "/tmp/workspace/source/a.out": _
			}
		}
	}
}
