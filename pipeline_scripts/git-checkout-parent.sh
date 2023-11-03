#!/bin/sh
WORK_DIR=$PWD
SOURCE_PATH=$1

check_parent() {
    DIR=$1
    echo "Enter "$DIR
    cd $DIR

    CURRENT_COMMIT=`git rev-parse HEAD`
    PARENT_COMMIT=`git log --pretty=%P -n 1 "$CURRENT_COMMIT"`
    echo "CHECKOUT TO COMMIT "$PARENT_COMMIT
    git checkout -b prev-branch $PARENT_COMMIT

    cd $WORK_DIR
}

check_branch() {
    DIR=$1
    echo "Enter "$DIR
    cd $DIR

    CURRENT_COMMIT=`git rev-parse HEAD`
    echo "Find branch by commit "$CURRENT_COMMIT
    REMOTE_BRANCH=`git branch --format='%(refname:short)' -r --contains "$CURRENT_COMMIT" | cut -c8-`
    if [ -z "$REMOTE_BRANCH" ]; then
        # CURRENT_COMMIT not merged, cannot be found at remote
        # get last 10 parent commits
        PARENT_COMMITs=`git log --pretty=%P -n 10 "$CURRENT_COMMIT"`
        while IFS= read -r line ; do 
            echo "Find branch by parent commit "$line
            REMOTE_BRANCH=`git branch --format='%(refname:short)' -r --contains "$line" | cut -c8-`
            if [ ! -z "$REMOTE_BRANCH" ]; then
                break
            fi
        done <<< "$PARENT_COMMITs"
    fi
    echo "CHECKOUT TO BRANCH "$REMOTE_BRANCH
    git checkout $REMOTE_BRANCH

    cd $WORK_DIR
}

restore() {
    DIR=$1
    echo "Enter "$DIR
    cd $DIR

    git checkout PFtest-branch

    cd $WORK_DIR
}

cd $SOURCE_PATH
submoduels=`git config --file .gitmodules --get-regexp path | awk '{ print $2 }'`
cd $WORK_DIR
if [ "$2" == "prev" ]; then
    check_parent $SOURCE_PATH
    while IFS= read -r line ; do 
        cd $SOURCE_PATH
        check_parent $line
    done <<< "$submoduels"
elif [ "$2" == "branch" ]; then
    check_branch $SOURCE_PATH
    while IFS= read -r line ; do 
        cd $SOURCE_PATH
        check_branch $line
    done <<< "$submoduels"
else
    # forward, back to PFtest-branch
    restore $SOURCE_PATH
    while IFS= read -r line ; do 
        cd $SOURCE_PATH
        restore $line
    done <<< "$submoduels"
fi

cd $WORK_DIR