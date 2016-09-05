#!/bin/bash

download_mozilla_certs()
{
    local destination_dir
    destination_dir="${1}"
    local pem_url
    pem_url=https://curl.haxx.se/ca/cacert.pem

    echo "Downlading trusted ca from ${pem_url}"
    wget "${pem_url}" -O "${destination_dir}/cacert.pem"

    if [ $? -ne 0 ]; then
        echo "Download failed"
        exit 1
    fi
}

get_client_ca()
{
    local platform
    platform=$(uname -s)

    local destination_dir
    destination_dir="${1}"

    if [ "Linux" == "${platform}" ]; then
        echo "Checking /etc/ssl/certs/ca-certificates.crt"
        if [ -s /etc/ssl/certs/ca-certificates.crt ]; then 
            cp /etc/ssl/certs/ca-certificates.crt "${destination_dir}/cacert.pem"
        fi
    elif [ "Darwin" == "${platform}" ]; then
        echo "Checking /usr/local/etc/openssl/cert.pem"
        if [ -s /usr/local/etc/openssl/cert.pem ]; then 
            echo "Using /usr/local/etc/openssl/cert.pem"
            cp /usr/local/etc/openssl/cert.pem "${destination_dir}/cacert.pem"
        fi
    fi

    if [ ! -f "${destination_dir}/cacert.pem" ]; then
        download_mozilla_certs "${destination_dir}"
    fi
}

create_server_ca()
{
    local cert_file
    cert_file="${1}/cert.crt"
    local key_file
    key_file="${1}/cert.key"
    
    echo "Creating certificate for microProxy"
    openssl req -new -x509 -days 365 -nodes -out "${cert_file}" -keyout "${key_file}"

    if [ $? -ne 0 ]; then
        echo "Creating certificate failed"
        exit 1
    fi
}

print_usage()
{
    echo "Usage: mpcertutil.sh MODE [PATH]" 
    echo ""
    echo "   Create microProxy related certificate to the given PATH."
    echo "   PATH when not specified, will be the current directory."
    echo ""
    echo "example:"
    echo "   mpcertutil.sh all /var/tmp"
    echo "   mpcertutil.sh client /var/tmp"
    echo ""
    echo "Output MODE:"
    echo "   all: create both client and server certificate."
    echo "   client: Check locald trusted ca file. "
    echo "           If can not find one, download trusted ca file curl."
    echo "   server: create microproy server cert/key file"

}

if [ $# -lt 1 ]; then
    echo "mpcertutil.sh require at least one arguments."
    print_usage
    exit 1
fi

if [ $# -eq 1 ]; then
    download_path=$(pwd)
else
    download_path="${2}"
fi

if [ ! -d "${download_path}" ]; then
    echo "${download_path} folder not exist"
    exit 1
fi

if [ "${1}" == "all" ]; then
    create_server_ca ${download_path}
    get_client_ca ${download_path}
elif [ "${1}" == "client" ]; then
    get_client_ca ${download_path}
elif [ "${1}" == "server" ]; then
    create_server_ca ${download_path}
else 
    echo "unknown command"
    exit 1
fi
exit 0
