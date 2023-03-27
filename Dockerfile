FROM golang:1.20-buster as protoc

WORKDIR /protobuf-builder

RUN apt update && apt install unzip
RUN go install github.com/verloop/twirpy/protoc-gen-twirpy@latest
RUN wget https://github.com/protocolbuffers/protobuf/releases/download/v3.19.5/protoc-3.19.5-linux-x86_64.zip && unzip protoc-3.19.5-linux-x86_64.zip && cp bin/protoc /bin/protoc

COPY eth_challenge_base/protobuf protobuf
RUN protoc --python_out=. --twirpy_out=. protobuf/sui_challenge.proto


FROM rust:1.68-buster AS chef
WORKDIR sui
ARG GIT_REVISION
ENV GIT_REVISION=$GIT_REVISION
RUN apt-get update && apt-get install -y cmake clang

FROM chef AS planner
COPY sui/Cargo.toml sui/Cargo.lock ./
COPY sui/crates/workspace-hack crates/workspace-hack
RUN sed -i '/crates\/workspace-hack/b; /crates/d; /narwhal/d' Cargo.toml \
    && cargo metadata -q >/dev/null

FROM chef AS builder
COPY --from=planner /sui/Cargo.toml Cargo.toml
COPY --from=planner /sui/Cargo.lock Cargo.lock
COPY --from=planner /sui/crates/workspace-hack crates/workspace-hack
RUN cargo build --release

COPY sui/Cargo.toml sui/Cargo.lock ./
COPY sui/crates crates
COPY sui/narwhal narwhal
RUN cargo build --release \
    --bin sui-node \
    --bin sui \
    --bin sui-faucet \
    --bin stress \
    --bin sui-cluster-test

FROM python:3.10.10-slim-buster

WORKDIR /home/ctf

RUN apt update \
    && apt install -y --no-install-recommends build-essential tini xinetd \
    curl git-all cmake gcc libssl-dev pkg-config libclang-dev libpq-dev \
    && apt clean \
    && rm -rf /var/lib/apt/lists/*

RUN pip install pipenv
COPY Pipfile Pipfile.lock .
RUN pipenv install --system

RUN git clone -b 157ac7 https://github.com/MystenLabs/sui.git /root/.move/https___github_com_MystenLabs_sui_git_devnet

COPY sui_client.py .
COPY server.py .
COPY eth_challenge_base eth_challenge_base
COPY --from=protoc /protobuf-builder/protobuf eth_challenge_base
COPY --from=builder /sui/target/release/sui-node /usr/local/bin
COPY --from=builder /sui/target/release/sui /usr/local/bin
COPY --from=builder /sui/target/release/sui-faucet /usr/local/bin
COPY --from=builder /sui/target/release/stress /usr/local/bin
COPY --from=builder /sui/target/release/sui-cluster-test /usr/local/bin

COPY xinetd.sh /xinetd.sh
COPY entrypoint.sh /entrypoint.sh
RUN mkdir /var/log/ctf
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["tini", "-g", "--"]
CMD ["/entrypoint.sh"]