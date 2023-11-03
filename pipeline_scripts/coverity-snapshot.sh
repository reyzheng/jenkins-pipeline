#!/bin/bash

# check if under parallel build
if [ -z ${BUILD_BRANCH+x} ]; then
    # BUILD_BRANCH not set
    uvar="COVCOMP_USER"
    pvar="COVCOMP_PASS"
else
    # Under parallel build, BUILD_BRANCH set
    uvar=$BUILD_BRANCH"_COVCOMP_USER"
    pvar=$BUILD_BRANCH"_COVCOMP_PASS"
fi
RESTUSER=`echo "${!uvar}"`
RESTPASS=`echo "${!pvar}"`

host=$1
port=$2
project=$3
snapshot=$4
offset=$5
cmd="curl -s --location
            --request POST 'http://${host}:${port}/api/v2/issues/search?offset=${offset}&includeColumnLabels=true&locale=en_us&queryType=bySnapshot'
            --header 'Content-Type: application/json'
            --header 'Accept: application/json'
            --user $RESTUSER:$RESTPASS
            --data-raw
            '{
                \"filters\": [
                    {
                        \"columnKey\": \"project\",
                        \"matchMode\": \"oneOrMoreMatch\",
                        \"matchers\": [
                            {
                                \"class\": \"Project\",
                                \"name\": \"${project}\",
                                \"type\": \"nameMatcher\"
                            }
                        ]
                    }
                ],
                \"columns\": [
                    \"cid\"
                ],
                \"snapshotScope\":{
                    \"show\":{
                        \"scope\":\"${snapshot}\"
                    }
                }
            }'"
eval $cmd
