#!/bin/sh
if [ "$REPO_PROJECT" = "$1" ]; then
    if [ "$REPO_RREV" != "$GERRIT_BRANCH" ]; then
        echo "repoCheckoutCurrent.sh: skip REPO_PATH check ($REPO_RREV)"
        exit 0
    fi
    echo "repoCheckoutCurrent: path $REPO_PATH"
    #git checkout PF_PATCH_BRANCH
    git cherry-pick FETCH_HEAD
    git rev-parse HEAD
fi