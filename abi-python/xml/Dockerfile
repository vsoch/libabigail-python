FROM ghcr.io/autamus/clingo:latest
# docker build -f Dockerfile.clingo -t clingo .
ENV DEBIAN_FRONTEND=noninteractive
ENV PATH=/opt/conda/bin:$PATH
ARG LIBABIGAIL_VERSION=1.8
RUN apt-get update && apt-get install -y curl \
    build-essential \
    libelf-dev \
    libzip-dev \
    autoconf \
    libtool \
    pkg-config \
    libxml2 \
    libxml2-dev \
    elfutils \
    doxygen \
    wget \
    git \
    libdw-dev \
    elfutils \
    python3-lxml \
    python3 \
    python3-dev \
    python3-sphinx \
    python3-pip

RUN /bin/bash -c "curl -L https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh > miniconda.sh && \
    bash miniconda.sh -b -p /opt/conda && \
    rm miniconda.sh"
RUN /bin/bash -c "conda install -y -c conda-forge mamba && \
    mamba create -q -y -c potassco -n clingo-env clingo && \
    source activate clingo-env && \
    conda clean --all -y && \
    conda install clingo ipython six xmltodict"
RUN echo "source activate clingo-env" > ~/.bashrc
ENV PATH /opt/conda/envs/clingo-env/bin:${PATH}

# libabigail
RUN ldconfig && \ 
    wget http://mirrors.kernel.org/sourceware/libabigail/libabigail-${LIBABIGAIL_VERSION}.tar.gz && \
    tar -xvf libabigail-${LIBABIGAIL_VERSION}.tar.gz && \
    cd libabigail-${LIBABIGAIL_VERSION} && \
    mkdir build && \
    cd build && \
    ../configure --prefix=/usr/local  && \
    make all install && \
    ldconfig
ENTRYPOINT /bin/bash
WORKDIR /code
ADD . /code
