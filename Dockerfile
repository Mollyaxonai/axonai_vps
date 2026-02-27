FROM stanfordnmbl/opensim-python:4.3

# We used to do this locally until 12/2/23...but there isn't a Release file for ubuntu 20.04.
# RUN add-apt-repository ppa:jonathonf/ffmpeg-4 ; apt update
# RUN apt-get install ffmpeg -y --fix-missing

# Combine apt commands into a single layer to reduce image size
RUN apt update && apt install --no-install-recommends -y ffmpeg curl && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/

# Install uv using the official installer and add to PATH
ENV PATH="/root/.local/bin:${PATH}"
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    /root/.local/bin/uv --version

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y git

# Copy dependency files
COPY pyproject.toml uv.lock /workspace/

# Use Python 3.12 (project requires >=3.9, <3.13; base image has 3.14)
RUN uv python install 3.12

# Create venv using 3.12
RUN uv venv --python 3.12 /workspace/.venv

# Make the 3.12 venv the default interpreter inside the container
ENV VIRTUAL_ENV=/workspace/.venv
ENV PATH="/workspace/.venv/bin:${PATH}"

# Trust GitHub host
RUN mkdir -p -m 0700 /root/.ssh && \
    ssh-keyscan github.com >> /root/.ssh/known_hosts

# Sync into that environment
RUN --mount=type=ssh uv sync --python /workspace/.venv/bin/python

# Sanity check: default python in the image should be 3.12.x
RUN python --version && python3 --version

# Copy the rest of the application
COPY . /workspace/
