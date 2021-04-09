FROM ubuntu:20.04
ENV DEBIAN_FRONTEND=noninteractive
ARG LIBABIGAIL_VERSION=1.8
RUN apt-get update && apt-get install -y build-essential \
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
    python3 \
    python3-dev

# Yes we are cheating with xmltodict :)
RUN ldconfig && \ 
    wget http://mirrors.kernel.org/sourceware/libabigail/libabigail-${LIBABIGAIL_VERSION}.tar.gz && \
    tar -xvf libabigail-${LIBABIGAIL_VERSION}.tar.gz && \
    cd libabigail-${LIBABIGAIL_VERSION} && \
    mkdir build && \
    cd build && \
    ../configure --prefix=/usr/local  && \
    make all install && \
    ldconfig
WORKDIR /code
ADD . /code
