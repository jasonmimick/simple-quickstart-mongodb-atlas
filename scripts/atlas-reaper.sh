#!/usr/bin/env bash

filter="${1:-"XXX"}"
echo "filter=${filter}"
projects=$(mongocli iam projects list --output json | \
    jq "[ .results[] | select(.name | contains(\"${filter}\")) ]")
echo "projects=${projects}"

# Cleanup any clusters
CD=$(echo "${projects}" | jq -r ".[] | select(.clusterCount > 0) | .id+\":\"+.name")
echo "CD=${CD}"
while IFS= read -r cd
    do
        id=$(echo $cd | cut -d':' -f1)
        cluster=$(echo $cd | cut -d':' -f2)
        mongocli atlas clusters delete ${cluster} --projectId=${id} --force
    done < <(printf '%s\n' "${CD}")


echo "${projects}" | jq ".[] | .id" | \
    xargs -I {} mongocli iam projects delete {} --force

