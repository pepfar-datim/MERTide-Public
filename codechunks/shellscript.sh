#!/usr/bin/env bash

# Exit immediately upon non-zero exit status
set -e ; set -o pipefail

# Add src/bash to PATH as necessary
if ! [[ $PATH =~ /opt/bao/bin ]]; then 
  export PATH="$PATH:../../src/bash"
fi

source dhis_config

