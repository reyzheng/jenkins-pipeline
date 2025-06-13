#!/bin/sh
if [ "$REPO_PROJECT" = "$1" ]; then
    if [ "$REPO_RREV" != "$GERRIT_BRANCH" ]; then
        echo "repoPath.sh: skip REPO_PATH check ($REPO_RREV)"
        exit 0
    fi
    echo $REPO_PATH > $2
fi