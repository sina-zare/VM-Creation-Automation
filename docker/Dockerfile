# Usage:
# docker build \
#  --build-arg HTTP_PROXY=http://proxy.example.com:8080 \
#  --build-arg HTTPS_PROXY=http://proxy.example.com:8080 \
#  --build-arg NO_PROXY="localhost,127.0.0.1,.abramad.com,.cloud.local,.abramad.cloud" \
#  -t tap:1.0.0 .

ARG PYTHON_VERSION=3.12
# FILEBEAT_VERSION Must match ElasticSearch cluster version
ARG FILEBEAT_VERSION=8.19.9
ARG FILEBEAT_IMAGE=docker.elastic.co/beats/filebeat:${FILEBEAT_VERSION}

FROM ${FILEBEAT_IMAGE} AS filebeat
FROM python:${PYTHON_VERSION}-slim

ARG TERRAFORM_VERSION=1.13.0

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

# Set only if you need to send data through proxy in image later.
# ENV HTTP_PROXY=${HTTP_PROXY}
# ENV HTTPS_PROXY=${HTTPS_PROXY}
# ENV NO_PROXY=${NO_PROXY}

# ------------------------------------------------------------
# OS dependencies
# ------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    git \
    openssh-client \
    sshpass \
    jq \
    tzdata \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*


# ------------------------------------------------------------
# Terraform
# ------------------------------------------------------------
RUN curl -fsSL \
    https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip \
    -o /tmp/terraform.zip \
 && unzip /tmp/terraform.zip -d /usr/local/bin \
 && rm /tmp/terraform.zip \
 && terraform version

# ------------------------------------------------------------
# Terraform provider mirror
# ------------------------------------------------------------
 RUN mkdir -p /etc/terraform.d
 COPY terraform/cli-config.tfrc /etc/terraform.d/cli-config.tfrc
 ENV TF_CLI_CONFIG_FILE=/etc/terraform.d/cli-config.tfrc


# ------------------------------------------------------------
# Ansible
# ------------------------------------------------------------
RUN pip install --no-cache-dir ansible-core pywinrm requests-ntlm

# ------------------------------------------------------------
# Ansible collections
# ------------------------------------------------------------
COPY ansible/requirements.yml /tmp/ansible-requirements.yml
RUN ansible-galaxy collection install \
    -r /tmp/ansible-requirements.yml \
    -p /usr/share/ansible/collections

ENV ANSIBLE_COLLECTIONS_PATH=/usr/share/ansible/collections


# ------------------------------------------------------------
# Python libraries
# ------------------------------------------------------------
COPY python/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip --index-url http://vnk-nexus.abramad.com/repository/pypi-proxy/simple --trusted-host vnk-nexus.abramad.com \
&& pip install --no-cache-dir -r /tmp/requirements.txt --index-url http://vnk-nexus.abramad.com/repository/pypi-proxy/simple --trusted-host vnk-nexus.abramad.com

# ------------------------------------------------------------
# Filebeat (copied from the official image)
# ------------------------------------------------------------
COPY --from=filebeat /usr/share/filebeat/filebeat /usr/local/bin/filebeat
RUN filebeat version

# ------------------------------------------------------------
# Run as non-root
# ------------------------------------------------------------
RUN useradd --create-home --shell /bin/bash pipeline
USER pipeline

WORKDIR /workspace