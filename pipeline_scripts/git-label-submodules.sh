#!/bin/sh
WORK_DIR=$PWD
SOURCE_PATH=$1

cd $SOURCE_PATH
submoduels=`git config --file .gitmodules --get-regexp path | awk '{ print $2 }'`
while IFS= read -r line ; do
    echo "Enter "$line
    cd $line
    git checkout -b PFtest-branch
    cd $SOURCE_PATH
done <<< "$submoduels"

cd $WORK_DIR