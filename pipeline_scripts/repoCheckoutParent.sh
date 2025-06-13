#!/bin/sh
if [ "$REPO_PROJECT" = "$1" ]; then
    if [ "$REPO_RREV" != "$GERRIT_BRANCH" ]; then
        echo "repoCheckoutParent.sh: skip REPO_PATH check ($REPO_RREV)"
        exit 0
    fi
    parentRevision=`ssh -p $GERRIT_PORT $GERRIT_HOST \
                        gerrit query --format=JSON commit:$GERRIT_PATCHSET_REVISION \
                        --dependencies|head -n 1|jq -r '.dependsOn[].revision'`
    #git checkout PF_BASE_BRANCH
    echo "repoCheckoutParent.sh: pwd"
    pwd
    echo "repoCheckoutParent.sh: parentRevision $parentRevision"
    git checkout -f $parentRevision
    git status
fi