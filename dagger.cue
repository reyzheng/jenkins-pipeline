// usage: dagger-cue do hello --log-format=plain
package main

import (
    "dagger.io/dagger"
    "dagger.io/dagger/core"
)

dagger.#Plan & {
    //client: env: GREETING: string | *"hello"
    client: filesystem: ".": read: {
        // Load the '.' directory (host filesystem) into dagger's runtime
        // Specify to Dagger runtime that it is a `dagger.#FS`
        contents: dagger.#FS
        //exclude: ["node_modules"]
    }

    actions: {
        image: core.#Pull & {
            source: "gcc:12.2"
        }
        hello: core.#Exec & {
            input: image.output
            args: ["echo", "\(client.env.GREETING), world!"]
            always: true
        }
        mybuild: core.#Exec & {
            input: image.output
            args: ["gcc", "/tmp/workspace/source/test.c"]
            always: true
            mounts: "Local FS": {
                // Path key has to reference the client filesystem you read '.' above
                contents: client.filesystem.".".read.contents
                // Where to mount the FS, in your container image
                dest: "/tmp/workspace"
            }
        }
        myexport: core.#Exec & {
            input: mybuild.output
            args: ["ls", "-al", "/"]
            always: true
            mounts: "Local FS": {
                // Path key has to reference the client filesystem you read '.' above
                contents: client.filesystem.".".read.contents
                // Where to mount the FS, in your container image
                dest: "/tmp/workspace"
            }
        }
    }
}
