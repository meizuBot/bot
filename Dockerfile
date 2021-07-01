FROM python:3.9.5-slim-buster
LABEL maintainer="ppotatoo"

RUN apt-get update; \
    apt-get install -y --no-install-recommends \
        git; \
    rm -rf /var/lib/apt/lists/*;

WORKDIR /
COPY requirements.txt /

RUN pip install -U -r requirements.txt

COPY / /badbot/


COPY docker_run.sh /run.sh

WORKDIR /badbot/src

ENTRYPOINT ["sh"]
CMD ["/badbot/run.sh"]

EXPOSE 6666/tcp