# gulliver

Gulliver simulates a CD pipeline in XL Deploy. Packages are created & imported at random times. Versions are either patch, minor or major releases. Each new application version is sequentially deployed to a DEV, TEST, ACC and PROD environment.

# Running

```
bin/cli.sh -username admin -password admin1 -q -f gulliver.py; stty sane
```
