FROM python:3.6.6-slim-jessie

RUN mkdir /home/eng && /usr/sbin/groupadd -g 500 "eng" \
        && /usr/sbin/useradd -g 500 -d /home/eng -M -N -u 500 eng \
        && chown -R eng:eng /home/eng

COPY . /lco/floyds-guider-frame-processor

RUN python /lco/floyds-guider-frame-processor/setup.py install

USER eng

WORKDIR /home/eng
