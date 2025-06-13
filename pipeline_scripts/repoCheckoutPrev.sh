#!/bin/sh
if [ "$REPO_PROJECT" = "$1" ]; then
    if [ "$REPO_RREV" != "$GERRIT_BRANCH" ]; then
        echo "repoCheckoutPrev.sh: skip REPO_PATH check ($REPO_RREV)"
        exit 0
    fi
    echo "repoCheckoutPrev: path $REPO_PATH"
    #git checkout PF_BASE_BRANCH
    git reset --hard HEAD^
    git rev-parse HEAD
fi