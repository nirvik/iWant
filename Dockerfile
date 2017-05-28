FROM ubuntu:latest
MAINTAINER Nirvik Ghosh "nirvik1993@gmail.com"
RUN apt-get update
RUN apt-get install -y python-pip python-dev build-essential gcc  libffi-dev libssl-dev
COPY . /app
WORKDIR /app
RUN python setup.py install --user
ENTRYPOINT ["python -m iwant.cli.main start"]
