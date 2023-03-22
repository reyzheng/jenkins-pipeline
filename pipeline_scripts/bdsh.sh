filename=$1
line=$(head -n 1 $filename)
if [ -z "${line##*"bash"*}" ]; then
    bash $1
else
    sh $1
fi
