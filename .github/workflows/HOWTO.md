
```
act -j deploy-resource-manager --secret-file ~/local.env --eventpath .github/workflows/local-act.event.json -P ubuntu-latest=nektos/act-environments-ubuntu:18.04 --verbose --directory .
```


```
act -j create-quickstart-stack --secret-file ~/local.env --eventpath .github/workflows/local-act.event.json -P ubuntu-latest=nektos/act-environments-ubuntu:18.04 --verbose --directory .
```


