FROM ubuntu:latest
MAINTAINER Nirvik Ghosh "nirvik1993@gmail.com"
RUN apt-get update
RUN apt-get install -y python-pip python-dev build-essential gcc  libffi-dev libssl-dev
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
ENTRYPOINT ["python"]
CMD ["iwant/main.py"]
