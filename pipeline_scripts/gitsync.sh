#!/bin/bash
MODE=
HOST=
PROJECT=
BRANCHES=

while getopts “s:m:h:p:b:?” argv
do
    case $argv in
        s)
            SQUASH=$OPTARG
            ;;
        m)
            MODE=$OPTARG
            ;;
        h)
            HOST=$OPTARG
            ;;
        p)
            PROJECT=$OPTARG
            ;;
        b)
            BRANCHES=$OPTARG
            ;;
        ?)
            ;;
    esac
done

function syncProject () {
    branch=$1

    git checkout $branch
    git pull origin $branch
    git push protect $branch
}

function createProjectAndPush () {
    HOST=$1
    branch=$2
    squash=$3

    DST=ssh://$HOST:29418/$branch
    git remote add protect ${DST}
    git checkout $branch
    git pull origin $branch
    projectExists=`ssh -p 29418 $HOST gerrit ls-projects | grep "^$branch"`
    if [ "$projectExists" = "" ]; then
        echo "create project "$branch
        ssh -p 29418 $HOST gerrit create-project $branch
    fi

    if [ "$squash" = "1" ]; then
        # trick, squash all commits
        git checkout --orphan init-$branch $branch
        git commit -m "initial commit"
        git push -u protect init-$branch:master
    else
        git push -u protect $branch:master
    fi
    git remote remove protect
}

# pure: project to project, like repro to protected/repo
#     usage: bash gitsync.sh -m pure -h ctcsoc.rtkbf.com -p sdlc/jenkins-pipeline
#     usage: bash gitsync.sh -m pure -h ctcsoc.rtkbf.com -p sdlc/jenkins-pipeline -b actions/urfchecker,actions/urfretriever
# branch: branch to project, all/specific branch to individual repo., rebase all commits to one or not
#     usage: bash gitsync.sh -m branch -h ctcsoc.rtkbf.com
#     usage: bash gitsync.sh -m branch -h ctcsoc.rtkbf.com -b actions/urfchecker,actions/urfretriever
if [ "$MODE" = "pure" ]; then
    DST=ssh://$HOST:29418/$PROJECT
    git remote add protect ${DST}
    if [ "$BRANCHES" = "" ]; then
        git branch -r > allbranches
        while read -r line
        do
            if [[ "$line" = "origin"* ]]; then
                branch=${line#*/}   # remove prefix ending in "/"
                if [[ "$branch" == *"HEAD"* ]]; then
                    echo "skip HEAD"
                else
                    syncProject $branch
                fi
            fi
        done < allbranches
    else
        export IFS=","
        for BRANCH in $BRANCHES; do
            syncProject $BRANCH
        done
    fi
    git remote remove protect
elif [ "$MODE" = "branch" ]; then
    if [ "$BRANCHES" = "" ]; then
        git branch -r > allbranches
        while read -r line
        do
            if [[ "$line" = "origin"* ]]; then
                branch=${line#*/}   # remove prefix ending in "/"
                if [[ "$branch" == *"HEAD"* ]]; then
                    echo "skip HEAD"
                else
                    createProjectAndPush $HOST $branch $SQUASH
                fi
            fi
        done < allbranches
    else
        export IFS=","
        for BRANCH in $BRANCHES; do
            createProjectAndPush $HOST $BRANCH $SQUASH
        done
    fi    
fi
