FROM python:3.6-alpine

LABEL maintainer="hexzhou <hexzhou@hotmail.com>"

COPY ./go_spider.py /usr/local/bin/go_spider.py

RUN chmod a+rx /usr/local/bin/go_spider.py && pip install requests && mkdir /downloads

WORKDIR /downloads

VOLUME ["/downloads"]

ENTRYPOINT ["go_spider.py"]
CMD ["-h"]