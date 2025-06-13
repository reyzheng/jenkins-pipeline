#!/bin/sh\n
if [ "$REPO_PROJECT" = "$1" ]; then
    echo "repoSyncRefspec.sh: check $REPO_PROJECT $REPO_RREV"
    if [ "$REPO_RREV" != "$GERRIT_BRANCH" ]; then
        echo "repoSyncRefspec.sh: skip auto patch apply ($REPO_RREV)"
        exit 0
    fi
    #if [ `git rev-parse --verify PF_BASE_BRANCH 2>/dev/null` ]; then
    #    git branch -D PF_BASE_BRANCH
    #fi
    #git checkout -b PF_BASE_BRANCH
    #remote=`git remote -v|grep fetch|cut -f 1`
    #git fetch --force --progress $remote $2:$2
    #git checkout -f $3
    #if [ `git rev-parse --verify PF_PATCH_BRANCH 2>/dev/null` ]; then
    #    git branch -D PF_PATCH_BRANCH
    #fi
    #git checkout -b PF_PATCH_BRANCH
    pwd
    remote=`git remote -v|grep fetch|cut -f 1`
    echo "git fetch --force --progress $remote $2:$2"
    git fetch --force --progress $remote $2:$2
    echo "git cherry-pick FETCH_HEAD"
    git cherry-pick FETCH_HEAD
    if [ "$?" == "128" ]; then
        # commit is a merge but no m option was given
        git cherry-pick -m 1 FETCH_HEAD
    fi
    if [ "$?" != "0" ]; then
        echo "cherry-pick failure"
        exit 1
    fi
    echo "rev-parse HEAD"
    git rev-parse HEAD
fi