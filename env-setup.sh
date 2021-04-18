#!/usr/bin/env bash
# shellcheck disable=SC1091

VENV_PATH=venv/forecasting-operations

if [[ -n "$1" ]]; then
    TIQ4CAST_BRANCH="$1"
else
    TIQ4CAST_BRANCH=master
fi

if [[ -n "$2" ]]; then
    TIQDS_BRANCH="$2"
else
    TIQDS_BRANCH=master
fi


function activate_new_virtualenv() {
  echo "[+] Creating a new python3.7 virtual-environment (${VENV_PATH})"

  rm -rf "${VENV_PATH}"
  pip3.7 install --upgrade virtualenv
  virtualenv -p python3.7 "${VENV_PATH}"

  if [[ -f "${VENV_PATH}/bin/activate" ]]; then
    echo "[+] Activating the environment (${VENV_PATH})"
    # shellcheck source=venv/forecasting-operations/bin/activate
    source "${VENV_PATH}/bin/activate"
  else
    echo "[-] ERROR: Could not set virtual environment ($VENV_PATH). See error message above."
    exit
  fi

}

function install_requirements() {
  echo "[+] Installing requirements.txt (1/2)..."

  if cat requirements.txt | grep -v '^#\|^git+ssh://' | xargs pip3.7 install;
  then
    echo "[+] Successfully installed requirements.txt (1/2)!"
  else
    echo "[-] ERROR: Failed to install requirements.txt (1/2) with exit code $?. See traceback above."
    exit "1"
  fi

  echo "[+] Installing requirements.txt (2/2)..."
  yes | pip uninstall tiqds tiq4cast
  if cat requirements.txt | grep '^git+ssh://' | sed "s/tiq4cast.git@master/tiq4cast.git@${TIQ4CAST_BRANCH}/" | sed "s/tiqds.git@master/tiqds.git@${TIQDS_BRANCH}/" | xargs pip3.7 install --no-cache ;
  then
    echo "[+] Successfully installed requirements.txt (2/2)!"
  else
    echo "[-] ERROR: Failed to install requirements.txt (2/2) with exit code $?. See traceback above."
    exit "1"
  fi
}

function add_pre_commit() {
  pip3.7 install pre-commit
  pre-commit install
}

echo "[+] Setting-up macOS environment..."

activate_new_virtualenv
install_requirements
add_pre_commit

echo "[+] python executable at:  $VENV_PATH/bin/python3.7"
